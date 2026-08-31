"""Cables de fibra, geometr\u00eda GIS y tramos de instalaci\u00f3n."""

import json
import math

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class FiberGisCable(models.Model):
    _name = "fiber.gis.cable"
    _description = "Cable de fibra \u00f3ptica"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(string="Nombre", tracking=True, default="Cable")
    previous_name = fields.Char(string="Nombre anterior", readonly=True, copy=False)
    code = fields.Char(string="Matricula", tracking=True)
    profile_id = fields.Many2one("fiber.gis.cable.profile", string="Tipolog\u00eda", ondelete="restrict", tracking=True)
    installation_employee_ids = fields.Many2many(
        "hr.employee.public", "fiber_gis_cable_installer_rel", "cable_id", "employee_id",
        string="T\u00e9cnicos de instalaci\u00f3n", copy=False,
    )
    type_id = fields.Many2one(
        "fiber.gis.asset.type",
        domain=[("category", "=", "cable")],
        string="Tipo GIS",
    )
    deployment_plan_id = fields.Many2one(
        "fiber.gis.deployment.plan",
        string="Plan de despliegue",
        ondelete="set null",
        index=True,
        tracking=True,
    )
    color = fields.Char(string="Color", default="#0f766e", tracking=True)
    from_node_id = fields.Many2one("fiber.gis.node", required=True, string="Origen", tracking=True, ondelete="cascade")
    to_node_id = fields.Many2one("fiber.gis.node", required=True, string="Destino", tracking=True, ondelete="cascade")
    from_latitude = fields.Float(string="Latitud origen", related="from_node_id.latitude", store=True)
    from_longitude = fields.Float(string="Longitud origen", related="from_node_id.longitude", store=True)
    to_latitude = fields.Float(string="Latitud destino", related="to_node_id.latitude", store=True)
    to_longitude = fields.Float(string="Longitud destino", related="to_node_id.longitude", store=True)
    fiber_count = fields.Integer(
        string="Fibras",
        default=12,
        required=True,
        tracking=True,
        help="Si el cable no tiene tubos, indica el total de fibras. Si tiene tubos, indica las fibras por tubo.",
    )
    tube_count = fields.Integer(
        string="N.\u00ba de tubos",
        default=0,
        help="Usa 0 para cables sin tubos. Si hay tubos, las fibras se reparten entre ellos y cada tubo toma el color estandar de su posicion.",
    )
    fibers_per_tube = fields.Integer(
        string="Fibras por tubo",
        compute="_compute_fibers_per_tube",
        store=True,
        readonly=True,
    )
    total_fiber_count = fields.Integer(
        string="Total fibras",
        compute="_compute_total_fiber_count",
        store=True,
        readonly=True,
    )
    topology = fields.Char(string="Tipologia", compute="_compute_topology", store=True)
    route_kind = fields.Selection(
        [
            ("facade", "Fachada"),
            ("aerial", "A\u00e9reo"),
            ("underground", "Subterr\u00e1neo"),
        ],
        string="Trazado",
        default="underground",
        required=True,
        tracking=True,
    )
    state = fields.Selection(
        [
            ("planned", "Planificado"),
            ("installed", "Instalado"),
            ("active", "Activo"),
            ("fault", "Incidencia"),
            ("retired", "Retirado"),
        ],
        default="planned",
        required=True,
        tracking=True,
    )
    install_date = fields.Date(string="Fecha de instalaci\u00f3n")
    length_m = fields.Float(string="Longitud estimada (m)", compute="_compute_length_m", store=True)
    measured_length_m = fields.Float(string="Longitud medida (m)")
    geometry_geojson = fields.Text(
        string="Geometr\u00eda GeoJSON",
        help="LineString GeoJSON con coordenadas [longitud, latitud]. Si est\u00e1 vac\u00edo se dibuja una l\u00ednea directa.",
    )
    route_segment_kinds = fields.Text(
        string="Trazados por tramo",
        help="Lista JSON con el tipo de trazado de cada tramo del cable.",
    )
    segment_ids = fields.One2many("fiber.gis.cable.segment", "cable_id", string="Tramos")
    fiber_ids = fields.One2many("fiber.gis.cable.fiber", "cable_id", string="Fibras")
    notes = fields.Text(string="Notas")
    active = fields.Boolean(string="Activo", default=True)
    _fiber_count_positive = models.Constraint(
        "CHECK(fiber_count > 0)",
        "El cable debe tener al menos una fibra.",
    )
    _tube_count_not_negative = models.Constraint(
        "CHECK(tube_count >= 0)",
        "El numero de tubos no puede ser negativo.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._prepare_profile_values(dict(values), choose_profile=True) for values in vals_list]
        employee_id = self.env.context.get("fiber_gis_employee_id")
        if employee_id:
            for values in vals_list:
                values.setdefault("installation_employee_ids", [fields.Command.link(employee_id)])
        cables = super().create(vals_list)
        cables._sync_route_segments()
        cables.action_generate_fibers()
        return cables

    @api.model
    def _prepare_profile_values(self, values, choose_profile=False):
        profile = self.env["fiber.gis.cable.profile"]
        if values.get("profile_id"):
            profile = profile.browse(values["profile_id"]).exists()
            if not profile:
                raise ValidationError("La tipologia seleccionada ya no existe.")
        elif choose_profile and "profile_id" not in values:
            profile = profile.search([
                ("tube_count", "=", values.get("tube_count", 0)),
                ("fiber_count", "=", values.get("fiber_count", 12)),
            ], limit=1)
        if profile:
            values.update(profile_id=profile.id, tube_count=profile.tube_count, fiber_count=profile.fiber_count)
        return values

    @api.onchange("profile_id")
    def _onchange_profile_id(self):
        for cable in self:
            if cable.profile_id:
                cable.tube_count = cable.profile_id.tube_count
                cable.fiber_count = cable.profile_id.fiber_count

    @api.model
    def create_from_map(
        self,
        from_node_id,
        to_node_id,
        via_points=None,
        deployment_plan_id=False,
        route_kind="underground",
        cable_type_id=False,
    ):
        """Create a cable from the interactive map drawing tool."""
        from_node = self.env["fiber.gis.node"].browse(int(from_node_id or 0)).exists()
        to_node = self.env["fiber.gis.node"].browse(int(to_node_id or 0)).exists()
        if not from_node or not to_node:
            raise ValidationError("Selecciona dos elementos de red v\u00e1lidos.")
        if from_node == to_node:
            raise ValidationError("El origen y el destino deben ser elementos distintos.")
        if not from_node.latitude or not from_node.longitude:
            raise ValidationError("El elemento de origen no tiene coordenadas.")
        if not to_node.latitude or not to_node.longitude:
            raise ValidationError("El elemento de destino no tiene coordenadas.")

        valid_route_kinds = {"facade", "aerial", "underground"}
        if route_kind not in valid_route_kinds:
            route_kind = "underground"

        cable_type = self._map_cable_type(cable_type_id)

        plan = self.env["fiber.gis.deployment.plan"]
        if deployment_plan_id:
            plan = plan.browse(int(deployment_plan_id)).exists()
            if not plan:
                raise ValidationError("El plan de despliegue ya no existe.")

        points = [[from_node.latitude, from_node.longitude]]
        for point in via_points or []:
            if not isinstance(point, (list, tuple)) or len(point) < 2:
                continue
            try:
                latitude = float(point[0])
                longitude = float(point[1])
            except (TypeError, ValueError):
                continue
            if not math.isfinite(latitude) or not math.isfinite(longitude):
                continue
            if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
                continue
            candidate = [round(latitude, 7), round(longitude, 7)]
            previous = points[-1]
            if abs(previous[0] - candidate[0]) > 1e-7 or abs(previous[1] - candidate[1]) > 1e-7:
                points.append(candidate)
        points.append([to_node.latitude, to_node.longitude])

        geometry = {
            "type": "LineString",
            "coordinates": [[round(point[1], 7), round(point[0], 7)] for point in points],
        }
        values = {
            "from_node_id": from_node.id,
            "to_node_id": to_node.id,
            "type_id": cable_type.id,
            "route_kind": route_kind,
            "route_segment_kinds": json.dumps([route_kind] * (len(points) - 1)),
            "geometry_geojson": json.dumps(geometry),
            "state": "planned",
        }
        if plan:
            values["deployment_plan_id"] = plan.id
        cable = self.create(values)
        return {
            "id": cable.id,
            "name": cable.display_name,
            "length_m": cable.length_m,
            "deployment_plan_id": cable.deployment_plan_id.id or False,
            "type_id": cable.type_id.id,
        }

    @api.model
    def _map_cable_type(self, cable_type_id=False):
        """Return a valid cable type for an interactive map creation."""
        type_model = self.env["fiber.gis.asset.type"]
        cable_type = type_model
        if cable_type_id:
            cable_type = type_model.browse(int(cable_type_id)).exists()
            if not cable_type or cable_type.category != "cable":
                raise ValidationError("Selecciona un tipo GIS v\u00e1lido para el cable.")
            return cable_type
        cable_type = type_model.search([
            ("category", "=", "cable"),
            ("code", "=", "CABLE_DISTRIBUTION"),
            ("active", "=", True),
        ], limit=1)
        if not cable_type:
            cable_type = type_model.search([
                ("category", "=", "cable"),
                ("active", "=", True),
            ], order="sequence, id", limit=1)
        if not cable_type:
            raise ValidationError("No hay ning\u00fan tipo GIS de cable activo configurado.")
        return cable_type

    def write(self, vals):
        vals = self._prepare_profile_values(dict(vals))
        if (
            "route_kind" in vals
            and "route_segment_kinds" not in vals
            and not self.env.context.get("skip_segment_sync")
        ):
            # Changing the main route kind in the form applies it to every segment.
            vals["route_segment_kinds"] = False
        result = super().write(vals)
        sync_fields = {
            "from_node_id",
            "to_node_id",
            "route_kind",
            "geometry_geojson",
            "route_segment_kinds",
        }
        if not self.env.context.get("skip_segment_sync") and sync_fields.intersection(vals):
            self._sync_route_segments()
        if {"fiber_count", "tube_count"}.intersection(vals):
            self._sync_fiber_topology()
        return result

    @api.depends("fiber_count", "tube_count")
    def _compute_fibers_per_tube(self):
        for cable in self:
            cable.fibers_per_tube = cable.fiber_count if cable.tube_count else 0

    @api.depends("fiber_count", "tube_count")
    def _compute_total_fiber_count(self):
        for cable in self:
            cable.total_fiber_count = cable.fiber_count * cable.tube_count if cable.tube_count else cable.fiber_count

    @api.depends("fiber_count", "tube_count", "fibers_per_tube", "total_fiber_count")
    def _compute_topology(self):
        for cable in self:
            if cable.tube_count:
                cable.topology = f"{cable.total_fiber_count} fibras / {cable.tube_count} tubos x {cable.fibers_per_tube} fibras por tubo"
            else:
                cable.topology = f"{cable.fiber_count} fibras sin tubos"

    @api.depends(
        "from_latitude",
        "from_longitude",
        "to_latitude",
        "to_longitude",
        "measured_length_m",
        "geometry_geojson",
    )
    def _compute_length_m(self):
        for cable in self:
            if cable.measured_length_m:
                cable.length_m = cable.measured_length_m
                continue
            points = cable._get_geometry_points()
            if len(points) < 2:
                points = [
                    (cable.from_latitude, cable.from_longitude),
                    (cable.to_latitude, cable.to_longitude),
                ]
            cable.length_m = cable._polyline_length(points)

    def _get_geometry_points(self):
        self.ensure_one()
        if not self.geometry_geojson:
            return []
        try:
            geometry = json.loads(self.geometry_geojson)
        except ValueError:
            return []
        if geometry.get("type") != "LineString":
            return []
        points = []
        for coord in geometry.get("coordinates", []):
            if len(coord) >= 2:
                points.append((float(coord[1]), float(coord[0])))
        return points

    def _get_route_points(self):
        self.ensure_one()
        points = self._get_geometry_points()
        if len(points) >= 2:
            return points
        return [
            (self.from_latitude, self.from_longitude),
            (self.to_latitude, self.to_longitude),
        ]

    def _get_route_segment_kinds(self, segment_count):
        self.ensure_one()
        kinds = []
        if self.route_segment_kinds:
            try:
                parsed = json.loads(self.route_segment_kinds)
                kinds = parsed if isinstance(parsed, list) else []
            except ValueError:
                kinds = []
        fallback = self.route_kind or "underground"
        return [kinds[index] if index < len(kinds) and kinds[index] else fallback for index in range(segment_count)]

    def _route_point_label(self, point_index, point_count):
        self.ensure_one()
        if point_index == 0:
            return self.from_node_id.display_name or "Origen"
        if point_index == point_count - 1:
            return self.to_node_id.display_name or "Destino"
        return f"Punto {point_index}"

    def _sync_route_segments(self):
        segment_model = self.env["fiber.gis.cable.segment"]
        for cable in self:
            points = [point for point in cable._get_route_points() if all(point)]
            segment_count = max(len(points) - 1, 0)
            kinds = cable._get_route_segment_kinds(segment_count)
            existing_by_sequence = {segment.sequence: segment for segment in cable.segment_ids}
            for index in range(segment_count):
                sequence = index + 1
                start = points[index]
                end = points[index + 1]
                values = {
                    "name": f"Tramo {sequence}",
                    "sequence": sequence,
                    "from_label": cable._route_point_label(index, len(points)),
                    "to_label": cable._route_point_label(index + 1, len(points)),
                    "route_kind": kinds[index],
                    "length_m": cable._haversine_m(start[0], start[1], end[0], end[1]),
                }
                if sequence in existing_by_sequence:
                    existing_by_sequence[sequence].with_context(skip_cable_segment_json=True).write(values)
                else:
                    values["cable_id"] = cable.id
                    segment_model.with_context(skip_cable_segment_json=True).create(values)
            obsolete_segments = cable.segment_ids.filtered(lambda segment: segment.sequence > segment_count)
            obsolete_segments.with_context(skip_cable_segment_json=True).unlink()
            canonical_kinds = json.dumps(kinds) if kinds else False
            if cable.route_segment_kinds != canonical_kinds:
                cable.with_context(skip_segment_sync=True).write({"route_segment_kinds": canonical_kinds})

    @api.model
    def _polyline_length(self, points):
        total = 0.0
        for start, end in zip(points, points[1:]):
            total += self._haversine_m(start[0], start[1], end[0], end[1])
        return total

    @api.model
    def _haversine_m(self, lat1, lon1, lat2, lon2):
        if not all([lat1, lon1, lat2, lon2]):
            return 0.0
        radius = 6371000
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        d_phi = math.radians(lat2 - lat1)
        d_lambda = math.radians(lon2 - lon1)
        a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
        return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def action_generate_fibers(self):
        self._check_fiber_topology()
        for cable in self:
            existing_numbers = set(cable.fiber_ids.mapped("number"))
            values = []
            for number in range(1, cable.total_fiber_count + 1):
                tube = cable._tube_for_fiber(number)
                color_index = cable._fiber_color_index(number)
                if number not in existing_numbers:
                    values.append(
                        {
                            "name": f"{cable.code or cable.name or 'Cable'}-{number:02d}",
                            "number": number,
                            "cable_id": cable.id,
                            "tube": tube,
                            "color": self.env["fiber.gis.cable.fiber"].fiber_color(color_index),
                            "tube_color": self.env["fiber.gis.cable.fiber"].fiber_color(tube) if tube else False,
                            "state": "free",
                        }
                    )
                else:
                    fiber = cable.fiber_ids.filtered(lambda item: item.number == number)[:1]
                    fiber.write({
                        "tube": tube,
                        "color": self.env["fiber.gis.cable.fiber"].fiber_color(color_index),
                        "tube_color": self.env["fiber.gis.cable.fiber"].fiber_color(tube) if tube else False,
                    })
            if values:
                self.env["fiber.gis.cable.fiber"].create(values)
        return True

    def _sync_fiber_topology(self):
        for cable in self:
            cable.action_generate_fibers()

    def _tube_for_fiber(self, number):
        self.ensure_one()
        if not self.tube_count:
            return 0
        return int((number - 1) / max(self.fibers_per_tube, 1)) + 1

    def _fiber_color_index(self, number):
        self.ensure_one()
        if not self.tube_count:
            return number
        return ((number - 1) % max(self.fibers_per_tube, 1)) + 1

    def _check_fiber_topology(self):
        for cable in self:
            total = cable.fiber_count * (cable.tube_count or 1)
            if cable.fiber_ids.filtered(lambda fiber: fiber.number > total):
                raise ValidationError(
                    "No se puede reducir la tipologia: el cable contiene fibras fuera del nuevo total. "
                    "No se han borrado fibras ni conexiones."
                )
            if cable.profile_id and (cable.fiber_count != cable.profile_id.fiber_count or cable.tube_count != cable.profile_id.tube_count):
                raise ValidationError("Los tubos y fibras deben coincidir con la tipologia seleccionada.")
        return True

    def action_sync_route_segments(self):
        self._sync_route_segments()
        return True

    def action_open_tray_wizard(self):
        self.ensure_one()
        self.action_generate_fibers()
        return {
            "type": "ir.actions.act_window",
            "name": "Registrar cable en bandeja",
            "res_model": "fiber.gis.cable.tray.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_cable_id": self.id,
                "default_node_id": self.from_node_id.id,
                "default_from_fiber": 1,
                "default_to_fiber": self.total_fiber_count,
            },
        }

    def action_set_planned(self):
        self.write({"state": "planned"})

    def action_open_map(self):
        self.ensure_one()
        params = {
            "target_cable_id": self.id,
        }
        if self.deployment_plan_id:
            params["deployment_plan_id"] = self.deployment_plan_id.id
        return {
            "type": "ir.actions.client",
            "tag": "fiber_gis.map_action",
            "name": "Mapa de Fibra",
            "params": params,
        }

    def action_set_installed(self):
        self.write({"state": "installed"})

    def action_set_active(self):
        self.write({"state": "active"})

    def action_set_fault(self):
        self.write({"state": "fault"})

    def action_set_retired(self):
        self.write({"state": "retired"})

    @api.constrains("geometry_geojson")
    def _check_geometry_geojson(self):
        for cable in self:
            if not cable.geometry_geojson:
                continue
            try:
                geometry = json.loads(cable.geometry_geojson)
            except ValueError as error:
                raise ValidationError("La geometr\u00eda GeoJSON no es JSON v\u00e1lido.") from error
            if geometry.get("type") != "LineString":
                raise ValidationError("La geometr\u00eda debe ser un GeoJSON LineString.")

    @api.constrains("fiber_count", "tube_count", "profile_id")
    def _check_counts(self):
        self._check_fiber_topology()

    @api.constrains("route_segment_kinds")
    def _check_route_segment_kinds(self):
        valid_kinds = {"facade", "aerial", "underground"}
        for cable in self:
            if not cable.route_segment_kinds:
                continue
            try:
                segment_kinds = json.loads(cable.route_segment_kinds)
            except ValueError as error:
                raise ValidationError("Los trazados por tramo no son JSON v\u00e1lido.") from error
            if not isinstance(segment_kinds, list) or any(kind not in valid_kinds for kind in segment_kinds):
                raise ValidationError("Los trazados por tramo deben ser fachada, a\u00e9reo o subterr\u00e1neo.")


class FiberGisCableSegment(models.Model):
    _name = "fiber.gis.cable.segment"
    _description = "Tramo de cable de fibra"
    _order = "cable_id, sequence"

    name = fields.Char(string="Tramo", required=True)
    cable_id = fields.Many2one("fiber.gis.cable", required=True, ondelete="cascade", string="Cable")
    sequence = fields.Integer(string="Secuencia", required=True, default=1)
    from_label = fields.Char(string="Desde", readonly=True)
    to_label = fields.Char(string="Hasta", readonly=True)
    route_kind = fields.Selection(
        [
            ("facade", "Fachada"),
            ("aerial", "A\u00e9reo"),
            ("underground", "Subterr\u00e1neo"),
        ],
        string="Instalaci\u00f3n",
        default="underground",
        required=True,
    )
    length_m = fields.Float(string="Longitud estimada (m)", readonly=True)

    _segment_sequence_unique = models.Constraint(
        "UNIQUE(cable_id, sequence)",
        "La secuencia del tramo debe ser \u00fanica por cable.",
    )

    def write(self, vals):
        result = super().write(vals)
        if "route_kind" in vals and not self.env.context.get("skip_cable_segment_json"):
            self.mapped("cable_id")._update_route_segment_kinds_from_segments()
        return result


    @api.model_create_multi
    def create(self, vals_list):
        segments = super().create(vals_list)
        if not self.env.context.get("skip_cable_segment_json"):
            segments.mapped("cable_id")._update_route_segment_kinds_from_segments()
        return segments

    def unlink(self):
        cables = self.mapped("cable_id")
        result = super().unlink()
        if not self.env.context.get("skip_cable_segment_json"):
            cables._sync_route_segments()
        return result


def _update_route_segment_kinds_from_segments(self):
    for cable in self:
        kinds = [segment.route_kind for segment in cable.segment_ids.sorted("sequence")]
        cable.with_context(skip_segment_sync=True).write({
            "route_segment_kinds": json.dumps(kinds) if kinds else False,
        })


FiberGisCable._update_route_segment_kinds_from_segments = _update_route_segment_kinds_from_segments
