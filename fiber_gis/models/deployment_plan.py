"""Planificaci\u00f3n previa de despliegues de fibra y documentaci\u00f3n para campo."""

import base64
import html
import math
import re
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict

from markupsafe import Markup
from odoo import api, fields, models
from odoo.exceptions import UserError

CATASTRO_WMS_URL = "https://ovc.catastro.meh.es/Cartografia/WMS/ServidorWMS.aspx"
WEB_MERCATOR_LIMIT = 20037508.342789244
SAFE_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


class FiberGisDeploymentPlan(models.Model):
    _name = "fiber.gis.deployment.plan"
    _description = "Plan de despliegue de fibra"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "planned_start desc, id desc"

    name = fields.Char(string="Nombre", required=True, tracking=True)
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("review", "En revisi\u00f3n"),
            ("approved", "Aprobado"),
            ("in_progress", "En ejecuci\u00f3n"),
            ("done", "Finalizado"),
            ("cancelled", "Cancelado"),
        ],
        string="Estado",
        default="draft",
        required=True,
        tracking=True,
    )
    responsible_id = fields.Many2one(
        "res.users",
        string="Responsable",
        default=lambda self: self.env.user,
        tracking=True,
    )
    technician_ids = fields.Many2many(
        "res.users",
        "fiber_gis_deployment_plan_technician_rel",
        "plan_id",
        "user_id",
        string="T\u00e9cnicos previstos",
    )
    zone = fields.Char(string="Zona o poblaci\u00f3n", tracking=True)
    planned_start = fields.Date(string="Inicio previsto", tracking=True)
    planned_end = fields.Date(string="Fin previsto", tracking=True)
    reserve_percent = fields.Float(
        string="Reserva de cable (%)",
        default=10.0,
        help="Margen adicional aplicado al metraje dibujado para bobina, cocas y ajustes de instalaci\u00f3n.",
    )
    node_ids = fields.One2many(
        "fiber.gis.node",
        "deployment_plan_id",
        string="Elementos planificados",
    )
    cable_ids = fields.One2many(
        "fiber.gis.cable",
        "deployment_plan_id",
        string="Cables planificados",
    )
    node_count = fields.Integer(string="Elementos", compute="_compute_metrics")
    cable_count = fields.Integer(string="Cables", compute="_compute_metrics")
    estimated_length_m = fields.Float(
        string="Metros dibujados",
        compute="_compute_metrics",
        help="Suma de las longitudes calculadas a partir del trazado de todos los cables del plan.",
    )
    estimated_with_reserve_m = fields.Float(
        string="Metros estimados con reserva",
        compute="_compute_metrics",
    )
    missing_coordinates_count = fields.Integer(
        string="Elementos sin coordenadas",
        compute="_compute_metrics",
    )
    direct_cable_count = fields.Integer(
        string="Cables sin trazado detallado",
        compute="_compute_metrics",
    )
    description = fields.Text(string="Alcance y observaciones")
    active = fields.Boolean(string="Activo", default=True)
    _reserve_percent_not_negative = models.Constraint(
        "CHECK(reserve_percent >= 0)",
        "La reserva de cable no puede ser negativa.",
    )
    _planned_dates_order = models.Constraint(
        "CHECK(planned_start IS NULL OR planned_end IS NULL OR planned_end >= planned_start)",
        "La fecha de fin prevista no puede ser anterior a la fecha de inicio.",
    )

    @api.depends(
        "node_ids",
        "node_ids.latitude",
        "node_ids.longitude",
        "cable_ids",
        "cable_ids.length_m",
        "cable_ids.geometry_geojson",
        "cable_ids.from_node_id.latitude",
        "cable_ids.from_node_id.longitude",
        "cable_ids.to_node_id.latitude",
        "cable_ids.to_node_id.longitude",
        "reserve_percent",
    )
    def _compute_metrics(self):
        for plan in self:
            scope_nodes = plan._scope_nodes()
            plan.node_count = len(plan.node_ids)
            plan.cable_count = len(plan.cable_ids)
            plan.estimated_length_m = sum(plan.cable_ids.mapped("length_m"))
            plan.estimated_with_reserve_m = plan.estimated_length_m * (
                1.0 + max(plan.reserve_percent, 0.0) / 100.0
            )
            plan.missing_coordinates_count = len(
                scope_nodes.filtered(lambda node: not node.latitude or not node.longitude)
            )
            plan.direct_cable_count = len(
                plan.cable_ids.filtered(lambda cable: len(cable._get_geometry_points()) < 2)
            )

    def _scope_nodes(self):
        self.ensure_one()
        return (
            self.node_ids
            | self.cable_ids.mapped("from_node_id")
            | self.cable_ids.mapped("to_node_id")
        ).exists()

    def action_open_map(self):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "fiber_gis.map_action",
            "name": f"Plan de despliegue - {self.display_name}",
            "params": {
                "deployment_plan_id": self.id,
            },
        }

    def action_print_pdf(self):
        self.ensure_one()
        if not self.node_ids and not self.cable_ids:
            raise UserError("A\u00f1ade al menos un elemento o un cable antes de imprimir el plan.")
        return self.env.ref("fiber_gis.action_report_fiber_deployment_plan_v2").report_action(self)

    @api.model
    def action_print_plan_pdf(self, plan_id):
        plan = self.browse(plan_id).exists()
        if not plan:
            raise UserError("El plan de despliegue ya no existe.")
        return plan.action_print_pdf()

    @api.model
    def get_map_scope(self, plan_id):
        plan = self.browse(plan_id).exists()
        if not plan:
            raise UserError("El plan de despliegue ya no existe.")
        plan.ensure_one()
        nodes = plan._scope_nodes()
        return {
            "plan": {
                "id": plan.id,
                "name": plan.display_name,
                "state": plan.state,
                "state_label": dict(plan._fields["state"].selection).get(plan.state, plan.state),
                "node_count": plan.node_count,
                "cable_count": plan.cable_count,
                "estimated_length_m": plan.estimated_length_m,
                "estimated_with_reserve_m": plan.estimated_with_reserve_m,
                "reserve_percent": plan.reserve_percent,
                "missing_coordinates_count": plan.missing_coordinates_count,
                "direct_cable_count": plan.direct_cable_count,
            },
            "node_ids": nodes.ids,
            "cable_ids": plan.cable_ids.ids,
            "site_ids": nodes.mapped("site_id").ids,
        }

    def action_submit_review(self):
        self.write({"state": "review"})

    def action_approve(self):
        self.write({"state": "approved"})

    def action_start(self):
        self.write({"state": "in_progress"})

    def action_finish(self):
        self.write({"state": "done"})

    def action_cancel(self):
        self.write({"state": "cancelled"})

    def action_reset_draft(self):
        self.write({"state": "draft"})

    def _get_report_data(self):
        self.ensure_one()
        state_labels = dict(self._fields["state"].selection)
        route_labels = dict(self.env["fiber.gis.cable"]._fields["route_kind"].selection)
        node_kind_labels = dict(self.env["fiber.gis.node"]._fields["node_kind"].selection)
        scope_nodes = self._scope_nodes().sorted(lambda node: (node.display_name or "").lower())
        planned_node_ids = set(self.node_ids.ids)
        node_rows = []
        for sequence, node in enumerate(scope_nodes, start=1):
            node_rows.append({
                "sequence": sequence,
                "name": node.display_name or "",
                "type": (
                    node.type_id.display_name
                    or node.node_category_id.display_name
                    or node_kind_labels.get(node.node_kind, node.node_kind or "")
                ),
                "role": "Elemento planificado" if node.id in planned_node_ids else "Conexi\u00f3n existente",
                "address": node.address or "",
                "coordinates": (
                    f"{node.latitude:.7f}, {node.longitude:.7f}"
                    if node.latitude and node.longitude
                    else "Sin coordenadas"
                ),
                "state": dict(node._fields["state"].selection).get(node.state, node.state or ""),
            })

        cable_rows = []
        material_groups = defaultdict(lambda: {"quantity": 0, "length_m": 0.0})
        for cable in self.cable_ids.sorted(lambda item: (item.display_name or "").lower()):
            points = [point for point in cable._get_route_points() if all(point)]
            segment_kinds = cable._get_route_segment_kinds(max(len(points) - 1, 0))
            route_names = []
            for kind in segment_kinds or [cable.route_kind]:
                label = route_labels.get(kind, kind or "")
                if label and label not in route_names:
                    route_names.append(label)
            cable_rows.append({
                "name": cable.display_name or "",
                "from": cable.from_node_id.display_name or "",
                "to": cable.to_node_id.display_name or "",
                "fibers": cable.total_fiber_count,
                "topology": cable.topology or "",
                "route": " / ".join(route_names),
                "length_m": cable.length_m,
                "drawing": "Trazado dibujado" if len(cable._get_geometry_points()) >= 2 else "L\u00ednea directa",
                "state": dict(cable._fields["state"].selection).get(cable.state, cable.state or ""),
            })
            type_name = cable.type_id.display_name or "Cable de fibra"
            key = (type_name, cable.total_fiber_count, cable.tube_count)
            material_groups[key]["quantity"] += 1
            material_groups[key]["length_m"] += cable.length_m

        materials = []
        for (type_name, fibers, tubes), values in sorted(material_groups.items()):
            materials.append({
                "type": type_name,
                "fibers": fibers,
                "tubes": tubes,
                "quantity": values["quantity"],
                "length_m": values["length_m"],
                "reserve_length_m": values["length_m"] * (
                    1.0 + max(self.reserve_percent, 0.0) / 100.0
                ),
            })

        return {
            "state": state_labels.get(self.state, self.state),
            "nodes": node_rows,
            "cables": cable_rows,
            "materials": materials,
            "node_count": self.node_count,
            "connection_node_count": len(scope_nodes) - self.node_count,
            "cable_count": self.cable_count,
            "estimated_length_m": self.estimated_length_m,
            "estimated_with_reserve_m": self.estimated_with_reserve_m,
            "missing_coordinates_count": self.missing_coordinates_count,
            "direct_cable_count": self.direct_cable_count,
        }

    def _get_plan_map_svg(self):
        self.ensure_one()
        nodes = self._scope_nodes().sorted(lambda node: (node.display_name or "").lower())
        cable_routes = []
        points = []
        for cable in self.cable_ids:
            route = [point for point in cable._get_route_points() if all(point)]
            if len(route) >= 2:
                cable_routes.append((cable, route))
                points.extend(route)
        for node in nodes:
            if node.latitude and node.longitude:
                points.append((node.latitude, node.longitude))
        if not points:
            return Markup(
                "<div class='plan-map-note'>No hay coordenadas suficientes para dibujar el plano.</div>"
            )

        width = 1100
        height = 520
        image_width = 2200
        image_height = 1040
        mercator_points = [self._latlon_to_web_mercator(lat, lon) for lat, lon in points]
        min_x = min(point[0] for point in mercator_points)
        max_x = max(point[0] for point in mercator_points)
        min_y = min(point[1] for point in mercator_points)
        max_y = max(point[1] for point in mercator_points)
        x_pad = max((max_x - min_x) * 0.08, 35)
        y_pad = max((max_y - min_y) * 0.08, 35)
        min_x, min_y, max_x, max_y = self._fit_bbox_to_aspect(
            min_x - x_pad,
            min_y - y_pad,
            max_x + x_pad,
            max_y + y_pad,
            width / height,
        )

        def project(lat, lon):
            mercator_x, mercator_y = self._latlon_to_web_mercator(lat, lon)
            x = ((mercator_x - min_x) / max(max_x - min_x, 0.000001)) * width
            y = ((max_y - mercator_y) / max(max_y - min_y, 0.000001)) * height
            return round(x, 1), round(y, 1)

        catastro_image = self._catastro_image(
            min_x,
            min_y,
            max_x,
            max_y,
            image_width,
            image_height,
        )
        route_shadows = []
        route_lines = []
        for cable, route in cable_routes:
            coordinates = [project(lat, lon) for lat, lon in route]
            kinds = cable._get_route_segment_kinds(len(coordinates) - 1)
            color = cable.color if SAFE_COLOR.match(cable.color or "") else "#d946ef"
            for index, (start, end) in enumerate(zip(coordinates, coordinates[1:])):
                kind = kinds[index] if index < len(kinds) else cable.route_kind
                dash = {
                    "facade": "",
                    "aerial": "10 6",
                    "underground": "2 6",
                }.get(kind, "")
                dash_attr = f" stroke-dasharray='{dash}'" if dash else ""
                title = html.escape(cable.display_name or "")
                route_shadows.append(
                    f"<line x1='{start[0]}' y1='{start[1]}' x2='{end[0]}' y2='{end[1]}' "
                    f"class='plan-route-shadow'{dash_attr}/>"
                )
                route_lines.append(
                    f"<line x1='{start[0]}' y1='{start[1]}' x2='{end[0]}' y2='{end[1]}' "
                    f"class='plan-route' stroke='{color}'{dash_attr}><title>{title}</title></line>"
                )

        node_marks = []
        for sequence, node in enumerate(nodes, start=1):
            if not node.latitude or not node.longitude:
                continue
            x, y = project(node.latitude, node.longitude)
            label = html.escape(node.display_name or "")
            node_marks.append(
                f"<circle cx='{x}' cy='{y}' r='7' class='plan-node'/>"
                f"<text x='{x}' y='{y + 2.8}' text-anchor='middle' class='plan-node-number'>{sequence}</text>"
                f"<text x='{x + 10}' y='{y - 9}' class='plan-node-label'>{label}</text>"
            )

        return Markup(
            "<style>"
            ".plan-map-wrap{position:relative;width:100%;border:1px solid #475569;background:#fff;line-height:0;overflow:hidden}"
            ".plan-map-base{display:block;width:100%;height:auto}"
            ".plan-map-overlay{position:absolute;left:0;top:0;width:100%;height:100%}"
            ".plan-route-shadow{stroke:#fff;stroke-width:9;stroke-linecap:round;stroke-opacity:.92}"
            ".plan-route{fill:none;stroke-width:4.5;stroke-linecap:round;stroke-linejoin:round}"
            ".plan-node{fill:#fff;stroke:#111827;stroke-width:2}"
            ".plan-node-number{font-size:8px;font-weight:700;fill:#111827}"
            ".plan-node-label{font-size:8px;font-weight:700;fill:#111827;paint-order:stroke;stroke:#fff;stroke-width:3px}"
            ".plan-map-note{padding:18px;color:#334155;font-size:12px;line-height:1.35}"
            "</style>"
            "<div class='plan-map-wrap'>"
            f"{catastro_image}"
            f"<svg class='plan-map-overlay' viewBox='0 0 {width} {height}' xmlns='http://www.w3.org/2000/svg'>"
            f"{''.join(route_shadows)}"
            f"{''.join(route_lines)}"
            f"{''.join(node_marks)}"
            "</svg>"
            "</div>"
        )

    @staticmethod
    def _latlon_to_web_mercator(lat, lon):
        clipped_lat = max(min(lat, 85.05112878), -85.05112878)
        x = lon * WEB_MERCATOR_LIMIT / 180.0
        y = math.log(
            math.tan((90.0 + clipped_lat) * math.pi / 360.0)
        ) * WEB_MERCATOR_LIMIT / math.pi
        return x, y

    @staticmethod
    def _fit_bbox_to_aspect(min_x, min_y, max_x, max_y, target_aspect):
        bbox_width = max(max_x - min_x, 1)
        bbox_height = max(max_y - min_y, 1)
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        if bbox_width / bbox_height < target_aspect:
            bbox_width = bbox_height * target_aspect
        else:
            bbox_height = bbox_width / target_aspect
        return (
            center_x - bbox_width / 2,
            center_y - bbox_height / 2,
            center_x + bbox_width / 2,
            center_y + bbox_height / 2,
        )

    @staticmethod
    def _catastro_image(min_x, min_y, max_x, max_y, width, height):
        params = urllib.parse.urlencode({
            "SERVICE": "WMS",
            "VERSION": "1.1.1",
            "REQUEST": "GetMap",
            "FORMAT": "image/png",
            "TRANSPARENT": "FALSE",
            "SRS": "EPSG:3857",
            "LAYERS": "Catastro",
            "STYLES": "",
            "BBOX": f"{min_x},{min_y},{max_x},{max_y}",
            "WIDTH": str(width),
            "HEIGHT": str(height),
        })
        request = urllib.request.Request(
            f"{CATASTRO_WMS_URL}?{params}",
            headers={"User-Agent": "Odoo Fiber GIS deployment plan report"},
        )
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                payload = response.read()
                content_type = response.headers.get("Content-Type", "image/png")
        except (urllib.error.URLError, TimeoutError):
            return (
                f"<div class='plan-map-note' style='height:{height}px;background:#f8fafc;'>"
                "No se ha podido cargar Catastro para este plano."
                "</div>"
            )
        if not payload.startswith(b"\x89PNG"):
            return (
                f"<div class='plan-map-note' style='height:{height}px;background:#f8fafc;'>"
                "Catastro no ha devuelto una imagen v\u00e1lida."
                "</div>"
            )
        encoded = base64.b64encode(payload).decode("ascii")
        return (
            f"<img class='plan-map-base' src='data:{content_type};base64,{encoded}' "
            "alt='Plano del Catastro'/>"
        )
