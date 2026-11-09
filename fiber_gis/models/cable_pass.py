"""Cables que atraviesan elementos: detección sobre el recorrido y registro como cable de paso."""

import json
import math

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from .route_geometry import GRID_CELL_DEG, PASS_NODE_LOCATE_MAX_M, geometry_json, route_candidates, split_route

class FiberGisCablePass(models.Model):
    _inherit = "fiber.gis.cable"

    @api.model
    def _pass_node_points(self, points, tolerance_m, exclude_ids=()):
        """Elementos con coordenadas dentro del rectángulo de la ruta ampliado con la tolerancia."""
        margin = tolerance_m / 100000.0 + 0.0001
        latitudes = [point[0] for point in points]
        longitudes = [point[1] for point in points]
        nodes = self.env["fiber.gis.node"].search_read([
            ("latitude", ">=", min(latitudes) - margin),
            ("latitude", "<=", max(latitudes) + margin),
            ("longitude", ">=", min(longitudes) - margin),
            ("longitude", "<=", max(longitudes) + margin),
            ("id", "not in", list(exclude_ids)),
        ], ["latitude", "longitude"])
        return [(node["id"], node["latitude"], node["longitude"]) for node in nodes if node["latitude"] and node["longitude"]]

    @api.model
    def get_map_route_pass_candidates(self, from_node_id, to_node_id, via_points=None, tolerance_m=5.0):
        """Elementos sobre los que pasa un cable que se está dibujando en el mapa."""
        node_model = self.env["fiber.gis.node"]
        from_node = node_model.browse(int(from_node_id or 0)).exists()
        to_node = node_model.browse(int(to_node_id or 0)).exists()
        if not from_node or not to_node:
            return []
        points = self._map_route_points(from_node, to_node, via_points)
        tolerance_m = min(max(float(tolerance_m or 5.0), 0.5), 50.0)
        candidates = route_candidates(
            points, self._pass_node_points(points, tolerance_m, (from_node | to_node).ids), tolerance_m,
        )
        nodes = node_model.browse([item["key"] for item in candidates])
        names = {node.id: node.display_name for node in nodes}
        return [{"id": item["key"], "name": names[item["key"]], "distance_m": round(item["distance"], 1)} for item in candidates]

    @api.model
    def _map_route_points(self, from_node, to_node, via_points):
        """Vértices (lat, lon) de un trazado del mapa entre dos elementos, sin puntos inválidos o repetidos."""
        points = [(from_node.latitude, from_node.longitude)]
        for point in via_points or []:
            if not isinstance(point, (list, tuple)) or len(point) < 2:
                continue
            try:
                latitude, longitude = float(point[0]), float(point[1])
            except (TypeError, ValueError):
                continue
            if not (math.isfinite(latitude) and math.isfinite(longitude)):
                continue
            if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
                continue
            candidate = (round(latitude, 7), round(longitude, 7))
            previous = points[-1]
            if abs(previous[0] - candidate[0]) > 1e-7 or abs(previous[1] - candidate[1]) > 1e-7:
                points.append(candidate)
        points.append((to_node.latitude, to_node.longitude))
        return points

    @api.model
    def _locate_pass_nodes(self, points, pass_nodes, exclude_ids=()):
        """Sitúa sobre el recorrido los elementos de paso elegidos y los devuelve en orden de ruta."""
        node_points = [(node.id, node.latitude, node.longitude) for node in pass_nodes if node.id not in exclude_ids]
        located = route_candidates(points, node_points, PASS_NODE_LOCATE_MAX_M)
        missing = pass_nodes.filtered(lambda node: node.id not in {item["key"] for item in located})
        if missing:
            raise ValidationError(
                "Estos elementos no están sobre el recorrido del cable: " + ", ".join(missing.mapped("display_name"))
            )
        return located

    @api.model
    def _split_route_at(self, points, kinds, located):
        """Divide el recorrido en los elementos de paso y comprueba que cada tramo tenga longitud."""
        pieces = split_route(points, kinds, located)
        if any(len(piece_points) < 2 for piece_points, _kinds in pieces):
            raise ValidationError("Dos elementos de paso coinciden en el mismo punto del recorrido.")
        return pieces

    @api.model
    def _pass_bocas(self, node, count=2):
        """Bocas libres para que un cable entre y salga de un elemento de paso."""
        bocas = self.get_available_bocas(node.id)
        if len(bocas) < count:
            raise ValidationError(
                f"{node.display_name} no tiene {count} bocas libres para dejar el cable de paso. "
                "Amplía sus bocas en la ficha o no lo dejes de paso."
            )
        return bocas[:count]

    @api.model
    def _create_pass_through(self, incoming, outgoing, node):
        """Registra como sangría las fibras de igual número entre dos tramos en la primera bandeja.

        Si el elemento no tiene bandejas, se activa con una bandeja.
        """
        incoming.action_generate_fibers()
        outgoing.action_generate_fibers()
        if not node.tray_ids:
            node.write({"has_trays": True, "tray_count": max(node.tray_count or 0, 1)})
            node._ensure_trays_from_count()
        tray = node.tray_ids.sorted(lambda item: (item.sequence, item.id))[:1]
        result = {"node": node.display_name, "tray": tray.display_name}
        if (
            incoming.total_fiber_count != outgoing.total_fiber_count
            or incoming.tube_count != outgoing.tube_count
            or incoming.fiber_count != outgoing.fiber_count
        ):
            result["note"] = "Los tramos tienen distinta distribución de fibras; registra la sangría en Gestión de bandejas."
            return result
        input_by_number = {fiber.number: fiber for fiber in incoming.fiber_ids}
        output_by_number = {fiber.number: fiber for fiber in outgoing.fiber_ids}
        pairs = [(input_by_number[number], output_by_number[number])
                 for number in sorted(input_by_number.keys() & output_by_number.keys())]
        fibers = self.env["fiber.gis.cable.fiber"].browse([fiber.id for pair in pairs for fiber in pair])
        lines = self.env["fiber.gis.tray.line"].search([
            ("node_id", "=", node.id),
            "|", ("input_fiber_id", "in", fibers.ids), ("output_fiber_id", "in", fibers.ids),
        ])
        occupied = set(lines.mapped("input_fiber_id").ids + lines.mapped("output_fiber_id").ids)
        occupied.update(self.env["fiber.gis.splitter"].search([
            ("node_id", "=", node.id), ("input_fiber_id", "in", fibers.ids),
        ]).mapped("input_fiber_id").ids)
        occupied.update(self.env["fiber.gis.splitter.output"].search([
            ("splitter_id.node_id", "=", node.id), ("output_fiber_id", "in", fibers.ids),
        ]).mapped("output_fiber_id").ids)
        free_pairs = [pair for pair in pairs if pair[0].id not in occupied and pair[1].id not in occupied]
        if free_pairs:
            next_position = max(tray.line_ids.mapped("position") or [0]) + 1
            self.env["fiber.gis.tray.line"].create([{
                "tray_id": tray.id,
                "position": next_position + index,
                "line_type": "pass",
                "input_fiber_id": input_fiber.id,
                "output_fiber_id": output_fiber.id,
                "notes": "Cable de paso registrado automáticamente.",
            } for index, (input_fiber, output_fiber) in enumerate(free_pairs)])
        result.update(created=len(free_pairs), skipped=len(pairs) - len(free_pairs))
        return result

    def _split_at_pass_nodes(self, pass_nodes):
        """Parte un cable existente en los elementos de paso y registra la sangría en cada uno.

        El cable original se queda con el primer tramo. Las operaciones que tenía en su elemento de
        destino (bandejas, splitters, puertos y cabeceras) pasan a las fibras del último tramo.
        """
        self.ensure_one()
        cable = self
        points = [tuple(point) for point in cable._get_route_points()]
        kinds = cable._get_route_segment_kinds(len(points) - 1)
        end_nodes = cable.from_node_id | cable.to_node_id
        located = self._locate_pass_nodes(points, pass_nodes, end_nodes.ids)
        pieces = self._split_route_at(points, kinds, located)
        nodes = self.env["fiber.gis.node"].browse([item["key"] for item in located])
        self._lock_endpoint_nodes(end_nodes | nodes)
        bocas = {node.id: self._pass_bocas(node) for node in nodes}

        cable.action_generate_fibers()
        destination, destination_boca = cable.to_node_id, cable.to_boca
        original_fibers = cable.fiber_ids
        first_points, first_kinds = pieces[0]
        cable.write({
            "to_node_id": nodes[0].id,
            "to_boca": bocas[nodes[0].id][0],
            "geometry_geojson": geometry_json(first_points),
            "route_segment_kinds": json.dumps(first_kinds),
        })
        chain = cable
        stops = list(nodes) + [destination]
        for index, (piece_points, piece_kinds) in enumerate(pieces[1:], start=1):
            start, end = stops[index - 1], stops[index]
            chain |= self.create({
                "name": f"{cable.name or cable.code or 'Cable'} (tramo {index + 1})",
                "from_node_id": start.id,
                "from_boca": bocas[start.id][1],
                "to_node_id": end.id,
                "to_boca": destination_boca if end == destination else bocas[end.id][0],
                "profile_id": cable.profile_id.id,
                "tube_count": cable.tube_count,
                "fiber_count": cable.fiber_count,
                "type_id": cable.type_id.id,
                "color": cable.color,
                "state": cable.state,
                "deployment_plan_id": cable.deployment_plan_id.id,
                "route_kind": cable.route_kind,
                "route_segment_kinds": json.dumps(piece_kinds),
                "geometry_geojson": geometry_json(piece_points),
            })
        last = chain[-1]
        last.action_generate_fibers()
        self._move_endpoint_fibers(original_fibers, last, destination)
        for fiber in original_fibers.filtered(lambda item: item.state in ("reserved", "fault")):
            for piece in chain[1:]:
                piece.fiber_ids.filtered(lambda item: item.number == fiber.number).write({"state": fiber.state})
        links = self.env["fiber.gis.logical.link"].search([("fiber_ids", "in", original_fibers.ids)])
        for link in links:
            numbers = set(link.fiber_ids.filtered(lambda item: item.cable_id == cable).mapped("number"))
            added = chain[1:].mapped("fiber_ids").filtered(lambda item: item.number in numbers)
            link.write({"fiber_ids": [fields.Command.link(fiber.id) for fiber in added]})
        results = [
            self._create_pass_through(incoming, outgoing, incoming.to_node_id)
            for incoming, outgoing in zip(chain, chain[1:])
        ]
        return {"cable_ids": chain.ids, "pass_results": results}

    @api.model
    def _move_endpoint_fibers(self, original_fibers, new_cable, node):
        """Pasa a ``new_cable`` las operaciones de ``node`` que usaban fibras del cable original."""
        by_number = {fiber.number: fiber for fiber in new_cable.fiber_ids}
        mapping = {fiber.id: by_number[fiber.number].id for fiber in original_fibers if fiber.number in by_number}
        if not mapping:
            return
        ids = list(mapping)
        context = {"skip_fiber_gis_work_log": True}
        splitters = self.env["fiber.gis.splitter"].with_context(**context).search([
            ("node_id", "=", node.id), ("input_fiber_id", "in", ids),
        ])
        for splitter in splitters:
            splitter.write({"input_fiber_id": mapping[splitter.input_fiber_id.id]})
        lines = self.env["fiber.gis.tray.line"].with_context(**context).search([
            ("node_id", "=", node.id), "|", ("input_fiber_id", "in", ids), ("output_fiber_id", "in", ids),
        ])
        for line in lines:
            values = {}
            for field_name in ("input_fiber_id", "output_fiber_id"):
                if line[field_name].id in mapping:
                    values[field_name] = mapping[line[field_name].id]
            line.write(values)
        outputs = self.env["fiber.gis.splitter.output"].with_context(**context).search([
            ("splitter_id.node_id", "=", node.id), ("output_fiber_id", "in", ids),
        ])
        for output in outputs:
            output.write({"output_fiber_id": mapping[output.output_fiber_id.id]})
        for port in self.env["fiber.gis.port"].with_context(**context).search([
            ("node_id", "=", node.id), ("fiber_id", "in", ids),
        ]):
            port.write({"fiber_id": mapping[port.fiber_id.id]})
        for port in self.env["fiber.gis.cabinet.port"].search([
            ("cabinet_id.node_id", "=", node.id), ("fiber_id", "in", ids),
        ]):
            port.write({"fiber_id": mapping[port.fiber_id.id]})
        (original_fibers | new_cable.fiber_ids)._recompute_tray_state()

    @api.model
    def _find_cables_crossing_nodes(self, tolerance_m=3.0):
        """Busca cables activos cuyo recorrido pasa sobre un elemento que no es su origen ni su destino."""
        nodes = self.env["fiber.gis.node"].search_read(
            [("latitude", "!=", False), ("longitude", "!=", False)], ["latitude", "longitude"],
        )
        grid = {}
        for node in nodes:
            cell = (int(node["latitude"] / GRID_CELL_DEG), int(node["longitude"] / GRID_CELL_DEG))
            grid.setdefault(cell, []).append((node["id"], node["latitude"], node["longitude"]))
        margin_cells = int(tolerance_m / 100000.0 / GRID_CELL_DEG) + 1
        found = []
        for cable in self.search([("state", "!=", "retired")]):
            points = [tuple(point) for point in cable._get_route_points() if point[0] and point[1]]
            if len(points) < 2:
                continue
            nearby = {}
            for start, end in zip(points, points[1:]):
                lat_cells = sorted(int(value / GRID_CELL_DEG) for value in (start[0], end[0]))
                lon_cells = sorted(int(value / GRID_CELL_DEG) for value in (start[1], end[1]))
                for lat_cell in range(lat_cells[0] - margin_cells, lat_cells[1] + margin_cells + 1):
                    for lon_cell in range(lon_cells[0] - margin_cells, lon_cells[1] + margin_cells + 1):
                        for item in grid.get((lat_cell, lon_cell), ()):
                            nearby[item[0]] = item
            excluded = {cable.from_node_id.id, cable.to_node_id.id}
            node_points = [item for key, item in nearby.items() if key not in excluded]
            for candidate in route_candidates(points, node_points, tolerance_m):
                found.append({"cable_id": cable.id, "node_id": candidate["key"], "distance": candidate["distance"]})
        return found


class FiberGisCablePassReview(models.TransientModel):
    _name = "fiber.gis.cable.pass.review"
    _description = "Revisión de cables que atraviesan elementos"

    tolerance_m = fields.Float(
        string="Distancia máxima (m)", default=3.0, digits=(6, 1),
        help="Un elemento se considera atravesado si el recorrido del cable pasa a esta distancia o menos.",
    )
    filter_text = fields.Char(
        string="Filtrar por nombre",
        help="Muestra solo los cruces cuyo cable o elemento contiene este texto en el nombre o la matrícula.",
    )
    line_ids = fields.One2many("fiber.gis.cable.pass.review.line", "review_id", string="Cables que atraviesan elementos")
    searched = fields.Boolean(default=False)
    result_message = fields.Text(string="Resultado", readonly=True)

    def _reopen(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "name": "Revisar cables de paso",
        }

    def _check_manager(self):
        if not self.env.user.has_group("fiber_gis.group_fiber_gis_manager"):
            raise ValidationError("Solo los responsables de Fiber GIS pueden revisar el cableado.")

    def action_search(self):
        """Lista los cables cuyo recorrido pasa sobre un elemento."""
        self.ensure_one()
        self._check_manager()
        tolerance = min(max(self.tolerance_m or 3.0, 0.5), 50.0)
        found = self.env["fiber.gis.cable"]._find_cables_crossing_nodes(tolerance)
        text = (self.filter_text or "").strip().casefold()
        if text:
            cables = self.env["fiber.gis.cable"].browse(list({item["cable_id"] for item in found}))
            nodes = self.env["fiber.gis.node"].browse(list({item["node_id"] for item in found}))
            matching_cables = {cable.id for cable in cables if text in f"{cable.name or ''} {cable.code or ''}".casefold()}
            matching_nodes = {node.id for node in nodes if text in f"{node.name or ''} {node.code or ''}".casefold()}
            found = [item for item in found if item["cable_id"] in matching_cables or item["node_id"] in matching_nodes]
        self.line_ids.unlink()
        self.write({
            "searched": True,
            "line_ids": [fields.Command.create({
                "cable_id": item["cable_id"],
                "node_id": item["node_id"],
                "distance_m": round(item["distance"], 1),
            }) for item in found],
            "result_message": f"{len(found)} cruces encontrados." if found else "No hay cables que atraviesen elementos.",
        })
        return self._reopen()

    def action_apply(self):
        """Deja de paso los cables marcados en sus elementos y vuelve a buscar."""
        self.ensure_one()
        self._check_manager()
        selected = self.line_ids.filtered("leave_pass")
        if not selected:
            raise ValidationError("Marca «Dejar de paso» en al menos un cruce.")
        messages, errors = [], []
        for cable in selected.mapped("cable_id"):
            nodes = selected.filtered(lambda line: line.cable_id == cable).mapped("node_id")
            label = cable.display_name
            try:
                with self.env.cr.savepoint():
                    result = cable._split_at_pass_nodes(nodes)
            except (UserError, ValidationError) as error:
                errors.append(f"{label}: {error.args[0]}")
                continue
            for item in result["pass_results"]:
                if item.get("note"):
                    messages.append(f"{label} en {item['node']}: {item['note']}")
                else:
                    messages.append(f"{label} en {item['node']}: {item['created']} fibras de paso en {item['tray']}.")
        self.action_search()
        summary = "\n".join(messages + ["No aplicado: " + error for error in errors])
        self.result_message = summary or self.result_message
        return self._reopen()


class FiberGisCablePassReviewLine(models.TransientModel):
    _name = "fiber.gis.cable.pass.review.line"
    _description = "Cruce de cable con elemento"
    _order = "cable_id, distance_m"

    review_id = fields.Many2one("fiber.gis.cable.pass.review", required=True, ondelete="cascade")
    cable_id = fields.Many2one("fiber.gis.cable", string="Cable", required=True, ondelete="cascade")
    node_id = fields.Many2one("fiber.gis.node", string="Elemento atravesado", required=True, ondelete="cascade")
    distance_m = fields.Float(string="Distancia (m)", digits=(6, 1))
    leave_pass = fields.Boolean(string="Dejar de paso")
