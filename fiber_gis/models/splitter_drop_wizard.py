"""Asistente contextual: una salida conecta fibra, splitter o acometida."""

import html

from odoo import api, fields, models
from odoo.exceptions import UserError
from .work_log import work_employee_id
from .splitter_options import SPLITTER_RATIO_SELECTION


class FiberGisSplitterDropWizard(models.TransientModel):
    _name = "fiber.gis.splitter.drop.wizard"
    employee_id = fields.Many2one("hr.employee.public", string="T\u00e9cnico", default=lambda self: work_employee_id(self.env))
    _description = "Gestionar salida de splitter"

    operation = fields.Selection([
        ("fusion", "Fusionar con una fibra"),
        ("splitter", "Conectar otro splitter"),
        ("customer_drop", "Conectar acometida de cliente"),
    ], string="Operaci\u00f3n", default="customer_drop")
    output_connected = fields.Boolean(related="output_id.is_connected")
    has_child_splitter = fields.Boolean(compute="_compute_has_child_splitter")
    output_state = fields.Selection(related="output_id.state")
    destination_label = fields.Char(related="output_id.destination_label", string="Conexi\u00f3n actual")
    available_cable_ids = fields.Many2many("fiber.gis.cable", compute="_compute_connection_options")
    available_fiber_ids = fields.Many2many("fiber.gis.cable.fiber", compute="_compute_connection_options")
    cable_id = fields.Many2one("fiber.gis.cable", string="Cable")
    fiber_id = fields.Many2one("fiber.gis.cable.fiber", string="Fibra")
    fiber_info_html = fields.Html(compute="_compute_fiber_info_html", sanitize=False)
    create_splitter = fields.Boolean(string="Crear un splitter nuevo", default=True)
    available_splitter_ids = fields.Many2many("fiber.gis.splitter", compute="_compute_connection_options")
    target_splitter_id = fields.Many2one("fiber.gis.splitter", string="Splitter a conectar")
    tray_id = fields.Many2one("fiber.gis.tray", string="Bandeja del nuevo splitter")
    splitter_name = fields.Char(string="Nombre del nuevo splitter")
    new_ratio = fields.Selection(SPLITTER_RATIO_SELECTION, string="Relaci\u00f3n", default="1:8")

    splitter_id = fields.Many2one(
        "fiber.gis.splitter",
        string="Splitter",
        required=True,
        readonly=True,
    )
    node_id = fields.Many2one(
        "fiber.gis.node",
        related="splitter_id.node_id",
        string="Elemento",
        readonly=True,
    )
    available_output_ids = fields.Many2many(
        "fiber.gis.splitter.output",
        string="Salidas libres",
        compute="_compute_available_options",
    )
    output_id = fields.Many2one(
        "fiber.gis.splitter.output",
        string="Salida",
        required=True,
    )
    customer_id = fields.Many2one("res.partner", string="Cliente")
    customer_address = fields.Char(string="Direcci\u00f3n del cliente")
    customer_latitude = fields.Float(string="Latitud cliente", digits=(10, 7))
    customer_longitude = fields.Float(string="Longitud cliente", digits=(10, 7))
    available_drop_cable_ids = fields.Many2many(
        "fiber.gis.cable",
        string="Acometidas",
        compute="_compute_available_options",
    )
    drop_cable_id = fields.Many2one(
        "fiber.gis.cable",
        string="Cable de acometida",
    )
    drop_cable_topology = fields.Char(
        related="drop_cable_id.topology",
        string="Tipologia acometida",
        readonly=True,
    )
    available_drop_fiber_ids = fields.Many2many(
        "fiber.gis.cable.fiber",
        string="Fibras de acometida",
        compute="_compute_available_options",
    )
    drop_fiber_id = fields.Many2one(
        "fiber.gis.cable.fiber",
        string="Fibra de acometida",
    )
    notes = fields.Text(string="Observaciones")

    @api.depends("output_id.downstream_splitter_ids")
    def _compute_has_child_splitter(self):
        """Calcula y actualiza «tiene elemento dependiente splitter» a partir de los datos actuales y sus relaciones."""
        for wizard in self:
            wizard.has_child_splitter = bool(wizard.output_id.downstream_splitter_ids)

    @api.depends("splitter_id", "cable_id")
    def _compute_connection_options(self):
        """Calcula y actualiza «conexión opciones» a partir de los datos actuales y sus relaciones."""
        for wizard in self:
            wizard.available_cable_ids = wizard.splitter_id._connected_cables() if wizard.splitter_id else self.env["fiber.gis.cable"]
            if wizard.cable_id and wizard.cable_id in wizard.available_cable_ids:
                if not wizard.cable_id.fiber_ids:
                    wizard.cable_id.action_generate_fibers()
                wizard.available_fiber_ids = wizard.cable_id.fiber_ids
            else:
                wizard.available_fiber_ids = self.env["fiber.gis.cable.fiber"]
            wizard.available_splitter_ids = self.env["fiber.gis.splitter"].search([
                ("node_id", "=", wizard.node_id.id), ("id", "!=", wizard.splitter_id.id),
                ("input_fiber_id", "=", False), ("input_output_id", "=", False),
                ("state", "not in", ["retired", "fault"]),
            ]) if wizard.node_id else self.env["fiber.gis.splitter"]

    @api.depends(
        "cable_id", "cable_id.fiber_ids", "cable_id.fiber_ids.number", "fiber_id",
        "cable_id.fiber_ids.tube", "cable_id.fiber_ids.tube_color",
        "cable_id.fiber_ids.color", "cable_id.fiber_ids.state",
        "cable_id.fiber_ids.tray_input_line_ids.line_type",
        "cable_id.fiber_ids.tray_output_line_ids.line_type",
        "cable_id.fiber_ids.splitter_input_ids", "cable_id.fiber_ids.splitter_output_ids",
        "node_id", "node_id.name", "node_id.address",
    )
    def _compute_fiber_info_html(self):
        """Lista todas las fibras del cable y resume la conexion registrada en ambos extremos."""
        for wizard in self:
            cable = wizard.cable_id
            node = wizard.node_id
            if not cable or not node:
                wizard.fiber_info_html = False
                continue
            rows = []
            fibers = cable.fiber_ids
            if not fibers:
                cable.action_generate_fibers()
                fibers = cable.fiber_ids
            for fiber in fibers.sorted("number"):
                from_summary = fiber._endpoint_connections(cable.from_node_id)
                to_summary = fiber._endpoint_connections(cable.to_node_id)
                selected = " class='is-selected'" if fiber == wizard.fiber_id else ""
                fiber_visual = wizard.splitter_id._fiber_html(
                    fiber, wizard.splitter_id._fiber_remote_label(fiber),
                )
                rows.append(
                    f"<tr{selected}><td>{fiber_visual}</td>"
                    f"<td><strong>Origen:</strong><br/>{html.escape(from_summary).replace(chr(10), '<br/>')}</td>"
                    f"<td><strong>Destino:</strong><br/>{html.escape(to_summary).replace(chr(10), '<br/>')}</td></tr>"
                )
            wizard.fiber_info_html = (
                "<div class='o_fiber_splitter_fiber_info'><table><thead><tr>"
                "<th>Fibra / cable / extremo</th>"
                "<th>Conexión en origen</th><th>Conexión en destino</th>"
                f"</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
            )

    @api.onchange("cable_id")
    def _onchange_cable_id(self):
        """Recalcula los campos del formulario al cambiar «cable identificador», antes de guardar el registro."""
        for wizard in self:
            if wizard.fiber_id.cable_id != wizard.cable_id:
                wizard.fiber_id = False

    def action_disconnect(self):
        """Ejecuta la acción de usuario «desconexión» y devuelve el resultado correspondiente a Odoo."""
        self.ensure_one()
        self = self.with_context(fiber_gis_employee_id=self.employee_id.id or False)
        work_employee_id(self.env)
        if self.output_id.splitter_id != self.splitter_id:
            raise UserError("La salida no pertenece al splitter.")
        self.output_id._disconnect()
        action = self.output_id.action_manage_connection()
        action["context"]["default_employee_id"] = self.employee_id.id or False
        return action

    def action_open_connected_splitter(self):
        """Abre la ficha del splitter conectado a esta salida."""
        self.ensure_one()
        child = self.output_id.downstream_splitter_ids[:1]
        if not child:
            raise UserError("Esta salida no tiene un splitter conectado.")
        return child.action_open_form()

    @api.depends("splitter_id", "drop_cable_id")
    def _compute_available_options(self):
        """Calcula y actualiza «disponible opciones» a partir de los datos actuales y sus relaciones."""
        empty_outputs = self.env["fiber.gis.splitter.output"]
        empty_cables = self.env["fiber.gis.cable"]
        empty_fibers = self.env["fiber.gis.cable.fiber"]
        for wizard in self:
            splitter = wizard.splitter_id
            if not splitter:
                wizard.available_output_ids = empty_outputs
                wizard.available_drop_cable_ids = empty_cables
                wizard.available_drop_fiber_ids = empty_fibers
                continue
            drop_cables = splitter._customer_drop_cables()
            for cable in drop_cables.filtered(lambda item: not item.fiber_ids):
                cable.action_generate_fibers()
            wizard.available_output_ids = splitter.output_ids.filtered(
                lambda output: output.state == "free" and not output.is_connected
            )
            wizard.available_drop_cable_ids = drop_cables
            wizard.available_drop_fiber_ids = (
                wizard.drop_cable_id.fiber_ids
                if wizard.drop_cable_id in drop_cables
                else empty_fibers
            )

    @api.onchange("drop_cable_id")
    def _onchange_drop_cable_id(self):
        """Recalcula los campos del formulario al cambiar «acometida cable identificador», antes de guardar el registro."""
        self.drop_fiber_id = False
        if self.drop_cable_id:
            self.drop_cable_id.action_generate_fibers()

    @api.onchange("customer_id")
    def _onchange_customer_id(self):
        """Recalcula los campos del formulario al cambiar «cliente identificador», antes de guardar el registro."""
        self.drop_cable_id = False
        self.drop_fiber_id = False
        customer = self.customer_id
        if not customer:
            self.customer_address = False
            self.customer_latitude = 0.0
            self.customer_longitude = 0.0
            return
        node_model = self.env["fiber.gis.node"]
        endpoint = node_model.with_context(active_test=False).search([
            ("partner_id", "=", customer.id),
            ("node_kind", "=", "ont"),
        ], limit=1)
        self.customer_address = endpoint.address or node_model._customer_address(customer)
        if endpoint and endpoint.latitude and endpoint.longitude:
            self.customer_latitude = endpoint.latitude
            self.customer_longitude = endpoint.longitude
        else:
            latitude, longitude = node_model._customer_partner_coordinates(customer)
            self.customer_latitude = latitude
            self.customer_longitude = longitude

    def action_connect(self):
        """Ejecuta la acción de usuario «conexión» y devuelve el resultado correspondiente a Odoo."""
        self.ensure_one()
        self = self.with_context(fiber_gis_employee_id=self.employee_id.id or False)
        work_employee_id(self.env)
        output = self.output_id
        if not output or output.splitter_id != self.splitter_id:
            raise UserError("La salida no pertenece al splitter.")
        output._lock_connection()
        if output.is_connected or output.state != "free":
            raise UserError("Selecciona una salida libre del splitter.")
        if not self.splitter_id.active or self.splitter_id.state in ("retired", "fault"):
            raise UserError("El splitter no esta disponible para nuevas conexiones.")
        if self.operation == "fusion":
            if not self.fiber_id or self.fiber_id.cable_id != self.cable_id:
                raise UserError("Selecciona el cable y una de sus fibras.")
            if self.cable_id not in self.splitter_id._connected_cables():
                raise UserError("El cable debe estar conectado al elemento del splitter.")
            wizard = self.env["fiber.gis.cable.tray.wizard"].with_context(
                fiber_gis_internal_splitter_fusion=True,
            ).create({
                "operation": "splitter_fusion", "node_id": self.node_id.id,
                "tray_id": self.splitter_id.tray_id.id, "cable_id": self.cable_id.id,
                "from_fiber": self.fiber_id.number, "to_fiber": self.fiber_id.number,
                "selected_fiber_ids": [fields.Command.set(self.fiber_id.ids)],
                "target_splitter_id": self.splitter_id.id, "target_splitter_output_id": output.id,
                "notes": self.notes,
                "employee_id": self.employee_id.id or False,
            })
            return wizard.with_context(active_model="fiber.gis.splitter", active_id=self.splitter_id.id).action_apply()
        if self.operation == "splitter":
            if self.create_splitter:
                if not self.tray_id or self.tray_id.node_id != self.node_id:
                    raise UserError("Selecciona una bandeja del mismo elemento para el nuevo splitter.")
                self.env["fiber.gis.cable.tray.wizard"]._check_tray_capacity(self.tray_id, 1, "splitter")
                self.env["fiber.gis.splitter"].create({
                    "name": self.splitter_name or "Splitter", "tray_id": self.tray_id.id,
                    "ratio": self.new_ratio or "1:8", "input_output_id": output.id, "notes": self.notes,
                })
            else:
                target = self.target_splitter_id
                if not target or target.node_id != self.node_id or target == self.splitter_id:
                    raise UserError("Selecciona otro splitter del mismo elemento.")
                if target.input_fiber_id or target.input_output_id or not target.active or target.state in ("retired", "fault"):
                    raise UserError("El splitter seleccionado ya tiene entrada o no esta disponible.")
                target.write({"input_output_id": output.id})
            self.node_id._log_work("tray", f"Conexion de splitter desde {output.display_name}.")
            return {"type": "ir.actions.act_window_close"}
        if self.operation != "customer_drop":
            raise UserError("Elige fusion, splitter o acometida.")
        if not self.customer_id:
            raise UserError("Selecciona el cliente de la acometida.")
        _endpoint, drop_cable, drop_fiber = self.node_id._ensure_customer_drop(
            self.customer_id,
            self.customer_address,
            self.customer_latitude,
            self.customer_longitude,
        )
        self.write({
            "drop_cable_id": drop_cable.id,
            "drop_fiber_id": drop_fiber.id,
            "customer_address": _endpoint.address,
            "customer_latitude": _endpoint.latitude,
            "customer_longitude": _endpoint.longitude,
        })
        self.splitter_id._connect_customer_drop(
            self.output_id,
            drop_fiber,
            self.notes,
        )
        return {"type": "ir.actions.act_window_close"}
