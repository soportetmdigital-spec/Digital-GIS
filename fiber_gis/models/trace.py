"""Trazado de fibras para diagnostico, mapa resaltado e informe PDF."""

import html

from markupsafe import Markup
from odoo import api, fields, models
from odoo.exceptions import UserError

from .map_geometry import (
    catastro_wms_png_data_uri,
    fit_bbox_to_aspect,
    latlon_to_web_mercator,
    project_map_point,
)


class FiberGisTraceWizard(models.TransientModel):
    _name = "fiber.gis.trace.wizard"
    _description = "Trazar recorrido de una fibra"

    node_id = fields.Many2one("fiber.gis.node", string="Elemento origen", required=True)
    fiber_id = fields.Many2one("fiber.gis.cable.fiber", string="Fibra a comprobar", required=True)
    result_html = fields.Html(string="Recorrido", readonly=True, sanitize=False)

    def action_trace(self):
        """Ejecuta la acción de usuario «trazado» y devuelve el resultado correspondiente a Odoo."""
        self.ensure_one()
        if self.fiber_id.cable_id.from_node_id != self.node_id and self.fiber_id.cable_id.to_node_id != self.node_id:
            raise UserError("La fibra seleccionada no pertenece a un cable conectado al elemento origen.")
        self.result_html = self._build_trace_html()
        return {
            "type": "ir.actions.act_window",
            "name": "Trazar fibra",
            "res_model": "fiber.gis.trace.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_open_trace_map(self):
        """Ejecuta la acción de usuario «apertura trazado mapa» y devuelve el resultado correspondiente a Odoo."""
        self.ensure_one()
        if not self.result_html:
            self.result_html = self._build_trace_html()
        return {
            "type": "ir.actions.client",
            "tag": "fiber_gis.map_action",
            "name": "Mapa de trazado de fibra",
            "params": {
                "trace_node_id": self.node_id.id,
                "trace_fiber_id": self.fiber_id.id,
            },
        }

    def action_print_pdf(self):
        """Genera y descarga el informe PDF correspondiente."""
        self.ensure_one()
        if not self.result_html:
            self.result_html = self._build_trace_html()
        return self.env.ref("fiber_gis.action_report_fiber_trace").report_action(self)

    @api.model
    def get_trace_map_data(self, node_id, fiber_id):
        """Prepara los datos geográficos que necesita el mapa del recorrido de una fibra."""
        wizard = self.create({
            "node_id": node_id,
            "fiber_id": fiber_id,
        })
        return wizard._get_trace_data()

    @api.model
    def action_print_trace_pdf(self, wizard_id):
        """Genera el informe PDF con el recorrido de la fibra."""
        wizard = self.browse(wizard_id).exists()
        if not wizard:
            raise UserError("No se ha encontrado el trazado para imprimir.")
        return wizard.action_print_pdf()

    def _build_trace_html(self):
        """Construye «trazado HTML» con los datos del modelo para mostrarlo o imprimirlo."""
        data = self._get_trace_data()
        if not data["rows"]:
            return "<p>No hay recorrido para mostrar.</p>"
        return "<div class='o_fiber_trace_diagram'>" + "".join(self._trace_row(row) for row in data["rows"]) + "</div>"

    def _get_trace_data(self):
        """Obtiene «trazado datos» aplicando las reglas y relaciones propias del modelo."""
        rows = []
        cable_ids = []
        node_ids = []
        visited = set()
        max_steps = 80
        pending = [(self.node_id, self.fiber_id)]
        steps = 0

        while pending and steps < max_steps:
            current_node, current_fiber = pending.pop(0)
            steps += 1
            key = (current_node.id, current_fiber.id)
            if key in visited:
                rows.append(self._trace_row_values(
                    len(rows) + 1,
                    current_node,
                    current_fiber,
                    "Bucle detectado. Revisa las bandejas.",
                ))
                continue
            visited.add(key)
            cable = current_fiber.cable_id
            if current_node.id not in node_ids:
                node_ids.append(current_node.id)
            if cable.id not in cable_ids:
                cable_ids.append(cable.id)
            if cable.from_node_id != current_node and cable.to_node_id != current_node:
                rows.append(
                    self._trace_row_values(
                        len(rows) + 1,
                        current_node,
                        current_fiber,
                        "El cable de esta fibra no esta conectado a este elemento. Revisa los extremos del cable o la bandeja.",
                    )
                )
                continue
            other_node = cable.to_node_id if cable.from_node_id == current_node else cable.from_node_id
            if other_node.id not in node_ids:
                node_ids.append(other_node.id)
            rows.append(self._trace_row_values(
                len(rows) + 1,
                current_node,
                current_fiber,
                f"Cable hasta {other_node.display_name or ''}",
            ))

            connections, stop_detail = self._trace_connections(other_node, current_fiber)
            if not connections:
                terminal_line = self.env["fiber.gis.tray.line"].search(
                    [
                        ("node_id", "=", other_node.id),
                        ("line_type", "in", ("free", "pending_cancel")),
                        "|",
                        ("input_fiber_id", "=", current_fiber.id),
                        ("output_fiber_id", "=", current_fiber.id),
                    ],
                    limit=1,
                )
                detail = stop_detail or (
                    (
                        "Fin del recorrido: fibra pendiente de anular."
                        if terminal_line.line_type == "pending_cancel"
                        else "Fin del recorrido: fibra en punta en bandeja."
                    )
                    if terminal_line
                    else "Fin del recorrido: no hay conexion registrada en bandeja."
                )
                rows.append(self._trace_row_values(
                    len(rows) + 1,
                    other_node,
                    current_fiber,
                    detail,
                ))
                continue

            for next_fiber, connection_detail in connections:
                rows.append(self._trace_row_values(
                    len(rows) + 1,
                    other_node,
                    next_fiber,
                    connection_detail,
                ))
                pending.append((other_node, next_fiber))

        if pending:
            current_node, current_fiber = pending[0]
            rows.append({
                "sequence": len(rows) + 1,
                "node_id": current_node.id,
                "node_name": current_node.display_name or "",
                "cable_id": current_fiber.cable_id.id,
                "cable_name": current_fiber.cable_id.display_name or "",
                "fiber_id": current_fiber.id,
                "fiber_number": current_fiber.number,
                "fiber_color": current_fiber.color or "#d1d5db",
                "detail": "Recorrido detenido por seguridad: demasiados saltos.",
            })
        return {
            "title": f"Trazado de fibra {self.fiber_id.number} - {self.fiber_id.cable_id.display_name or ''}",
            "wizard_id": self.id,
            "origin": self.node_id.display_name or "",
            "fiber": self.fiber_id.display_name or "",
            "fiber_color": self.fiber_id.color or "#d1d5db",
            "cable_ids": cable_ids,
            "node_ids": node_ids,
            "rows": rows,
        }

    def _trace_connections(self, node, fiber):
        """Devuelve la continuidad aguas arriba de una fibra en el elemento."""
        tray_line = self.env["fiber.gis.tray.line"].search(
            [
                ("node_id", "=", node.id),
                ("line_type", "in", ("fusion", "pass")),
                "|",
                ("input_fiber_id", "=", fiber.id),
                ("output_fiber_id", "=", fiber.id),
            ],
            limit=1,
        )
        if tray_line:
            next_fiber = (
                tray_line.output_fiber_id
                if tray_line.input_fiber_id == fiber
                else tray_line.input_fiber_id
            )
            if next_fiber:
                return [(
                    next_fiber,
                    (
                        f"Continuidad de paso en {tray_line.tray_id.display_name or ''}: "
                        f"continúa a fibra {next_fiber.number} de {next_fiber.cable_id.display_name}"
                        if tray_line.line_type == "pass"
                        else f"Fusión en {tray_line.tray_id.display_name or ''}: pasa a fibra {next_fiber.number}"
                    ),
                )], False

        splitter_outputs = self.env["fiber.gis.splitter.output"].search([
            ("splitter_id.node_id", "=", node.id),
            ("output_fiber_id", "=", fiber.id),
            ("splitter_id.active", "=", True),
        ], limit=1)
        if splitter_outputs:
            input_fiber, splitter_path = splitter_outputs.splitter_id._upstream_fiber()
            if input_fiber:
                return [(
                    input_fiber,
                    f"Salida {splitter_outputs.sequence} de {' -> '.join(splitter_path)}: "
                    "continua hacia el origen por la "
                    f"fibra de entrada {input_fiber.number} de "
                    f"{input_fiber.cable_id.display_name}",
                )], False
            return [], (
                f"Fin del recorrido: {splitter_outputs.splitter_id.display_name} "
                "no tiene fibra de entrada."
            )

        input_splitter = self.env["fiber.gis.splitter"].search([
            ("node_id", "=", node.id),
            ("input_fiber_id", "=", fiber.id),
            ("active", "=", True),
        ], limit=1)
        if input_splitter:
            return [], (
                f"Fin del recorrido aguas arriba: fibra de entrada de "
                f"{input_splitter.display_name}."
            )

        return [], False

    def _trace_row_values(self, sequence, node, fiber, detail):
        """Recorre o representa «fila valores» para mantener la continuidad del trazado de fibra."""
        return {
            "sequence": sequence,
            "node_id": node.id,
            "node_name": node.display_name or "",
            "cable_id": fiber.cable_id.id,
            "cable_name": fiber.cable_id.display_name or "",
            "fiber_id": fiber.id,
            "fiber_number": fiber.number,
            "fiber_color": fiber.color or "#d1d5db",
            "detail": detail or "",
        }

    def _trace_row(self, row):
        """Recorre o representa «fila» para mantener la continuidad del trazado de fibra."""
        color = row.get("fiber_color") or "#d1d5db"
        node_name = html.escape(row.get("node_name") or "")
        cable_name = html.escape(row.get("cable_name") or "")
        detail_text = html.escape(row.get("detail") or "")
        sequence = row.get("sequence") or ""
        fiber_number = row.get("fiber_number") or ""
        return (
            "<div class='o_fiber_trace_row'>"
            f"<span class='o_fiber_trace_step'>{sequence}</span>"
            f"<span class='o_fiber_trace_chip' style='background:{color}'></span>"
            f"<span><strong>{node_name}</strong><br/>{cable_name} \u00b7 Fibra {fiber_number}</span>"
            f"<span>{detail_text}</span>"
            "</div>"
        )

    def _get_trace_map_svg(self):
        """Obtiene «trazado mapa SVG» aplicando las reglas y relaciones propias del modelo."""
        self.ensure_one()
        data = self._get_trace_data()
        cables = self.env["fiber.gis.cable"].browse(data["cable_ids"]).exists()
        nodes = self.env["fiber.gis.node"].browse(data["node_ids"]).exists()
        points = []
        cable_points = []
        for cable in cables:
            route = self._trace_cable_points(cable)
            if len(route) >= 2:
                cable_points.append((cable, route))
                points.extend(route)
        for node in nodes:
            if node.latitude and node.longitude:
                points.append((node.latitude, node.longitude))
        if not points:
            return Markup("<p>No hay coordenadas suficientes para dibujar el plano.</p>")

        width = 900
        height = 390
        image_width = 1800
        image_height = 780

        mercator_points = [latlon_to_web_mercator(lat, lon) for lat, lon in points]
        min_x = min(point[0] for point in mercator_points)
        max_x = max(point[0] for point in mercator_points)
        min_y = min(point[1] for point in mercator_points)
        max_y = max(point[1] for point in mercator_points)
        x_pad = max((max_x - min_x) * 0.08, 45)
        y_pad = max((max_y - min_y) * 0.08, 45)
        min_x -= x_pad
        max_x += x_pad
        min_y -= y_pad
        max_y += y_pad
        min_x, min_y, max_x, max_y = fit_bbox_to_aspect(
            min_x, min_y, max_x, max_y, width / height
        )

        catastro_image = self._trace_catastro_image(min_x, min_y, max_x, max_y, image_width, image_height)
        trace_paths = []
        for cable, route in cable_points:
            coords = [
                project_map_point(lat, lon, min_x, min_y, max_x, max_y, width, height)
                for lat, lon in route
            ]
            path = " ".join(f"{'M' if index == 0 else 'L'} {x} {y}" for index, (x, y) in enumerate(coords))
            trace_paths.append(f"<path d='{path}' class='trace-route'><title>{html.escape(cable.display_name or '')}</title></path>")

        node_marks = []
        for index, node in enumerate(nodes, start=1):
            if not node.latitude or not node.longitude:
                continue
            x, y = project_map_point(
                node.latitude, node.longitude, min_x, min_y, max_x, max_y, width, height
            )
            label = html.escape(node.display_name or "")
            node_marks.append(
                f"<circle cx='{x}' cy='{y}' r='5' class='trace-node'/>"
                f"<text x='{x + 7}' y='{y - 7}' class='trace-node-label'>{index}. {label}</text>"
            )

        route_shadows = [path.replace("class='trace-route'", "class='trace-route-shadow'") for path in trace_paths]
        svg = (
            "<style>"
            ".trace-map-wrap{position:relative;width:100%;border:1px solid #475569;background:#ffffff;line-height:0;overflow:hidden}"
            ".trace-map-base{display:block;width:100%;height:auto}"
            ".trace-map-overlay{position:absolute;left:0;top:0;width:100%;height:100%}"
            ".trace-route-shadow{fill:none;stroke:#ffffff;stroke-width:9;stroke-linecap:round;stroke-linejoin:round;stroke-opacity:.90}"
            ".trace-route{fill:none;stroke:#e11d48;stroke-width:4.5;stroke-linecap:round;stroke-linejoin:round;stroke-opacity:.98}"
            ".trace-node{fill:#ffffff;stroke:#0f172a;stroke-width:2}"
            ".trace-node-label{font-size:8px;font-weight:700;fill:#0f172a;paint-order:stroke;stroke:#fff;stroke-width:3px}"
            ".trace-map-note{padding:18px 20px;color:#334155;font-size:12px;line-height:1.35}"
            "</style>"
            "<div class='trace-map-wrap'>"
            f"{catastro_image}"
            f"<svg class='trace-map-overlay' viewBox='0 0 {width} {height}' xmlns='http://www.w3.org/2000/svg'>"
            f"{''.join(route_shadows)}"
            f"{''.join(trace_paths)}"
            f"{''.join(node_marks)}"
            "</svg>"
            "</div>"
        )
        return Markup(svg)

    def _trace_cable_points(self, cable):
        """Recorre o representa «cable puntos» para mantener la continuidad del trazado de fibra."""
        cable.ensure_one()
        points = []
        if cable.from_node_id.latitude and cable.from_node_id.longitude:
            points.append((cable.from_node_id.latitude, cable.from_node_id.longitude))
        manual_points = cable._get_geometry_points()
        if len(manual_points) > 2:
            points.extend(manual_points[1:-1])
        if cable.to_node_id.latitude and cable.to_node_id.longitude:
            points.append((cable.to_node_id.latitude, cable.to_node_id.longitude))
        return points

    def _trace_catastro_image(self, min_x, min_y, max_x, max_y, width, height):
        """Solicita la cartografía catastral para el área del trazado y prepara la imagen del informe."""
        image_uri = catastro_wms_png_data_uri(
            min_x, min_y, max_x, max_y, width, height,
            "Odoo Fiber GIS trace report", timeout=20,
        )
        if not image_uri:
            return (
                f"<div class='trace-map-note' style='height:{height}px;background:#f8fafc;'>"
                "No se ha podido cargar Catastro para este plano."
                "</div>"
            )
        return f"<img class='trace-map-base' src='{image_uri}' alt='Plano del Catastro'/>"
