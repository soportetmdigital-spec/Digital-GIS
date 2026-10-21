"""Asistente para registrar cables y fibras dentro de bandejas."""

import html

from odoo import api, fields, models
from odoo.exceptions import UserError
from .work_log import work_employee_id
from .splitter_options import SPLITTER_RATIO_SELECTION


class FiberGisCableTrayWizard(models.TransientModel):
    _name = "fiber.gis.cable.tray.wizard"
    employee_id = fields.Many2one("hr.employee.public", string="T\u00e9cnico", default=lambda self: work_employee_id(self.env))
    _description = "Registrar cable en bandeja"

    @api.model
    def _selection_operation(self):
        options = [
            ("rest", "Fibra en punta"),
            ("pending_cancel", "Fibra pendiente de anular"),
            ("fusion", "Fusionar con otro cable"),
            ("pass", "Sangría"),
            ("splitter", "Instalar splitter"),
            ("customer_drop", "Acometida final de cliente"),
        ]
        if self.env.context.get("fiber_gis_internal_splitter_fusion"):
            options.insert(-1, ("splitter_fusion", "Conectar fibra a splitter"))
        return options

    operation = fields.Selection(
        selection="_selection_operation",
        string="Operacion",
        default="rest",
        required=True,
    )
    available_cable_ids = fields.Many2many(
        "fiber.gis.cable",
        string="Cables del elemento",
        compute="_compute_available_cable_ids",
    )
    available_pass_input_cable_ids = fields.Many2many(
        "fiber.gis.cable",
        string="Cables que vienen de otra caja",
        compute="_compute_available_cable_ids",
    )
    available_pass_output_cable_ids = fields.Many2many(
        "fiber.gis.cable",
        string="Cables que van a otra caja",
        compute="_compute_available_cable_ids",
    )
    available_fiber_ids = fields.Many2many(
        "fiber.gis.cable.fiber",
        string="Fibras disponibles",
        compute="_compute_available_fiber_ids",
    )
    available_other_fiber_ids = fields.Many2many(
        "fiber.gis.cable.fiber",
        string="Fibras del otro cable",
        compute="_compute_available_fiber_ids",
    )
    available_drop_cable_ids = fields.Many2many(
        "fiber.gis.cable",
        string="Acometidas del elemento",
        compute="_compute_splitter_and_drop_options",
    )
    available_drop_fiber_ids = fields.Many2many(
        "fiber.gis.cable.fiber",
        string="Fibras de acometida",
        compute="_compute_splitter_and_drop_options",
    )
    available_splitter_ids = fields.Many2many(
        "fiber.gis.splitter",
        string="Splitters del elemento",
        compute="_compute_splitter_and_drop_options",
    )
    available_splitter_output_ids = fields.Many2many(
        "fiber.gis.splitter.output",
        string="Salidas libres",
        compute="_compute_splitter_and_drop_options",
    )
    available_target_splitter_output_ids = fields.Many2many(
        "fiber.gis.splitter.output",
        string="Salidas libres del splitter",
        compute="_compute_splitter_and_drop_options",
    )
    cable_id = fields.Many2one("fiber.gis.cable", string="Cable")
    pass_output_cable_id = fields.Many2one(
        "fiber.gis.cable",
        string="Cable que va a la caja destino",
    )
    cable_topology = fields.Char(related="cable_id.topology", string="Tipologia cable", readonly=True)
    node_id = fields.Many2one("fiber.gis.node", string="Elemento", required=True)
    tray_id = fields.Many2one("fiber.gis.tray", string="Bandeja")
    from_fiber = fields.Integer(string="Desde fibra", default=1, required=True)
    to_fiber = fields.Integer(string="Hasta fibra", default=1, required=True)
    selected_fiber_ids = fields.Many2many(
        "fiber.gis.cable.fiber",
        "fiber_gis_tray_wizard_selected_fiber_rel",
        "wizard_id",
        "fiber_id",
        string="Fibras",
    )
    fusion_input_fiber_id = fields.Many2one("fiber.gis.cable.fiber", string="Fibra del cable")
    fusion_input_fiber_ids = fields.Many2many(
        "fiber.gis.cable.fiber",
        "fiber_gis_tray_wizard_fusion_input_rel",
        "wizard_id",
        "fiber_id",
        string="Fibra del cable",
    )
    other_cable_id = fields.Many2one("fiber.gis.cable", string="Cable a empalmar")
    other_cable_topology = fields.Char(related="other_cable_id.topology", string="Tipologia otro cable", readonly=True)
    other_tray_id = fields.Many2one("fiber.gis.tray", string="Bandeja del otro cable")
    other_from_fiber = fields.Integer(string="Fibra del otro cable", default=1)
    fusion_output_fiber_id = fields.Many2one("fiber.gis.cable.fiber", string="Fibra del otro cable")
    fusion_output_fiber_ids = fields.Many2many(
        "fiber.gis.cable.fiber",
        "fiber_gis_tray_wizard_fusion_output_rel",
        "wizard_id",
        "fiber_id",
        string="Fibra del otro cable",
    )
    splitter_ratio = fields.Selection(
        SPLITTER_RATIO_SELECTION,
        string="Relacion splitter",
        default="1:8",
    )
    splitter_name = fields.Char(string="Nombre del splitter")
    splitter_type = fields.Selection(
        [
            ("plc", "PLC"),
            ("fbt", "FBT"),
        ],
        string="Tecnologia",
        default="plc",
    )
    splitter_connector_type = fields.Selection(
        [
            ("none", "Sin conectores"),
            ("sc_apc", "SC/APC"),
            ("sc_upc", "SC/UPC"),
            ("lc_apc", "LC/APC"),
            ("lc_upc", "LC/UPC"),
        ],
        string="Conectores",
        default="none",
    )
    splitter_loss_db = fields.Float(
        string="P\u00e9rdida nominal (dB)",
        default=10.4,
        help="Valor de referencia editable; debe prevalecer el dato del fabricante.",
    )
    target_splitter_id = fields.Many2one(
        "fiber.gis.splitter",
        string="Splitter a conectar",
    )
    target_splitter_output_id = fields.Many2one(
        "fiber.gis.splitter.output",
        string="Boca libre",
    )
    customer_drop_source = fields.Selection(
        [
            ("fiber", "Fibra de cable"),
            ("splitter", "Salida de splitter"),
        ],
        string="Origen de la acometida",
        default="fiber",
    )
    customer_splitter_id = fields.Many2one("fiber.gis.splitter", string="Splitter")
    customer_splitter_output_id = fields.Many2one(
        "fiber.gis.splitter.output",
        string="Salida del splitter",
    )
    customer_id = fields.Many2one("res.partner", string="Cliente")
    customer_address = fields.Char(string="Direcci\u00f3n del cliente")
    customer_latitude = fields.Float(string="Latitud cliente", digits=(10, 7))
    customer_longitude = fields.Float(string="Longitud cliente", digits=(10, 7))
    drop_cable_id = fields.Many2one("fiber.gis.cable", string="Cable de acometida")
    drop_cable_topology = fields.Char(
        related="drop_cable_id.topology",
        string="Tipologia acometida",
        readonly=True,
    )
    drop_fiber_ids = fields.Many2many(
        "fiber.gis.cable.fiber",
        "fiber_gis_tray_wizard_drop_fiber_rel",
        "wizard_id",
        "fiber_id",
        string="Fibra de acometida",
    )

    notes = fields.Text(string="Observaciones")
    source_line_id = fields.Many2one("fiber.gis.tray.line", string="Registro de origen", ondelete="set null")
    source_fiber_id = fields.Many2one("fiber.gis.cable.fiber", string="Fibra seleccionada", ondelete="set null")
    source_info_html = fields.Html(string="Situaci\u00f3n actual", compute="_compute_source_info_html", sanitize=False)

    @api.depends("source_line_id", "source_fiber_id")
    def _compute_source_info_html(self):
        """Calcula y actualiza «origen información HTML» a partir de los datos actuales y sus relaciones."""
        for wizard in self:
            line = wizard.source_line_id
            if not line:
                wizard.source_info_html = False
                continue
            label = dict(line._fields["line_type"].selection).get(line.line_type, "")
            parts = [f"<strong>Situaci\u00f3n actual: {html.escape(line.tray_id.display_name)} - {html.escape(label)}</strong>"]
            for fiber in (line.input_fiber_id, line.output_fiber_id):
                if fiber:
                    parts.append(wizard.node_id._fiber_endpoint_html(fiber, fiber.tube, fiber.tube_color, fiber.color))
            wizard.source_info_html = "<div class='o_fiber_context_info'>" + "".join(parts) + "</div>"

    has_conflict_warning = fields.Boolean(string="Hay aviso de fibras ocupadas")
    conflict_warning_html = fields.Html(
        string="Aviso",
        sanitize=False,
    )
    operation_preview_html = fields.Html(
        string="Previsualizacion",
        compute="_compute_operation_preview_html",
        sanitize=False,
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Crea los registros y prepara sus relaciones o datos derivados antes de devolverlos."""
        splitter_model = self.env["fiber.gis.splitter"]
        for values in vals_list:
            if "splitter_loss_db" not in values:
                ratio = values.get("splitter_ratio") or "1:8"
                values["splitter_loss_db"] = splitter_model.get_default_nominal_loss_db(ratio)
        return super().create(vals_list)

    @api.depends("node_id", "node_id.incoming_cable_ids", "node_id.outgoing_cable_ids")
    def _compute_available_cable_ids(self):
        """Actualiza la lista de cables conectados al elemento seleccionado."""
        for wizard in self:
            if wizard.node_id:
                wizard.available_cable_ids = wizard.node_id.incoming_cable_ids | wizard.node_id.outgoing_cable_ids
                wizard.available_pass_input_cable_ids = wizard.node_id.incoming_cable_ids
                wizard.available_pass_output_cable_ids = wizard.node_id.outgoing_cable_ids
            else:
                wizard.available_cable_ids = self.env["fiber.gis.cable"]
                wizard.available_pass_input_cable_ids = self.env["fiber.gis.cable"]
                wizard.available_pass_output_cable_ids = self.env["fiber.gis.cable"]

    @api.depends(
        "cable_id", "other_cable_id", "node_id", "source_line_id", "source_fiber_id",
        "node_id.tray_ids.line_ids.input_fiber_id", "node_id.tray_ids.line_ids.output_fiber_id",
        "node_id.splitter_ids.input_fiber_id", "node_id.splitter_ids.output_ids.output_fiber_id",
        "node_id.port_ids.fiber_id",
    )
    def _compute_available_fiber_ids(self):
        """Actualiza las listas de fibras disponibles para los cables elegidos."""
        empty = self.env["fiber.gis.cable.fiber"]
        for wizard in self:
            if wizard.cable_id and not wizard.cable_id.fiber_ids:
                wizard.cable_id.action_generate_fibers()
            if wizard.other_cable_id and not wizard.other_cable_id.fiber_ids:
                wizard.other_cable_id.action_generate_fibers()
            wizard.available_fiber_ids = wizard._available_fibers_for_cable(wizard.cable_id) if wizard.cable_id else empty
            wizard.available_other_fiber_ids = wizard._available_fibers_for_cable(wizard.other_cable_id) if wizard.other_cable_id else empty

    def _available_fibers_for_cable(self, cable):
        """Oculta fibras fusionadas o conectadas a la entrada de un splitter."""
        self.ensure_one()
        fibers = cable.fiber_ids
        if not self.node_id or not fibers:
            return fibers

        occupied_lines = self._used_lines_for_fibers(fibers).filtered(
            lambda line: line.line_type in ("fusion", "splitter")
        )
        occupied = occupied_lines.mapped("input_fiber_id") | occupied_lines.mapped("output_fiber_id")
        occupied |= self.env["fiber.gis.splitter"].search([
            ("node_id", "=", self.node_id.id),
            ("input_fiber_id", "in", fibers.ids),
        ]).mapped("input_fiber_id")

        available = fibers - occupied
        preserved = self.source_fiber_id | self.source_line_id.input_fiber_id | self.source_line_id.output_fiber_id
        preserved = preserved.filtered(lambda fiber: fiber.cable_id == cable)
        return (available | preserved).sorted(lambda fiber: (fiber.tube or 0, fiber.number, fiber.id))

    @api.depends(
        "node_id",
        "drop_cable_id",
        "customer_splitter_id",
        "target_splitter_id",
        "node_id.tray_ids.line_ids.input_fiber_id",
        "node_id.tray_ids.line_ids.output_fiber_id",
        "node_id.splitter_ids.input_fiber_id",
        "node_id.splitter_ids.output_ids.output_fiber_id",
        "node_id.port_ids.fiber_id",
    )
    def _compute_splitter_and_drop_options(self):
        """Actualiza las opciones de splitters, salidas y acometidas del elemento."""
        empty_cables = self.env["fiber.gis.cable"]
        empty_fibers = self.env["fiber.gis.cable.fiber"]
        empty_splitters = self.env["fiber.gis.splitter"]
        empty_outputs = self.env["fiber.gis.splitter.output"]
        for wizard in self:
            if not wizard.node_id:
                wizard.available_drop_cable_ids = empty_cables
                wizard.available_drop_fiber_ids = empty_fibers
                wizard.available_splitter_ids = empty_splitters
                wizard.available_splitter_output_ids = empty_outputs
                wizard.available_target_splitter_output_ids = empty_outputs
                continue
            connected_cables = wizard.node_id.incoming_cable_ids | wizard.node_id.outgoing_cable_ids
            drop_cables = connected_cables.filtered(
                lambda cable: cable.type_id.code == "CABLE_DROP"
            )
            for cable in drop_cables.filtered(lambda item: not item.fiber_ids):
                cable.action_generate_fibers()
            splitters = self.env["fiber.gis.splitter"].search([
                ("node_id", "=", wizard.node_id.id),
                ("active", "=", True),
                ("state", "not in", ["retired", "fault"]),
            ])
            wizard.available_drop_cable_ids = drop_cables
            wizard.available_drop_fiber_ids = (
                wizard._available_fibers_for_cable(wizard.drop_cable_id)
                if wizard.drop_cable_id in drop_cables
                else empty_fibers
            )
            wizard.available_splitter_ids = splitters
            wizard.available_splitter_output_ids = (
                wizard.customer_splitter_id.output_ids.filtered(
                    lambda output: output.state == "free" and not output.is_connected
                )
                if wizard.customer_splitter_id in splitters
                else empty_outputs
            )
            wizard.available_target_splitter_output_ids = (
                wizard.target_splitter_id.output_ids.filtered(
                    lambda output: output.state == "free" and not output.is_connected
                )
                if wizard.target_splitter_id in splitters
                else empty_outputs
            )

    @api.onchange("cable_id")
    def _onchange_cable_id(self):
        """Recalcula los campos del formulario al cambiar «cable identificador», antes de guardar el registro."""
        for wizard in self:
            if wizard.cable_id:
                wizard.cable_id.action_generate_fibers()
                wizard.to_fiber = wizard.cable_id.total_fiber_count or 1
                if wizard.node_id not in (wizard.cable_id.from_node_id | wizard.cable_id.to_node_id):
                    wizard.node_id = wizard.cable_id.from_node_id
                wizard.selected_fiber_ids = False
                wizard.fusion_input_fiber_id = False
                wizard.fusion_input_fiber_ids = False
                if wizard.pass_output_cable_id == wizard.cable_id:
                    wizard.pass_output_cable_id = False
                if wizard.operation == "pass":
                    wizard.pass_output_cable_id = wizard._default_pass_output_cable()

    @api.onchange("other_cable_id")
    def _onchange_other_cable_id(self):
        """Recalcula los campos del formulario al cambiar «otro cable identificador», antes de guardar el registro."""
        for wizard in self:
            if wizard.other_cable_id:
                wizard.other_cable_id.action_generate_fibers()
                wizard.fusion_output_fiber_id = False
                wizard.fusion_output_fiber_ids = False

    @api.onchange("pass_output_cable_id")
    def _onchange_pass_output_cable_id(self):
        for wizard in self:
            if wizard.pass_output_cable_id:
                wizard.pass_output_cable_id.action_generate_fibers()

    def _default_pass_output_cable(self):
        """Elige un tramo saliente real compatible con los tubos y fibras del cable entrante."""
        self.ensure_one()
        if not self.node_id or not self.cable_id:
            return self.env["fiber.gis.cable"]
        candidates = self.node_id.outgoing_cable_ids.filtered(lambda cable: cable != self.cable_id)
        if not candidates:
            return self.env["fiber.gis.cable"]
        source = self.cable_id
        candidates = candidates.filtered(
            lambda cable: (
                cable.total_fiber_count == source.total_fiber_count
                and cable.tube_count == source.tube_count
                and cable.fiber_count == source.fiber_count
            )
        )
        if not candidates:
            return self.env["fiber.gis.cable"]

        def compatibility(cable):
            # Entre tramos compatibles se prioriza el que tenga una tipología definida.
            return (
                bool(cable.profile_id),
                -(cable.id or 0),
            )

        selected = candidates.sorted(key=compatibility, reverse=True)[:1]
        if selected:
            selected.action_generate_fibers()
        return selected

    @api.onchange("drop_cable_id")
    def _onchange_drop_cable_id(self):
        """Recalcula los campos del formulario al cambiar «acometida cable identificador», antes de guardar el registro."""
        for wizard in self:
            if wizard.drop_cable_id:
                wizard.drop_cable_id.action_generate_fibers()
            wizard.drop_fiber_ids = False

    @api.onchange("customer_splitter_id")
    def _onchange_customer_splitter_id(self):
        """Recalcula los campos del formulario al cambiar «cliente splitter identificador», antes de guardar el registro."""
        for wizard in self:
            wizard.customer_splitter_output_id = False
            if wizard.customer_splitter_id:
                input_fiber, _path = wizard.customer_splitter_id._upstream_fiber()
                input_cable = input_fiber.cable_id
                wizard.cable_id = input_cable
                wizard.from_fiber = 1
                wizard.to_fiber = input_cable.total_fiber_count or 1

    @api.onchange("target_splitter_id")
    def _onchange_target_splitter_id(self):
        """Recalcula los campos del formulario al cambiar «destino splitter identificador», antes de guardar el registro."""
        for wizard in self:
            wizard.target_splitter_output_id = False
            if wizard.target_splitter_id:
                wizard.tray_id = wizard.target_splitter_id.tray_id

    @api.onchange("customer_drop_source")
    def _onchange_customer_drop_source(self):
        """Recalcula los campos del formulario al cambiar «cliente acometida origen», antes de guardar el registro."""
        for wizard in self:
            wizard.selected_fiber_ids = False
            wizard.customer_splitter_id = False
            wizard.customer_splitter_output_id = False

    @api.onchange("customer_id")
    def _onchange_customer_id(self):
        """Recalcula los campos del formulario al cambiar «cliente identificador», antes de guardar el registro."""
        for wizard in self:
            wizard.drop_cable_id = False
            wizard.drop_fiber_ids = False
            customer = wizard.customer_id
            if not customer:
                wizard.customer_address = False
                wizard.customer_latitude = 0.0
                wizard.customer_longitude = 0.0
                continue
            node_model = self.env["fiber.gis.node"]
            endpoint = node_model.with_context(active_test=False).search([
                ("partner_id", "=", customer.id),
                ("node_kind", "=", "ont"),
            ], limit=1)
            wizard.customer_address = endpoint.address or node_model._customer_address(customer)
            if endpoint and endpoint.latitude and endpoint.longitude:
                wizard.customer_latitude = endpoint.latitude
                wizard.customer_longitude = endpoint.longitude
            else:
                latitude, longitude = node_model._customer_partner_coordinates(customer)
                wizard.customer_latitude = latitude
                wizard.customer_longitude = longitude

    @api.onchange("splitter_ratio")
    def _onchange_splitter_ratio(self):
        """Recalcula los campos del formulario al cambiar «splitter relación», antes de guardar el registro."""
        splitter_model = self.env["fiber.gis.splitter"]
        for wizard in self:
            wizard.splitter_loss_db = splitter_model.get_default_nominal_loss_db(
                wizard.splitter_ratio
            )

    @api.onchange("node_id")
    def _onchange_node_id(self):
        """Recalcula los campos del formulario al cambiar «elemento de red identificador», antes de guardar el registro."""
        for wizard in self:
            if wizard.node_id and wizard.node_id.has_trays:
                tray = wizard.node_id.tray_ids[:1]
                wizard.tray_id = tray
                selected_cable = wizard.cable_id
                if not wizard.cable_id:
                    selected_cable = wizard.node_id.incoming_cable_ids[:1] or wizard.node_id.outgoing_cable_ids[:1]
                    wizard.cable_id = selected_cable
                wizard.to_fiber = (selected_cable.total_fiber_count or 1) if selected_cable else 1
                if wizard.operation == "pass":
                    wizard.pass_output_cable_id = wizard._default_pass_output_cable()

    @api.onchange("operation")
    def _onchange_pass_operation_default_cable(self):
        for wizard in self:
            if wizard.operation == "pass":
                if wizard.node_id and wizard.cable_id not in wizard.node_id.incoming_cable_ids:
                    wizard.cable_id = wizard.node_id.incoming_cable_ids[:1]
                    if wizard.cable_id:
                        wizard.cable_id.action_generate_fibers()
                        wizard.to_fiber = wizard.cable_id.total_fiber_count or 1
                if not wizard.pass_output_cable_id or wizard.pass_output_cable_id == wizard.cable_id:
                    wizard.pass_output_cable_id = wizard._default_pass_output_cable()
            elif wizard.operation != "pass":
                wizard.pass_output_cable_id = False

    @api.onchange("operation", "from_fiber")
    def _onchange_operation_single_fusion(self):
        """Recalcula los campos del formulario al cambiar «operación individual fusión», antes de guardar el registro."""
        for wizard in self:
            if wizard.operation == "fusion":
                wizard.to_fiber = wizard.from_fiber or 1
                wizard.selected_fiber_ids = False
            else:
                wizard.fusion_input_fiber_id = False
                wizard.fusion_output_fiber_id = False
                wizard.fusion_input_fiber_ids = False
                wizard.fusion_output_fiber_ids = False
            if wizard.operation != "splitter_fusion":
                wizard.target_splitter_id = False
                wizard.target_splitter_output_id = False
            source = wizard.source_fiber_id
            if source and source.cable_id == wizard.cable_id:
                if wizard.operation == "fusion":
                    wizard.fusion_input_fiber_ids = source
                else:
                    wizard.selected_fiber_ids = source

    def action_apply(self):
        """Valida y registra en la bandeja la operación elegida en el asistente."""
        return self._action_apply(confirm_conflicts=False)

    def action_apply_confirmed(self):
        """Confirma el aviso de conflicto y aplica la operación seleccionada sobre las fibras."""
        return self._action_apply(confirm_conflicts=True)

    def _action_apply(self, confirm_conflicts=False):
        """Coordina la validación y el guardado de la operación seleccionada, y dirige los casos que requieren confirmación adicional."""
        self.ensure_one()
        self = self.with_context(fiber_gis_employee_id=self.employee_id.id or False)
        work_employee_id(self.env)
        self._validate_common()
        if self.operation == "customer_drop":
            self._prepare_customer_drop()
        self._validate_fiber_selection()
        if not self._is_splitter_customer_drop():
            self.cable_id.action_generate_fibers()
        conflicts = self._operation_conflict_lines()
        if conflicts and not confirm_conflicts:
            return self._open_conflict_confirmation(conflicts)
        if conflicts and confirm_conflicts:
            conflict_count = len(conflicts)
            conflicts.unlink()
            self.node_id._log_work(
                "tray",
                f"Se sustituyen {conflict_count} registro(s) anteriores de bandeja tras confirmacion del tecnico.",
            )
        self.write({
            "has_conflict_warning": False,
            "conflict_warning_html": False,
        })
        if self.operation == "rest":
            self._create_rest_lines()
        elif self.operation == "pending_cancel":
            self._create_pending_cancel_lines()
        elif self.operation == "fusion":
            self._create_fusion_lines()
        elif self.operation == "pass":
            self._create_pass_lines()
        elif self.operation == "splitter":
            self._create_splitter_lines()
        elif self.operation == "splitter_fusion":
            self._create_splitter_fusion_connection()
        elif self.operation == "customer_drop":
            self._create_customer_drop_connection()
        self.node_id._log_work("tray", self._work_log_text())
        return {"type": "ir.actions.act_window_close"}

    def _open_conflict_confirmation(self, conflicts):
        """Abre una ventana de confirmación cuando la operación afecta a fibras que ya tienen una asignación."""
        self.ensure_one()
        return_model = self.env.context.get("active_model")
        return_res_id = self.env.context.get("active_id")
        if return_model not in {"fiber.gis.node", "fiber.gis.cable", "fiber.gis.splitter"} or not return_res_id:
            return_model = "fiber.gis.node"
            return_res_id = self.node_id.id
        return {
            "type": "ir.actions.act_window",
            "name": "Confirmar uso de fibras",
            "res_model": "fiber.gis.cable.tray.confirm.wizard",
            "view_mode": "form",
            "view_id": self.env.ref("fiber_gis.view_fiber_gis_cable_tray_confirm_wizard_form").id,
            "target": "new",
            "context": {
                "default_tray_wizard_id": self.id,
                "default_warning_html": self._build_conflict_warning_html(conflicts),
                "default_return_model": return_model,
                "default_return_res_id": return_res_id,
            },
        }

    @api.depends(
        "operation",
        "cable_id",
        "other_cable_id",
        "selected_fiber_ids",
        "fusion_input_fiber_id",
        "fusion_output_fiber_id",
        "fusion_input_fiber_ids",
        "fusion_output_fiber_ids",
        "from_fiber",
        "to_fiber",
        "other_from_fiber",
        "tray_id",
        "other_tray_id",
        "pass_output_cable_id",
        "splitter_ratio",
        "target_splitter_id",
        "target_splitter_output_id",
        "customer_drop_source",
        "customer_splitter_id",
        "customer_splitter_output_id",
        "customer_id",
        "customer_address",
        "customer_latitude",
        "customer_longitude",
        "drop_cable_id",
        "drop_fiber_ids",
    )
    def _compute_operation_preview_html(self):
        """Calcula y actualiza «operación vista previa HTML» a partir de los datos actuales y sus relaciones."""
        for wizard in self:
            wizard.operation_preview_html = wizard._build_operation_preview_html()

    def _build_operation_preview_html(self):
        """Construye «operación vista previa HTML» con los datos del modelo para mostrarlo o imprimirlo."""
        self.ensure_one()
        if not self.cable_id and not self._is_splitter_customer_drop():
            return "<div class='o_fiber_tray_empty'>Selecciona un cable para ver la previsualizacion.</div>"
        to_fiber = self._effective_to_fiber()
        if not self._is_splitter_customer_drop() and (self.from_fiber < 1 or to_fiber < self.from_fiber):
            return "<div class='o_fiber_tray_empty'>Indica un rango de fibras valido.</div>"
        rows = []
        if self.operation == "fusion" and self.other_cable_id:
            input_number = self._fusion_input_number()
            output_number = self._fusion_output_number()
            rows.append(
                "<div class='o_fiber_tray_preview_row'>"
                f"{self._preview_fiber_token(self.cable_id, input_number)}"
                "<span>&rarr;</span>"
                f"{self._preview_fiber_token(self.other_cable_id, output_number)}"
                "</div>"
            )
        elif self.operation == "splitter":
            selected_numbers = self._selected_numbers_for_primary_cable()
            if not selected_numbers:
                rows.append("<div class='o_fiber_tray_empty'>Selecciona una o varias fibras.</div>")
            for number in selected_numbers:
                rows.append(
                    "<div class='o_fiber_tray_preview_row'>"
                    f"{self._preview_fiber_token(self.cable_id, number)}"
                    f"<span>Splitter {html.escape(self.splitter_ratio or '')}</span>"
                    "</div>"
                )
        elif self.operation == "splitter_fusion":
            output_label = (
                f"{html.escape(self.target_splitter_id.display_name or '')} / "
                f"salida {self.target_splitter_output_id.sequence}"
                if self.target_splitter_output_id
                else "Selecciona una salida libre"
            )
            selected = self.selected_fiber_ids[:1]
            fiber_html = (
                self._preview_fiber_token(self.cable_id, selected.number)
                if selected
                else "<span class='o_fiber_preview_token is-empty'>Selecciona una fibra</span>"
            )
            rows.append(
                "<div class='o_fiber_tray_preview_row'>"
                f"<span class='o_fiber_preview_token'><b>{output_label}</b></span>"
                f"<span>&rarr;</span>{fiber_html}"
                "</div>"
            )
        elif self.operation == "pass":
            pairs = self._pass_fiber_pairs(validate=False)
            cut_numbers = self._selected_numbers_for_primary_cable()
            if not self.pass_output_cable_id:
                rows.append("<div class='o_fiber_tray_empty'>Selecciona el cable que va a la caja destino.</div>")
            for input_fiber, output_fiber in pairs:
                rows.append(
                    "<div class='o_fiber_tray_preview_row'>"
                    f"{self._preview_fiber_token(self.cable_id, input_fiber.number)}"
                    "<span>&rarr;</span>"
                    f"{self._preview_fiber_token(self.pass_output_cable_id, output_fiber.number)}"
                    "</div>"
                )
            for number in cut_numbers:
                rows.append(
                    "<div class='o_fiber_tray_preview_row'>"
                    f"{self._preview_fiber_token(self.cable_id, number)}"
                    "<span>Fibra cortada en punta</span></div>"
                )
            if not pairs and not cut_numbers and self.pass_output_cable_id:
                rows.append("<div class='o_fiber_tray_empty'>Selecciona fibras cortadas o comprueba los cables.</div>")
        elif self.operation == "customer_drop":
            drop_fiber = self.drop_fiber_ids[:1]
            if self.customer_drop_source == "splitter":
                source = (
                    f"{html.escape(self.customer_splitter_id.display_name or '')} / "
                    f"salida {self.customer_splitter_output_id.sequence}"
                    if self.customer_splitter_output_id
                    else "Selecciona una salida libre"
                )
                source_html = f"<span class='o_fiber_preview_token'><b>{source}</b></span>"
            else:
                selected = self.selected_fiber_ids[:1]
                source_html = (
                    self._preview_fiber_token(self.cable_id, selected.number)
                    if selected
                    else "<span class='o_fiber_preview_token is-empty'>Selecciona una fibra</span>"
                )
            if drop_fiber:
                destination_html = self._preview_fiber_token(drop_fiber.cable_id, drop_fiber.number)
            elif self.customer_id:
                destination_html = (
                    "<span class='o_fiber_preview_token'>"
                    f"<b>{html.escape(self.customer_id.display_name or '')}</b>"
                    f"<span>{html.escape(self.customer_address or '')}</span>"
                    "</span>"
                )
            else:
                destination_html = (
                    "<span class='o_fiber_preview_token is-empty'>Selecciona el cliente</span>"
                )
            rows.append(
                "<div class='o_fiber_tray_preview_row'>"
                f"{source_html}<span>&rarr;</span>{destination_html}"
                "</div>"
            )
        else:
            label = {
                "rest": "Fibra en punta",
                "pending_cancel": "Fibra pendiente de anular",
            }.get(self.operation, "Sangría con fibra cortada")
            selected_numbers = self._selected_numbers_for_primary_cable()
            if not selected_numbers:
                rows.append("<div class='o_fiber_tray_empty'>Selecciona una o varias fibras.</div>")
            for number in selected_numbers:
                rows.append(
                    "<div class='o_fiber_tray_preview_row'>"
                    f"{self._preview_fiber_token(self.cable_id, number)}"
                    f"<span>{html.escape(label)}</span>"
                    "</div>"
                )
        return (
            "<div class='o_fiber_tray_preview'>"
            f"<strong>{html.escape(self.cable_id.topology or '')}</strong>"
            f"{''.join(rows[:48])}"
            f"{'<em>Se muestran las primeras 48 operaciones.</em>' if len(rows) > 48 else ''}"
            "</div>"
        )

    def _preview_fiber_token(self, cable, number):
        """Construye el indicador visual de una fibra para la previsualización del asistente."""
        if not cable or number < 1:
            return "<span class='o_fiber_preview_token is-empty'>Fibra no valida</span>"
        fiber = cable.fiber_ids.filtered(lambda item: item.number == number)[:1]
        if fiber and self.node_id:
            return self.node_id._fiber_endpoint_html(fiber, fiber.tube, fiber.tube_color, fiber.color)
        fiber_model = self.env["fiber.gis.cable.fiber"]
        tube = cable._tube_for_fiber(number) if cable.tube_count else 0
        fiber_color_index = cable._fiber_color_index(number)
        fiber_color = fiber_model.fiber_color(fiber_color_index)
        tube_html = ""
        if tube:
            tube_color = fiber_model.fiber_color(tube)
            tube_html = (
                f"<i style='background:{html.escape(tube_color)}'></i>"
                f"<span>T{tube}</span>"
            )
        return (
            "<span class='o_fiber_preview_token'>"
            f"{tube_html}"
            f"<i style='background:{html.escape(fiber_color)}'></i>"
            f"<span>F{number}</span>"
            f"<b>{html.escape(cable.display_name or '')}</b>"
            "</span>"
        )

    def _validate_common(self):
        """Valida los datos generales necesarios antes de registrar la operación de bandeja."""
        self.ensure_one()
        if not self.tray_id:
            raise UserError("Selecciona la bandeja donde se registra el trabajo.")
        if self._is_splitter_customer_drop():
            if self.tray_id.node_id != self.node_id:
                raise UserError("La bandeja seleccionada no pertenece al elemento indicado.")
            return
        if not self.cable_id:
            raise UserError("Selecciona el cable relacionado con el trabajo.")
        to_fiber = self._effective_to_fiber()
        if self.node_id not in (self.cable_id.from_node_id | self.cable_id.to_node_id):
            raise UserError("El elemento debe ser uno de los extremos del cable.")
        if self.tray_id and self.tray_id.node_id != self.node_id:
            raise UserError("La bandeja seleccionada no pertenece al elemento indicado.")
        if self.from_fiber < 1 or to_fiber < self.from_fiber:
            raise UserError("Revisa el rango de fibras.")
        if to_fiber > (self.cable_id.total_fiber_count or 0):
            raise UserError("El rango supera el numero de fibras del cable.")

    def _is_splitter_customer_drop(self):
        """Indica si la conexión seleccionada corresponde a una acometida de cliente desde un splitter."""
        self.ensure_one()
        return self.operation == "customer_drop" and self.customer_drop_source == "splitter"

    def _validate_fiber_selection(self):
        """Comprueba que las fibras seleccionadas sean válidas para la operación elegida."""
        self.ensure_one()
        if self.operation == "fusion":
            input_fiber = self._fusion_input_fiber()
            output_fiber = self._fusion_output_fiber()
            if not input_fiber or not output_fiber:
                raise UserError("Selecciona una fibra de cada cable para fusionar.")
            if len(self.fusion_input_fiber_ids) > 1 or len(self.fusion_output_fiber_ids) > 1:
                raise UserError("Para fusionar solo puedes seleccionar una fibra de cada cable.")
            if input_fiber.cable_id != self.cable_id:
                raise UserError("La fibra seleccionada no pertenece al cable principal.")
            if output_fiber.cable_id != self.other_cable_id:
                raise UserError("La fibra seleccionada no pertenece al otro cable.")
            return
        if self.operation == "customer_drop":
            self._validate_customer_drop_selection()
            return
        if self.operation == "pass":
            self._validate_pass_cables()
            return
        if self.operation == "splitter_fusion":
            self._validate_splitter_fusion_selection()
            return
        if not self.selected_fiber_ids:
            raise UserError("Selecciona al menos una fibra.")
        if self.operation == "splitter" and len(self.selected_fiber_ids) != 1:
            raise UserError("Selecciona una sola fibra para alimentar el splitter.")
        wrong_fibers = self.selected_fiber_ids.filtered(lambda fiber: fiber.cable_id != self.cable_id)
        if wrong_fibers:
            raise UserError("Hay fibras seleccionadas que no pertenecen al cable indicado.")

    def _validate_splitter_fusion_selection(self):
        """Comprueba que se hayan seleccionado las fibras necesarias para enlazar dos splitters."""
        self.ensure_one()
        if not self.target_splitter_id or not self.target_splitter_output_id:
            raise UserError("Selecciona el splitter y una boca libre.")
        if self.target_splitter_id.node_id != self.node_id:
            raise UserError("El splitter no pertenece al elemento actual.")
        if self.target_splitter_id.tray_id != self.tray_id:
            raise UserError("La bandeja debe ser la misma en la que est\u00e1 instalado el splitter.")
        if self.target_splitter_output_id.splitter_id != self.target_splitter_id:
            raise UserError("La boca no pertenece al splitter seleccionado.")
        if (
            self.target_splitter_output_id.state != "free"
            or self.target_splitter_output_id.is_connected
        ):
            raise UserError("La boca del splitter ya est\u00e1 ocupada.")
        if len(self.selected_fiber_ids) != 1:
            raise UserError("Selecciona una sola fibra para conectarla al splitter.")
        fiber = self.selected_fiber_ids[:1]
        if fiber.cable_id != self.cable_id:
            raise UserError("La fibra seleccionada no pertenece al cable indicado.")
        if fiber == self.target_splitter_id.input_fiber_id:
            raise UserError("La fibra de entrada del splitter no puede utilizarse como salida.")
        existing_output = self.env["fiber.gis.splitter.output"].search([
            ("splitter_id.node_id", "=", self.node_id.id),
            ("output_fiber_id", "=", fiber.id),
        ], limit=1)
        if existing_output:
            raise UserError(
                f"La fibra ya est\u00e1 conectada a {existing_output.splitter_id.display_name}, "
                f"salida {existing_output.sequence}."
            )

    def _effective_to_fiber(self):
        """Resuelve el número final de fibra considerando la selección individual o el intervalo introducido."""
        self.ensure_one()
        return self.from_fiber if self.operation == "fusion" else self.to_fiber

    def _validate_pass_cables(self):
        """Valida los dos tramos que atraviesan el elemento y su correspondencia de fibras."""
        self.ensure_one()
        output_cable = self.pass_output_cable_id
        if not output_cable:
            raise UserError("Selecciona el cable que va a la caja destino.")
        if output_cable == self.cable_id:
            raise UserError("El cable de entrada y el de salida deben ser distintos.")
        if self.node_id not in (output_cable.from_node_id | output_cable.to_node_id):
            raise UserError("El cable que va a la caja destino no está conectado al elemento actual.")
        if self.node_id == output_cable.to_node_id:
            raise UserError("El cable de salida debe ir desde esta caja hacia la caja destino.")
        if self.node_id != self.cable_id.to_node_id:
            raise UserError("El cable que viene de otra caja debe llegar al elemento actual.")
        wrong_fibers = self.selected_fiber_ids.filtered(lambda fiber: fiber.cable_id != self.cable_id)
        if wrong_fibers:
            raise UserError("Las fibras cortadas deben pertenecer al cable que viene de la caja anterior.")
        pairs = self._pass_fiber_pairs(validate=True)
        if not pairs:
            raise UserError("No hay fibras continuas entre los dos cables. Selecciona fibras cortadas en punta o revisa la correspondencia.")

    def _pass_fiber_pairs(self, validate=False):
        """Empareja por número las fibras no cortadas del cable entrante y el cable saliente."""
        self.ensure_one()
        if not self.cable_id or not self.pass_output_cable_id:
            return []
        self.cable_id.action_generate_fibers()
        self.pass_output_cable_id.action_generate_fibers()
        cut_ids = set(self.selected_fiber_ids.filtered(lambda fiber: fiber.cable_id == self.cable_id).ids)
        output_by_number = {fiber.number: fiber for fiber in self.pass_output_cable_id.fiber_ids}
        pairs = []
        missing = []
        for input_fiber in self.cable_id.fiber_ids:
            if input_fiber.id in cut_ids:
                continue
            output_fiber = output_by_number.get(input_fiber.number)
            if output_fiber:
                pairs.append((input_fiber, output_fiber))
            else:
                missing.append(input_fiber.number)
        if validate and missing:
            preview = ", ".join(str(number) for number in missing[:8])
            suffix = "…" if len(missing) > 8 else ""
            raise UserError(
                "No existe la misma numeración de fibra en el cable de salida para: "
                f"{preview}{suffix}. Marca esas fibras como cortadas o corrige los cables."
            )
        return pairs

    def _selected_numbers_for_primary_cable(self):
        """Devuelve los números de las fibras seleccionadas en el cable principal."""
        self.ensure_one()
        if self.selected_fiber_ids:
            return sorted(self.selected_fiber_ids.filtered(lambda fiber: fiber.cable_id == self.cable_id).mapped("number"))
        return []

    def _fusion_input_fiber(self):
        """Obtiene la fibra seleccionada como entrada de la fusión."""
        self.ensure_one()
        return self.fusion_input_fiber_ids[:1] or self.fusion_input_fiber_id

    def _fusion_output_fiber(self):
        """Obtiene la fibra seleccionada como salida de la fusión."""
        self.ensure_one()
        return self.fusion_output_fiber_ids[:1] or self.fusion_output_fiber_id

    def _fusion_input_number(self):
        """Devuelve el número de la fibra de entrada elegida para la fusión."""
        self.ensure_one()
        fiber = self._fusion_input_fiber()
        return fiber.number if fiber else 0

    def _fusion_output_number(self):
        """Devuelve el número de la fibra de salida elegida para la fusión."""
        self.ensure_one()
        fiber = self._fusion_output_fiber()
        return fiber.number if fiber else 0

    def _fiber_by_number(self, cable, number):
        """Busca una fibra del cable por su número y devuelve el registro correspondiente."""
        cable.action_generate_fibers()
        fiber = cable.fiber_ids.filtered(lambda item: item.number == number)[:1]
        if not fiber:
            raise UserError(f"No se ha encontrado la fibra {number} en {cable.display_name}.")
        return fiber

    def _directional_cable_name(self, cable):
        """Muestra el cable desde la caja actual con dirección, caja vecina y boca."""
        self.ensure_one()
        return cable.with_context(
            fiber_gis_node_id=self.node_id.id,
            fiber_gis_show_boca=True,
        ).display_name

    def _next_position(self, tray):
        """Calcula la siguiente posición libre de la bandeja para registrar la operación."""
        positions = tray.line_ids.mapped("position")
        return (max(positions) if positions else 0) + 1

    def _create_line(self, tray, values):
        """Crea «línea» y enlaza los registros necesarios para mantener la trazabilidad."""
        values.setdefault("employee_id", self.employee_id.id or False)
        values.setdefault("position", self._next_position(tray))
        values.setdefault("tray_id", tray.id)
        values.setdefault("notes", self.notes)
        return self.env["fiber.gis.tray.line"].create(values)

    def _check_tray_capacity(self, tray, positions_needed, line_type):
        """Conserva el punto de extensión histórico sin limitar el número de registros."""
        return

    def _check_fibers_available(self, fibers):
        """Comprueba que las fibras seleccionadas estén disponibles para la operación elegida."""
        fibers = fibers.filtered(lambda fiber: fiber)
        if not fibers:
            return
        used_lines = self._used_lines_for_fibers(fibers)
        if used_lines:
            used = used_lines[:1]
            fiber = used.input_fiber_id if used.input_fiber_id.id in fibers.ids else used.output_fiber_id
            line_type = dict(used._fields["line_type"].selection).get(used.line_type, used.line_type)
            raise UserError(
                f"La fibra {fiber.number} del cable {fiber.cable_id.display_name} ya esta registrada "
                f"en {used.tray_id.display_name} como {line_type}."
            )
        splitter_input = self.env["fiber.gis.splitter"].search([
            ("node_id", "=", self.node_id.id), ("input_fiber_id", "in", fibers.ids),
        ], limit=1)
        splitter_output = self.env["fiber.gis.splitter.output"].search([
            ("splitter_id.node_id", "=", self.node_id.id),
            ("output_fiber_id", "in", fibers.ids),
        ], limit=1)
        if splitter_input or splitter_output:
            splitter = splitter_input or splitter_output.splitter_id
            raise UserError(
                f"Una de las fibras seleccionadas ya está conectada al splitter {splitter.display_name}."
            )

    def _used_lines_for_fibers(self, fibers):
        """Busca las líneas de bandeja que ya contienen alguna de las fibras seleccionadas."""
        fibers = fibers.filtered(lambda fiber: fiber)
        if not fibers:
            return self.env["fiber.gis.tray.line"]
        return self.env["fiber.gis.tray.line"].search([
            ("node_id", "=", self.node_id.id),
            "|",
            ("input_fiber_id", "in", fibers.ids),
            ("output_fiber_id", "in", fibers.ids),
        ])

    def _operation_fibers(self):
        """Reúne las fibras que intervienen en la operación del asistente."""
        self.ensure_one()
        if self.operation == "fusion":
            if not self.other_cable_id:
                return self.env["fiber.gis.cable.fiber"]
            return (
                self._fiber_by_number(self.cable_id, self._fusion_input_number())
                | self._fiber_by_number(self.other_cable_id, self._fusion_output_number())
            )
        if self.operation == "pass":
            input_fibers = self.cable_id.fiber_ids
            paired_output = self.env["fiber.gis.cable.fiber"].browse(
                [output.id for _input, output in self._pass_fiber_pairs(validate=False)]
            )
            return input_fibers | paired_output
        if self.operation == "customer_drop":
            drop_fiber = self.drop_fiber_ids[:1]
            if self.customer_drop_source == "splitter":
                return drop_fiber
            return self.selected_fiber_ids[:1] | drop_fiber
        if self.selected_fiber_ids:
            return self.selected_fiber_ids.filtered(lambda fiber: fiber.cable_id == self.cable_id)
        return self.env["fiber.gis.cable.fiber"]

    def _operation_conflict_lines(self):
        """Busca las asignaciones de bandeja existentes que se verían afectadas por la operación."""
        return self._used_lines_for_fibers(self._operation_fibers())

    def _build_conflict_warning_html(self, conflicts):
        """Prepara el aviso visual con el detalle de las asignaciones de fibra que cambiarían."""
        labels = dict(self.env["fiber.gis.tray.line"]._fields["line_type"].selection)
        rows = []
        for line in conflicts[:12]:
            fiber = line.input_fiber_id or line.output_fiber_id
            if not fiber:
                continue
            rows.append(
                "<li>"
                f"{html.escape(fiber.cable_id.display_name or '')} - fibra {fiber.number}: "
                f"{html.escape(labels.get(line.line_type, line.line_type or ''))} "
                f"en {html.escape(line.tray_id.display_name or '')}"
                "</li>"
            )
        more = ""
        if len(conflicts) > 12:
            more = f"<p>Hay {len(conflicts) - 12} registro(s) mas afectados.</p>"
        return (
            "<div class='alert alert-warning'>"
            "<strong>Hay fibras ya registradas en este elemento.</strong>"
            "<p>Si aceptas, se borraran esos registros anteriores y se creara el nuevo trabajo.</p>"
            f"<ul>{''.join(rows)}</ul>"
            f"{more}"
            "</div>"
        )

    def _fibers_in_range(self, cable, first, last):
        """Devuelve las fibras comprendidas entre los números inicial y final indicados."""
        return self.env["fiber.gis.cable.fiber"].browse([
            self._fiber_by_number(cable, number).id for number in range(first, last + 1)
        ])

    def _create_rest_lines(self):
        """Registra en la bandeja cada fibra seleccionada que queda como resto."""
        fibers = self._operation_fibers()
        if not fibers:
            raise UserError("Selecciona al menos una fibra.")
        self._check_tray_capacity(self.tray_id, len(fibers), "free")
        self._check_fibers_available(fibers)
        for number in sorted(fibers.mapped("number")):
            self._create_line(self.tray_id, {
                "line_type": "free",
                "input_fiber_id": self._fiber_by_number(self.cable_id, number).id,
            })

    def _create_pending_cancel_lines(self):
        """Marca las fibras seleccionadas como pendientes de anular, sin consumir capacidad de empalme."""
        fibers = self._operation_fibers()
        if not fibers:
            raise UserError("Selecciona al menos una fibra.")
        self._check_tray_capacity(self.tray_id, len(fibers), "pending_cancel")
        self._check_fibers_available(fibers)
        for fiber in fibers.sorted(lambda item: (item.tube, item.number)):
            self._create_line(self.tray_id, {
                "line_type": "pending_cancel",
                "input_fiber_id": fiber.id,
            })

    def _create_fusion_lines(self):
        """Registra una fusion individual por cada pareja de fibras seleccionada."""
        if not self.other_cable_id:
            raise UserError("Selecciona el cable con el que se va a fusionar.")
        if self.other_cable_id == self.cable_id:
            raise UserError("No se puede fusionar un cable consigo mismo.")
        self.other_cable_id.action_generate_fibers()
        input_number = self._fusion_input_number()
        other_number = self._fusion_output_number()
        if other_number < 1 or other_number > (self.other_cable_id.total_fiber_count or 0):
            raise UserError("La fibra del otro cable no existe.")
        if input_number < 1 or input_number > (self.cable_id.total_fiber_count or 0):
            raise UserError("La fibra del cable no existe.")
        tray = self.other_tray_id or self.tray_id
        if tray.node_id != self.node_id:
            raise UserError("La bandeja del empalme debe pertenecer al elemento indicado.")
        input_fiber = self._fiber_by_number(self.cable_id, input_number)
        output_fiber = self._fiber_by_number(self.other_cable_id, other_number)
        self._check_tray_capacity(tray, 1, "fusion")
        self._check_fibers_available(input_fiber | output_fiber)
        self._create_line(tray, {
            "line_type": "fusion",
            "input_fiber_id": input_fiber.id,
            "output_fiber_id": output_fiber.id,
        })

    def _create_pass_lines(self):
        """Registra continuidad entrante-saliente y deja las fibras cortadas disponibles en punta."""
        pairs = self._pass_fiber_pairs(validate=True)
        cut_fibers = self.selected_fiber_ids.filtered(lambda fiber: fiber.cable_id == self.cable_id)
        if not pairs and not cut_fibers:
            raise UserError("Selecciona las fibras cortadas o comprueba la correspondencia de cables.")
        self._check_tray_capacity(self.tray_id, len(pairs), "pass")
        affected = self._operation_fibers()
        self._check_fibers_available(affected)
        for input_fiber, output_fiber in pairs:
            self._create_line(self.tray_id, {
                "line_type": "pass",
                "input_fiber_id": input_fiber.id,
                "output_fiber_id": output_fiber.id,
            })
        for fiber in cut_fibers.sorted(lambda item: (item.tube or 0, item.number)):
            self._create_line(self.tray_id, {
                "line_type": "free",
                "input_fiber_id": fiber.id,
            })

    def _create_splitter_lines(self):
        """Registra en la bandeja la conexión de las fibras seleccionadas con el splitter."""
        if not self.splitter_ratio:
            raise UserError("Selecciona la relacion del splitter.")
        fibers = self._operation_fibers()
        if len(fibers) != 1:
            raise UserError("Selecciona una sola fibra de entrada para el splitter.")
        self._check_tray_capacity(self.tray_id, 1, "splitter")
        self._check_fibers_available(fibers)
        input_fiber = fibers[:1]
        values = {
            "tray_id": self.tray_id.id,
            "ratio": self.splitter_ratio,
            "splitter_type": self.splitter_type or "plc",
            "connector_type": self.splitter_connector_type or "none",
            "input_fiber_id": input_fiber.id,
            "nominal_loss_db": self.splitter_loss_db,
            "notes": self.notes,
        }
        if self.splitter_name:
            values["name"] = self.splitter_name
        self.env["fiber.gis.splitter"].create(values)

    def _validate_customer_drop_origin(self):
        """Comprueba «cliente acometida origen» y evita continuar si la selección o los datos no son válidos."""
        self.ensure_one()
        if not self.customer_id:
            raise UserError("Selecciona el cliente al que llega la acometida.")
        if self.customer_drop_source == "splitter":
            if not self.customer_splitter_id or not self.customer_splitter_output_id:
                raise UserError("Selecciona el splitter y una salida libre.")
            if self.customer_splitter_id.node_id != self.node_id:
                raise UserError("El splitter no pertenece al elemento actual.")
            if self.customer_splitter_id.tray_id != self.tray_id:
                raise UserError("Selecciona la bandeja donde está instalado el splitter.")
            if self.customer_splitter_output_id.splitter_id != self.customer_splitter_id:
                raise UserError("La salida no pertenece al splitter seleccionado.")
            if (
                self.customer_splitter_output_id.state != "free"
                or self.customer_splitter_output_id.is_connected
            ):
                raise UserError("La salida del splitter ya est\u00e1 ocupada.")
            return
        if len(self.selected_fiber_ids) != 1:
            raise UserError("Selecciona una sola fibra para fusionar con la acometida.")
        if self.selected_fiber_ids[:1].cable_id != self.cable_id:
            raise UserError("La fibra de origen no pertenece al cable indicado.")

    def _prepare_customer_drop(self):
        """Prepara «cliente acometida» y aplica los valores derivados necesarios antes de persistirlos."""
        self.ensure_one()
        self._validate_customer_drop_origin()
        endpoint, drop_cable, drop_fiber = self.node_id._ensure_customer_drop(
            self.customer_id,
            self.customer_address,
            self.customer_latitude,
            self.customer_longitude,
        )
        self.write({
            "drop_cable_id": drop_cable.id,
            "drop_fiber_ids": [(6, 0, [drop_fiber.id])],
            "customer_address": endpoint.address,
            "customer_latitude": endpoint.latitude,
            "customer_longitude": endpoint.longitude,
        })

    def _validate_customer_drop_selection(self):
        """Comprueba «cliente acometida selección» y evita continuar si la selección o los datos no son válidos."""
        self.ensure_one()
        self._validate_customer_drop_origin()
        if not self.drop_cable_id:
            raise UserError("Selecciona el cable de acometida del cliente.")
        if self.node_id not in (
            self.drop_cable_id.from_node_id | self.drop_cable_id.to_node_id
        ):
            raise UserError("La acometida debe estar conectada al elemento actual.")
        if self.drop_cable_id.type_id.code != "CABLE_DROP":
            raise UserError("El cable destino debe estar clasificado como Acometida.")
        if len(self.drop_fiber_ids) != 1:
            raise UserError("Selecciona una sola fibra de la acometida.")
        drop_fiber = self.drop_fiber_ids[:1]
        if drop_fiber.cable_id != self.drop_cable_id:
            raise UserError("La fibra seleccionada no pertenece a la acometida indicada.")
        if self.customer_drop_source == "splitter":
            return
        source_fiber = self.selected_fiber_ids[:1]
        if self.cable_id == self.drop_cable_id:
            raise UserError("La fibra de origen y la acometida deben pertenecer a cables distintos.")

    def _create_customer_drop_connection(self):
        """Crea la conexión entre la salida del splitter y la acometida del cliente."""
        self.ensure_one()
        drop_fiber = self.drop_fiber_ids[:1]
        if self.customer_drop_source == "splitter":
            self.customer_splitter_id._connect_customer_drop(
                self.customer_splitter_output_id,
                drop_fiber,
                self.notes,
            )
            return
        source_fiber = self.selected_fiber_ids[:1]
        self._check_tray_capacity(self.tray_id, 1, "fusion")
        self._check_fibers_available(source_fiber | drop_fiber)
        self._create_line(self.tray_id, {
            "line_type": "fusion",
            "input_fiber_id": source_fiber.id,
            "output_fiber_id": drop_fiber.id,
        })

    def _create_splitter_fusion_connection(self):
        """Registra la conexión de fibra entre dos splitters."""
        self.ensure_one()
        fiber = self.selected_fiber_ids[:1]
        self._check_fibers_available(fiber)
        self.target_splitter_id._connect_output_fiber(
            self.target_splitter_output_id,
            fiber,
            self.notes,
        )

    def _work_log_text(self):
        """Compone el texto legible que se guarda en el historial del trabajo."""
        labels = dict(self._fields["operation"]._description_selection(self.env))
        if self.operation == "fusion":
            detail = f"fibra {self._fusion_input_number()} con fibra {self._fusion_output_number()}."
        elif self.operation == "pass":
            pairs = self._pass_fiber_pairs(validate=False)
            cut_count = len(self.selected_fiber_ids.filtered(lambda fiber: fiber.cable_id == self.cable_id))
            detail = f"{len(pairs)} fibras continúan; {cut_count} quedan en punta."
        elif self.operation == "splitter_fusion":
            fiber = self.selected_fiber_ids[:1]
            detail = (
                f"{self.target_splitter_id.display_name}, salida "
                f"{self.target_splitter_output_id.sequence}, con fibra {fiber.number} "
                f"de {self.cable_id.display_name}."
            )
        elif self.operation == "customer_drop":
            drop_fiber = self.drop_fiber_ids[:1]
            if self.customer_drop_source == "splitter":
                detail = (
                    f"{self.customer_splitter_id.display_name}, salida "
                    f"{self.customer_splitter_output_id.sequence}, con fibra {drop_fiber.number} "
                    f"de {self.drop_cable_id.display_name}."
                )
            else:
                detail = (
                    f"fibra {self.selected_fiber_ids[:1].number} con fibra {drop_fiber.number} "
                    f"de {self.drop_cable_id.display_name}."
                )
        elif self.selected_fiber_ids:
            detail = f"fibras {', '.join(str(number) for number in self._selected_numbers_for_primary_cable())}."
        else:
            detail = f"fibras {self.from_fiber}-{self.to_fiber}."
        cable_label = self.cable_id.display_name or ""
        if self.operation == "pass":
            cable_label = (
                f"{self._directional_cable_name(self.cable_id)} -> "
                f"{self._directional_cable_name(self.pass_output_cable_id)}"
            )
        return (
            f"{labels.get(self.operation)} en {self.tray_id.display_name or ''}. "
            f"Cable {cable_label}, {detail}"
        )


class FiberGisCableTrayConfirmWizard(models.TransientModel):
    _name = "fiber.gis.cable.tray.confirm.wizard"
    _description = "Confirmar uso de fibras ocupadas"

    tray_wizard_id = fields.Many2one(
        "fiber.gis.cable.tray.wizard",
        string="Asistente de bandejas",
        required=True,
        ondelete="cascade",
    )
    warning_html = fields.Html(
        string="Aviso",
        readonly=True,
        sanitize=False,
    )
    return_model = fields.Char(string="Modelo de retorno", readonly=True)
    return_res_id = fields.Integer(string="Registro de retorno", readonly=True)

    def action_confirm(self):
        """Confirma y ejecuta la operación del asistente."""
        self.ensure_one()
        tray_wizard = self.tray_wizard_id.exists()
        if not tray_wizard:
            raise UserError("El asistente de bandejas ya no est\u00e1 disponible.")

        return_model = self.return_model
        return_res_id = self.return_res_id
        if return_model not in {"fiber.gis.node", "fiber.gis.cable", "fiber.gis.splitter"} or not return_res_id:
            return_model = "fiber.gis.node"
            return_res_id = tray_wizard.node_id.id

        tray_wizard._action_apply(confirm_conflicts=True)
        return_record = self.env[return_model].browse(return_res_id).exists()
        if not return_record:
            return {"type": "ir.actions.act_window_close"}
        return {
            "type": "ir.actions.act_window",
            "name": return_record.display_name,
            "res_model": return_model,
            "res_id": return_record.id,
            "view_mode": "form",
            "target": "current",
        }
