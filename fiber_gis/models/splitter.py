"""Splitters opticos instalados dentro de las bandejas."""

import html

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from .work_log import work_employee_id
from .splitter_options import (
    SPLITTER_DEFAULT_LOSS_DB,
    SPLITTER_RATIO_SELECTION,
    splitter_default_loss_db,
    splitter_output_count,
)


def splitter_upstream_chain(splitter):
    """Devuelve la cadena de splitters aguas arriba e indica si contiene un ciclo."""
    chain = []
    visited = set()
    current = splitter
    while current:
        if current.id in visited:
            return chain, True
        visited.add(current.id)
        chain.append(current)
        source = current.input_output_id
        current = source.splitter_id if source else False
    return chain, False


class FiberGisSplitter(models.Model):
    _name = "fiber.gis.splitter"
    _description = "Splitter \u00f3ptico"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "node_id, tray_id, name, id"

    name = fields.Char(string="Nombre", required=True, default="Splitter", tracking=True)
    code = fields.Char(string="Matr\u00edcula", tracking=True)
    tray_id = fields.Many2one(
        "fiber.gis.tray",
        string="Bandeja",
        required=True,
        ondelete="cascade",
        tracking=True,
    )
    node_id = fields.Many2one(
        "fiber.gis.node",
        string="Elemento",
        required=True,
        index=True,
    )
    ratio = fields.Selection(
        SPLITTER_RATIO_SELECTION,
        string="Relaci\u00f3n",
        default="1:8",
        required=True,
        tracking=True,
    )
    splitter_type = fields.Selection(
        [
            ("plc", "PLC"),
            ("fbt", "FBT"),
        ],
        string="Tecnolog\u00eda",
        default="plc",
        required=True,
        tracking=True,
    )
    connector_type = fields.Selection(
        [
            ("none", "Sin conectores"),
            ("sc_apc", "SC/APC"),
            ("sc_upc", "SC/UPC"),
            ("lc_apc", "LC/APC"),
            ("lc_upc", "LC/UPC"),
        ],
        string="Conectores",
        default="none",
        required=True,
    )
    available_input_fiber_ids = fields.Many2many(
        "fiber.gis.cable.fiber",
        string="Fibras del elemento",
        compute="_compute_available_input_fiber_ids",
    )
    input_fiber_id = fields.Many2one(
        "fiber.gis.cable.fiber",
        string="Fibra de entrada",
        tracking=True,
    )
    input_output_id = fields.Many2one(
        "fiber.gis.splitter.output", string="Salida de origen",
        ondelete="set null", index=True, tracking=True, copy=False,
    )
    _input_output_unique = models.Constraint(
        "UNIQUE(input_output_id)",
        "Una salida solo puede alimentar un splitter.",
    )
    input_cable_id = fields.Many2one(
        "fiber.gis.cable",
        related="input_fiber_id.cable_id",
        string="Cable de entrada",
        store=True,
    )
    input_tube = fields.Integer(related="input_fiber_id.tube", string="Tubo de entrada")
    input_tube_color = fields.Char(related="input_fiber_id.tube_color", string="Color del tubo")
    input_fiber_number = fields.Integer(related="input_fiber_id.number", string="N. fibra de entrada")
    input_fiber_color = fields.Char(related="input_fiber_id.color", string="Color de la fibra")
    nominal_loss_db = fields.Float(
        string="P\u00e9rdida nominal (dB)",
        default=10.4,
        help=(
            "P\u00e9rdida de inserci\u00f3n. Se propone un valor de referencia "
            "para splitter PLC; puede sustituirse por el valor del fabricante."
        ),
    )
    output_ids = fields.One2many(
        "fiber.gis.splitter.output",
        "splitter_id",
        string="Salidas",
        copy=True,
    )
    tray_line_ids = fields.One2many(
        "fiber.gis.tray.line",
        "splitter_id",
        string="Posiciones de bandeja",
    )
    output_count = fields.Integer(string="Salidas totales", compute="_compute_output_counts")
    connected_output_count = fields.Integer(string="Salidas ocupadas", compute="_compute_output_counts")
    free_output_count = fields.Integer(string="Salidas libres", compute="_compute_output_counts")
    diagram_html = fields.Html(
        string="Diagrama del splitter",
        compute="_compute_diagram_html",
        sanitize=False,
    )
    state = fields.Selection(
        [
            ("planned", "Planificado"),
            ("installed", "Instalado"),
            ("active", "Activo"),
            ("fault", "Incidencia"),
            ("retired", "Retirado"),
        ],
        string="Estado",
        default="installed",
        required=True,
        tracking=True,
    )
    install_date = fields.Date(string="Fecha de instalaci\u00f3n", default=fields.Date.context_today)
    technician_id = fields.Many2one(
        "res.users",
        string="Usuario anterior",
        default=lambda self: self.env.user,
    )
    employee_id = fields.Many2one("hr.employee.public", string="T\u00e9cnico")
    work_date = fields.Datetime(string="Fecha del trabajo")
    notes = fields.Text(string="Observaciones")
    work_log_ids = fields.One2many(
        "fiber.gis.node.work.log", "splitter_id", string="Registro técnico",
    )
    active = fields.Boolean(string="Activo", default=True)

    @api.depends("tray_id", "node_id.incoming_cable_ids.fiber_ids", "node_id.outgoing_cable_ids.fiber_ids")
    def _compute_available_input_fiber_ids(self):
        """Calcula y actualiza «disponible entrada fibra identificadores» a partir de los datos actuales y sus relaciones."""
        empty = self.env["fiber.gis.cable.fiber"]
        for splitter in self:
            splitter.available_input_fiber_ids = splitter._available_fibers() if splitter.node_id else empty

    @api.depends("ratio", "output_ids.is_connected")
    def _compute_output_counts(self):
        """Calcula y actualiza «salida cantidades» a partir de los datos actuales y sus relaciones."""
        for splitter in self:
            splitter.output_count = splitter_output_count(splitter.ratio)
            splitter.connected_output_count = len(splitter.output_ids.filtered("is_connected"))
            splitter.free_output_count = max(splitter.output_count - splitter.connected_output_count, 0)

    @api.depends(
        "name",
        "ratio",
        "input_fiber_id",
        "input_output_id",
        "input_output_id.splitter_id.name",
        "input_fiber_id.color",
        "input_fiber_id.tube_color",
        "input_fiber_id.cable_id.name",
        "input_fiber_id.cable_id.from_node_id.name",
        "input_fiber_id.cable_id.from_node_id.code",
        "input_fiber_id.cable_id.from_node_id.address",
        "input_fiber_id.cable_id.to_node_id.name",
        "input_fiber_id.cable_id.to_node_id.code",
        "input_fiber_id.cable_id.to_node_id.address",
        "output_ids.sequence",
        "output_ids.state",
        "output_ids.output_fiber_id",
        "output_ids.output_fiber_id.color",
        "output_ids.output_fiber_id.tube_color",
        "output_ids.output_fiber_id.cable_id.name",
        "output_ids.destination_label",
        "output_ids.downstream_splitter_ids.name",
        "output_ids.downstream_splitter_ids.tray_id",
    )
    def _compute_diagram_html(self):
        """Calcula y actualiza «diagrama HTML» a partir de los datos actuales y sus relaciones."""
        for splitter in self:
            splitter.diagram_html = splitter._build_diagram_html()

    @api.onchange("tray_id")
    def _onchange_tray_id(self):
        """Recalcula los campos del formulario al cambiar «bandeja identificador», antes de guardar el registro."""
        for splitter in self:
            splitter.node_id = splitter.tray_id.node_id

    @api.onchange("ratio")
    def _onchange_ratio(self):
        """Recalcula los campos del formulario al cambiar «relación», antes de guardar el registro."""
        for splitter in self:
            splitter.nominal_loss_db = splitter_default_loss_db(splitter.ratio)

    @api.model
    def get_default_nominal_loss_db(self, ratio):
        """Devuelve la pérdida nominal orientativa según la relación del splitter."""
        return splitter_default_loss_db(ratio)

    @api.constrains("tray_id", "node_id", "input_fiber_id", "input_output_id")
    def _check_input_fiber(self):
        """Valida «entrada fibra» antes de guardar y rechaza los datos que incumplen las reglas del modelo."""
        tray_line_model = self.env["fiber.gis.tray.line"]
        output_model = self.env["fiber.gis.splitter.output"]
        for splitter in self:
            if splitter.tray_id.node_id != splitter.node_id:
                raise ValidationError("La bandeja seleccionada no pertenece al elemento del splitter.")
            if any(child.node_id != splitter.node_id for child in splitter.output_ids.downstream_splitter_ids):
                raise ValidationError("Desconecta los splitters enlazados antes de cambiar de elemento.")
            if splitter.input_output_id:
                source = splitter.input_output_id
                source._lock_connection()
                if splitter.input_fiber_id:
                    raise ValidationError("El splitter solo puede tener una entrada: fibra o salida de otro splitter.")
                if source.node_id != splitter.node_id:
                    raise ValidationError("La conexion directa entre splitters debe estar en el mismo elemento. Para otra caja, usa una fibra de cable.")
                if source.output_fiber_id or source.state in ("reserved", "fault"):
                    raise ValidationError("La salida de origen ya esta ocupada o no esta disponible.")
                if source.splitter_id.state in ("retired", "fault") or not source.splitter_id.active:
                    raise ValidationError("El splitter de origen no esta disponible.")
                _chain, has_cycle = splitter_upstream_chain(splitter)
                if has_cycle:
                    raise ValidationError("No se puede crear un circuito cerrado entre splitters.")
            if not splitter.input_fiber_id or not splitter.node_id:
                continue
            if splitter.input_fiber_id.cable_id not in splitter._connected_cables():
                raise ValidationError(
                    "La fibra de entrada debe pertenecer a un cable conectado al elemento."
                )
            other_splitter = self.search_count([
                ("id", "!=", splitter.id),
                ("node_id", "=", splitter.node_id.id),
                ("input_fiber_id", "=", splitter.input_fiber_id.id),
            ])
            if other_splitter:
                raise ValidationError("La fibra de entrada ya alimenta otro splitter en este elemento.")
            other_output = output_model.search_count([
                ("splitter_id.node_id", "=", splitter.node_id.id),
                ("splitter_id", "!=", splitter.id),
                ("output_fiber_id", "=", splitter.input_fiber_id.id),
            ])
            if other_output:
                raise ValidationError("La fibra de entrada ya est\u00e1 conectada a la salida de otro splitter.")
            tray_conflict = tray_line_model.search_count([
                ("node_id", "=", splitter.node_id.id),
                ("splitter_id", "!=", splitter.id),
                "|",
                ("input_fiber_id", "=", splitter.input_fiber_id.id),
                ("output_fiber_id", "=", splitter.input_fiber_id.id),
            ])
            if tray_conflict:
                raise ValidationError(
                    "La fibra de entrada ya est\u00e1 registrada en otra operaci\u00f3n de bandeja."
                )

    @api.model_create_multi
    def create(self, vals_list):
        """Crea los registros y prepara sus relaciones o datos derivados antes de devolverlos."""
        for values in vals_list:
            values.setdefault("employee_id", work_employee_id(self.env))
            values.setdefault("work_date", fields.Datetime.now())
            if values.get("input_output_id"):
                self.env["fiber.gis.splitter.output"].browse(values["input_output_id"])._lock_connection()
            tray = self.env["fiber.gis.tray"].browse(values.get("tray_id")).exists()
            ratio = values.get("ratio") or "1:8"
            if "nominal_loss_db" not in values:
                values["nominal_loss_db"] = splitter_default_loss_db(ratio)
            if tray:
                values["node_id"] = tray.node_id.id
            if not values.get("name") or values.get("name") == "Splitter":
                tray_name = tray.display_name if tray else "Bandeja"
                values["name"] = f"Splitter {ratio} - {tray_name}"
        splitters = super().create(vals_list)
        splitters._sync_output_ports()
        splitters._sync_tray_lines()
        splitters.mapped("input_output_id")._sync_connection_state()
        for splitter in splitters:
            splitter.node_id._log_work("tray", "Splitter instalado en bandeja.", employee_id=splitter.employee_id.id)
        return splitters

    def write(self, vals):
        """Actualiza los registros y mantiene coherentes sus campos y relaciones dependientes."""
        vals = dict(vals)
        work_fields = {"tray_id", "input_fiber_id", "input_output_id", "ratio", "nominal_loss_db", "notes", "employee_id"}
        if work_fields.intersection(vals):
            vals.setdefault("employee_id", work_employee_id(self.env))
            vals.setdefault("work_date", fields.Datetime.now())
        if "input_output_id" in vals:
            sources = self.mapped("input_output_id")
            if vals["input_output_id"]:
                sources |= self.env["fiber.gis.splitter.output"].browse(vals["input_output_id"])
            sources._lock_connection()
        if "ratio" in vals and "nominal_loss_db" not in vals:
            vals["nominal_loss_db"] = splitter_default_loss_db(vals["ratio"])
        if vals.get("tray_id"):
            tray = self.env["fiber.gis.tray"].browse(vals["tray_id"]).exists()
            if tray:
                vals["node_id"] = tray.node_id.id
        if "ratio" in vals:
            desired_count = splitter_output_count(vals["ratio"])
            for splitter in self:
                occupied_excess = splitter.output_ids.filtered(
                    lambda output: output.sequence > desired_count and output.is_connected
                )
                if occupied_excess:
                    raise UserError(
                        "No se puede reducir la relaci\u00f3n mientras haya salidas superiores ocupadas."
                    )
        old_fibers = self.mapped("input_fiber_id")
        old_outputs = self.mapped("input_output_id")
        result = super().write(vals)
        if "ratio" in vals:
            self._sync_output_ports()
        if {"tray_id", "input_fiber_id", "input_output_id", "ratio", "nominal_loss_db", "employee_id"}.intersection(vals):
            self._sync_tray_lines()
        (old_outputs | self.mapped("input_output_id"))._sync_connection_state()
        (old_fibers | self.mapped("input_fiber_id"))._recompute_tray_state()
        if work_fields.intersection(vals):
            for splitter in self:
                splitter.node_id._log_work("tray", "Splitter modificado.", employee_id=splitter.employee_id.id)
        return result

    @api.model
    def action_fill_missing_nominal_losses(self):
        """Ejecuta la acción de usuario «completar pendiente nominal pérdidas» y devuelve el resultado correspondiente a Odoo."""
        for ratio, loss_db in SPLITTER_DEFAULT_LOSS_DB.items():
            self.search([
                ("ratio", "=", ratio),
                ("nominal_loss_db", "=", 0.0),
            ]).write({"nominal_loss_db": loss_db})
        return True

    def unlink(self):
        """Elimina los registros aplicando las comprobaciones y limpiezas necesarias en sus relaciones."""
        fibers = self.mapped("input_fiber_id") | self.mapped("output_ids.output_fiber_id")
        nodes = self.mapped("node_id")
        upstream = self.mapped("input_output_id")
        if not self.env.context.get("skip_tray_line_unlink"):
            self.mapped("tray_line_ids").with_context(skip_splitter_unlink=True).unlink()
        result = super().unlink()
        upstream.exists()._sync_connection_state()
        fibers._recompute_tray_state()
        nodes._log_work("tray", "Splitter borrado de bandeja.")
        return result

    def action_sync_outputs(self):
        """Ejecuta la acción de usuario «sincronización salidas» y devuelve el resultado correspondiente a Odoo."""
        self._sync_output_ports()
        self._sync_tray_lines()
        self.mapped("output_ids")._sync_drop_cable_colors()
        return True

    def action_connect_customer_drop(self):
        """Ejecuta la acción de usuario «conexión cliente acometida» y devuelve el resultado correspondiente a Odoo."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Conectar acometida de cliente",
            "res_model": "fiber.gis.splitter.drop.wizard",
            "view_mode": "form",
            "view_id": self.env.ref("fiber_gis.view_fiber_gis_splitter_drop_wizard_form").id,
            "target": "new",
            "context": {
                "default_splitter_id": self.id,
            },
        }

    def action_open_form(self):
        """Abre el formulario del registro relacionado."""
        self.ensure_one()
        self.check_access("read")
        view_id = self.env.ref("fiber_gis.view_fiber_gis_splitter_form").id
        return {
            "type": "ir.actions.act_window", "name": self.display_name,
            "res_model": self._name, "res_id": self.id, "view_mode": "form", "target": "new",
            "views": [(view_id, "form")],
        }

    def _upstream_fiber(self):
        """Recorre la cascada local sin inventar cables entre splitters."""
        self.ensure_one()
        chain, has_cycle = splitter_upstream_chain(self)
        if has_cycle:
            raise UserError("Se ha detectado un circuito cerrado entre splitters.")
        path = []
        for current in chain:
            path.append(current.display_name)
            if current.input_fiber_id:
                return current.input_fiber_id, path
            source = current.input_output_id
            if source:
                path.append(f"salida {source.sequence}")
        return self.env["fiber.gis.cable.fiber"], path

    def _connected_cables(self):
        """Obtiene los cables que llegan o salen de las conexiones del splitter."""
        self.ensure_one()
        return self.env["fiber.gis.cable"].search([
            "|",
            ("from_node_id", "=", self.node_id.id),
            ("to_node_id", "=", self.node_id.id),
        ])

    def _customer_drop_cables(self):
        """Obtiene los cables de acometida asociados a las salidas conectadas a clientes."""
        self.ensure_one()
        return self._connected_cables().filtered(
            lambda cable: cable.type_id.code == "CABLE_DROP"
        )

    def _connect_output_fiber(self, output, fiber, notes=None):
        """Conecta la fibra elegida con la salida del splitter y actualiza sus registros asociados."""
        self.ensure_one()
        output = output.exists()
        fiber = fiber.exists()
        if not output or output.splitter_id != self:
            raise UserError("La salida seleccionada no pertenece a este splitter.")
        output._lock_connection()
        if output.state != "free" or output.is_connected:
            raise UserError("La salida del splitter ya est\u00e1 ocupada.")
        if not fiber or fiber.cable_id not in self._connected_cables():
            raise UserError("La fibra debe pertenecer a un cable conectado al elemento.")
        output.write({
            "output_fiber_id": fiber.id,
            "state": "connected",
            "notes": notes or output.notes,
        })
        return output

    def _connect_customer_drop(self, output, drop_fiber, notes=None):
        """Asocia una salida del splitter a la acometida y al cliente seleccionados."""
        self.ensure_one()
        drop_fiber = drop_fiber.exists()
        if not drop_fiber or drop_fiber.cable_id not in self._customer_drop_cables():
            raise UserError("La fibra debe pertenecer a una acometida conectada al elemento.")
        output = self._connect_output_fiber(output, drop_fiber, notes)
        self.node_id._log_work(
            "tray",
            f"{self.display_name}, salida {output.sequence}, conectada a la fibra "
            f"{drop_fiber.number} de la acometida {drop_fiber.cable_id.display_name}.",
        )
        return output

    def _available_fibers(self):
        """Devuelve las fibras disponibles que pueden conectarse al splitter."""
        self.ensure_one()
        cables = self._connected_cables()
        for cable in cables.filtered(lambda item: not item.fiber_ids):
            cable.action_generate_fibers()
        return cables.mapped("fiber_ids")

    def _sync_output_ports(self):
        """Sincroniza «salida puertos» entre los registros relacionados y evita duplicar los datos existentes."""
        output_model = self.env["fiber.gis.splitter.output"]
        for splitter in self:
            desired_count = splitter_output_count(splitter.ratio)
            existing_by_sequence = {output.sequence: output for output in splitter.output_ids}
            values = []
            for sequence in range(1, desired_count + 1):
                if sequence not in existing_by_sequence:
                    values.append({
                        "splitter_id": splitter.id,
                        "sequence": sequence,
                    })
            if values:
                output_model.create(values)
            excess = splitter.output_ids.filtered(lambda output: output.sequence > desired_count)
            occupied_excess = excess.filtered("is_connected")
            if occupied_excess:
                raise UserError("Hay salidas ocupadas fuera de la nueva relaci\u00f3n del splitter.")
            excess.unlink()

    def _sync_tray_lines(self):
        """Sincroniza «bandeja líneas» entre los registros relacionados y evita duplicar los datos existentes."""
        line_model = self.env["fiber.gis.tray.line"]
        for splitter in self:
            values = {
                "tray_id": splitter.tray_id.id,
                "line_type": "splitter",
                "input_fiber_id": splitter.input_fiber_id.id,
                "output_fiber_id": False,
                "splitter_ratio": splitter.ratio,
                "loss_db": splitter.nominal_loss_db,
                "splitter_id": splitter.id,
                "employee_id": splitter.employee_id.id or False,
                "work_date": splitter.work_date,
            }
            line = splitter.tray_line_ids[:1]
            if line:
                if line.tray_id != splitter.tray_id:
                    values["position"] = max(splitter.tray_id.line_ids.mapped("position") or [0]) + 1
                line.with_context(skip_splitter_sync=True).write(values)
                splitter.tray_line_ids[1:].with_context(skip_splitter_unlink=True).unlink()
            else:
                values["position"] = (
                    max(splitter.tray_id.line_ids.mapped("position"))
                    if splitter.tray_id.line_ids
                    else 0
                ) + 1
                line_model.with_context(skip_splitter_sync=True).create(values)

    def _build_diagram_html(self):
        """Construye «diagrama HTML» con los datos del modelo para mostrarlo o imprimirlo."""
        self.ensure_one()
        input_html = self._fiber_html(
            self.input_fiber_id,
            self._fiber_remote_label(self.input_fiber_id),
        )
        if self.input_output_id:
            source = self.input_output_id
            input_html = (
                f"<span class='o_fiber_splitter_fiber is-cascade'><b>{html.escape(source.splitter_id.display_name)}</b>"
                f"<span>Salida {source.sequence} - {html.escape(source.splitter_id.tray_id.display_name)}</span></span>"
            )
        outputs = []
        for output in self.output_ids.sorted("sequence"):
            if output.downstream_splitter_ids:
                child = output.downstream_splitter_ids[:1]
                endpoint = (
                    f"<span class='o_fiber_splitter_fiber is-cascade'><b>{html.escape(child.display_name)}</b>"
                    f"<em>{html.escape(child.tray_id.display_name)} - {html.escape(child.ratio)}</em></span>"
                )
                status_class = "is-connected"
            elif output.output_fiber_id:
                endpoint = self._fiber_html(output.output_fiber_id, output.destination_label)
                status_class = "is-connected"
            else:
                label = dict(output._fields["state"].selection).get(output.state, "Libre")
                endpoint = f"<span class='o_fiber_splitter_free'>{html.escape(label)}</span>"
                status_class = "is-free"
            outputs.append(
                f"<button type='button' class='o_fiber_splitter_output {status_class}' data-output-id='{output.id}' title='Gestionar salida {output.sequence}'>"
                f"<strong>{output.sequence}</strong>"
                "<span class='o_fiber_splitter_branch'></span>"
                f"{endpoint}"
                "</button>"
            )
        return (
            f"<div class='o_fiber_splitter_diagram' data-splitter-id='{self.id}'>"
            f"<div class='o_fiber_splitter_input'>{input_html}</div>"
            "<div class='o_fiber_splitter_link'></div>"
            "<div class='o_fiber_splitter_body'>"
            f"<strong>{html.escape(self.name or 'Splitter')}</strong>"
            f"<span>{html.escape(self.ratio or '')}</span>"
            f"<small>{self.connected_output_count}/{self.output_count} ocupadas</small>"
            "</div>"
            f"<div class='o_fiber_splitter_outputs'>{''.join(outputs)}</div>"
            "</div>"
        )

    def _fiber_html(self, fiber, endpoint_label):
        """Construye el fragmento HTML que representa una fibra y el extremo al que llega."""
        if not fiber:
            return "<span class='o_fiber_splitter_free'>Sin fibra</span>"
        parts = []
        if fiber.tube:
            parts.append(
                "<span class='o_fiber_splitter_identity'>"
                f"<i style='background:{html.escape(fiber.tube_color or '#ffffff')}'></i>"
                f"T{fiber.tube}"
                "</span>"
            )
        parts.append(
            "<span class='o_fiber_splitter_identity'>"
            f"<i style='background:{html.escape(fiber.color or '#ffffff')}'></i>"
            f"F{fiber.number}"
            "</span>"
        )
        cable = html.escape(fiber.cable_id.display_name or "")
        endpoint = html.escape(endpoint_label or "")
        return (
            "<span class='o_fiber_splitter_fiber'>"
            f"<span class='o_fiber_splitter_identities'>{''.join(parts)}</span>"
            f"<b>{cable}</b>"
            f"<em title='{endpoint}'>{endpoint}</em>"
            "</span>"
        )

    def _fiber_remote_label(self, fiber):
        """Forma el texto identificativo del cable, fibra y elemento remoto conectado."""
        self.ensure_one()
        if not fiber or not self.node_id:
            return ""
        cable = fiber.cable_id
        endpoint = cable.to_node_id if cable.from_node_id == self.node_id else cable.from_node_id
        if not endpoint:
            return ""
        label = endpoint.display_name or endpoint.name or endpoint.code or "Elemento"
        return f"{label} - {endpoint.address}" if endpoint.address else label


class FiberGisSplitterOutput(models.Model):
    _name = "fiber.gis.splitter.output"
    _description = "Salida de splitter \u00f3ptico"
    _order = "splitter_id, sequence, id"

    splitter_id = fields.Many2one(
        "fiber.gis.splitter",
        string="Splitter",
        required=True,
        ondelete="cascade",
    )
    node_id = fields.Many2one(
        "fiber.gis.node",
        related="splitter_id.node_id",
        string="Elemento",
        store=True,
    )
    sequence = fields.Integer(string="Salida", required=True)
    port_color = fields.Char(
        string="Color de la boca",
        compute="_compute_port_color",
        store=True,
    )
    name = fields.Char(string="Puerto", compute="_compute_name", store=True)
    available_fiber_ids = fields.Many2many(
        "fiber.gis.cable.fiber",
        string="Fibras disponibles",
        compute="_compute_available_fiber_ids",
    )
    output_fiber_id = fields.Many2one(
        "fiber.gis.cable.fiber",
        string="Fibra conectada",
    )
    downstream_splitter_ids = fields.One2many(
        "fiber.gis.splitter", "input_output_id", string="Splitter conectado",
        context={"active_test": False},
    )
    is_connected = fields.Boolean(string="Ocupada", compute="_compute_is_connected")
    output_cable_id = fields.Many2one(
        "fiber.gis.cable",
        related="output_fiber_id.cable_id",
        string="Cable de salida",
        store=True,
    )
    output_tube = fields.Integer(related="output_fiber_id.tube", string="Tubo")
    output_tube_color = fields.Char(related="output_fiber_id.tube_color", string="Color del tubo")
    output_fiber_number = fields.Integer(related="output_fiber_id.number", string="Fibra")
    output_fiber_color = fields.Char(related="output_fiber_id.color", string="Color de la fibra")
    destination_label = fields.Char(string="Destino", compute="_compute_destination_label", store=True)
    state = fields.Selection(
        [
            ("free", "Libre"),
            ("reserved", "Reservada"),
            ("connected", "Conectada"),
            ("fault", "Incidencia"),
        ],
        string="Estado",
        default="free",
        required=True,
    )
    loss_db = fields.Float(string="P\u00e9rdida adicional (dB)")
    notes = fields.Char(string="Observaciones")
    employee_id = fields.Many2one("hr.employee.public", string="T\u00e9cnico")
    work_date = fields.Datetime(string="Fecha del trabajo")

    _splitter_output_sequence_unique = models.Constraint(
        "UNIQUE(splitter_id, sequence)",
        "El n\u00famero de salida debe ser \u00fanico dentro del splitter.",
    )

    @api.depends("output_fiber_id", "downstream_splitter_ids")
    def _compute_is_connected(self):
        """Calcula y actualiza «es conectado» a partir de los datos actuales y sus relaciones."""
        for output in self:
            output.is_connected = bool(output.output_fiber_id or output.downstream_splitter_ids)

    def _lock_connection(self):
        """Serializa la ocupacion de salidas y las cascadas del mismo elemento."""
        self.check_access("write")
        if not self:
            return
        for node_id in sorted(set(self.mapped("node_id").ids)):
            self.env.cr.execute("SELECT pg_advisory_xact_lock(%s, %s)", (934034, node_id))
        self.env["fiber.gis.splitter"].invalidate_model(["input_output_id"])
        self.env.cr.execute(
            "SELECT id FROM fiber_gis_splitter_output WHERE id IN %s ORDER BY id FOR UPDATE",
            (tuple(self.ids),),
        )
        self.invalidate_recordset(["output_fiber_id", "state", "downstream_splitter_ids", "is_connected"])

    def _sync_connection_state(self):
        """Sincroniza «conexión estado» entre los registros relacionados y evita duplicar los datos existentes."""
        for output in self:
            output.invalidate_recordset(["downstream_splitter_ids", "is_connected"])
            if output.is_connected and output.state == "free":
                output.write({"state": "connected"})
            elif not output.is_connected and output.state == "connected":
                output.write({"state": "free"})

    def action_manage_connection(self):
        """Ejecuta la acción de usuario «gestión conexión» y devuelve el resultado correspondiente a Odoo."""
        self.ensure_one()
        self.check_access("read")
        view_id = self.env.ref("fiber_gis.view_fiber_gis_splitter_drop_wizard_form").id
        return {
            "type": "ir.actions.act_window", "name": f"Gestionar salida {self.sequence}",
            "res_model": "fiber.gis.splitter.drop.wizard", "view_mode": "form", "target": "new",
            "view_id": view_id, "views": [(view_id, "form")],
            "context": {"default_splitter_id": self.splitter_id.id, "default_output_id": self.id,
                        "default_operation": False, "fiber_gis_fixed_output": True},
        }

    def _disconnect(self):
        """Elimina la conexión de la salida y sincroniza los registros de bandeja y puerto relacionados."""
        self._lock_connection()
        for output in self:
            output.downstream_splitter_ids.write({"input_output_id": False})
            output.write({"output_fiber_id": False, "state": "free"})
            output.node_id._log_work("tray", f"Desconectada {output.display_name}.")

    @api.depends("splitter_id", "sequence")
    def _compute_name(self):
        """Calcula y actualiza «nombre» a partir de los datos actuales y sus relaciones."""
        for output in self:
            output.name = f"{output.splitter_id.display_name or 'Splitter'} / salida {output.sequence}"

    @api.depends("sequence")
    def _compute_port_color(self):
        """Calcula y actualiza «puerto color» a partir de los datos actuales y sus relaciones."""
        fiber_model = self.env["fiber.gis.cable.fiber"]
        for output in self:
            output.port_color = fiber_model.fiber_color(output.sequence)

    def _sync_drop_cable_colors(self):
        """Aplica el color de la boca a las acometidas conectadas."""
        fiber_model = self.env["fiber.gis.cable.fiber"]
        for output in self.filtered("output_fiber_id"):
            cable = output.output_fiber_id.cable_id
            if cable.type_id.code != "CABLE_DROP":
                continue
            color = fiber_model.fiber_color(output.sequence)
            if cable.color != color:
                cable.write({"color": color})
        return True

    @api.model
    def action_sync_all_drop_cable_colors(self):
        """Ejecuta la acción de usuario «sincronización todos acometida cable colores» y devuelve el resultado correspondiente a Odoo."""
        outputs = self.search([("output_fiber_id", "!=", False)])
        outputs._sync_drop_cable_colors()
        return True

    @api.depends("splitter_id.node_id", "splitter_id.node_id.incoming_cable_ids.fiber_ids", "splitter_id.node_id.outgoing_cable_ids.fiber_ids")
    def _compute_available_fiber_ids(self):
        """Actualiza las listas de fibras disponibles para los cables elegidos."""
        empty = self.env["fiber.gis.cable.fiber"]
        fibers_by_splitter = {}
        for output in self:
            splitter = output.splitter_id
            if not splitter.node_id:
                output.available_fiber_ids = empty
                continue
            if splitter.id not in fibers_by_splitter:
                fibers_by_splitter[splitter.id] = splitter._available_fibers()
            output.available_fiber_ids = fibers_by_splitter[splitter.id]

    @api.depends(
        "output_fiber_id",
        "output_fiber_id.cable_id.from_node_id",
        "output_fiber_id.cable_id.from_node_id.name",
        "output_fiber_id.cable_id.from_node_id.code",
        "output_fiber_id.cable_id.to_node_id",
        "output_fiber_id.cable_id.to_node_id.name",
        "output_fiber_id.cable_id.to_node_id.code",
        "output_fiber_id.cable_id.from_node_id.address",
        "output_fiber_id.cable_id.to_node_id.address",
        "splitter_id.node_id",
        "downstream_splitter_ids.name",
        "downstream_splitter_ids.tray_id",
    )
    def _compute_destination_label(self):
        """Calcula y actualiza «destino etiqueta» a partir de los datos actuales y sus relaciones."""
        for output in self:
            if output.downstream_splitter_ids:
                child = output.downstream_splitter_ids[:1]
                output.destination_label = f"{child.display_name} - {child.tray_id.display_name}"
                continue
            fiber = output.output_fiber_id
            node = output.splitter_id.node_id
            if not fiber or not node:
                output.destination_label = ""
                continue
            output.destination_label = output.splitter_id._fiber_remote_label(fiber)

    @api.onchange("output_fiber_id")
    def _onchange_output_fiber_id(self):
        """Recalcula los campos del formulario al cambiar «salida fibra identificador», antes de guardar el registro."""
        for output in self:
            if output.output_fiber_id and output.state == "free":
                output.state = "connected"
            elif not output.output_fiber_id and output.state == "connected":
                output.state = "free"

    @api.constrains("splitter_id", "output_fiber_id")
    def _check_output_fiber(self):
        """Valida «salida fibra» antes de guardar y rechaza los datos que incumplen las reglas del modelo."""
        tray_line_model = self.env["fiber.gis.tray.line"]
        for output in self:
            fiber = output.output_fiber_id
            splitter = output.splitter_id
            if not fiber:
                continue
            if output.downstream_splitter_ids:
                raise ValidationError("La salida ya alimenta otro splitter.")
            if fiber == splitter.input_fiber_id:
                raise ValidationError("La entrada del splitter no puede usarse tambi\u00e9n como salida.")
            if fiber.cable_id not in splitter._connected_cables():
                raise ValidationError(
                    "La fibra de salida debe pertenecer a un cable conectado al elemento."
                )
            duplicate = self.search_count([
                ("id", "!=", output.id),
                ("splitter_id.node_id", "=", splitter.node_id.id),
                ("output_fiber_id", "=", fiber.id),
            ])
            if duplicate:
                raise ValidationError("La fibra ya est\u00e1 conectada a otra salida de splitter.")
            input_conflict = self.env["fiber.gis.splitter"].search_count([
                ("id", "!=", splitter.id),
                ("node_id", "=", splitter.node_id.id),
                ("input_fiber_id", "=", fiber.id),
            ])
            if input_conflict:
                raise ValidationError("La fibra ya alimenta otro splitter en este elemento.")
            tray_conflict = tray_line_model.search_count([
                ("node_id", "=", splitter.node_id.id),
                "|",
                ("input_fiber_id", "=", fiber.id),
                ("output_fiber_id", "=", fiber.id),
            ])
            if tray_conflict:
                raise ValidationError(
                    "La fibra ya est\u00e1 registrada en una operaci\u00f3n de bandeja."
                )

    @api.model_create_multi
    def create(self, vals_list):
        """Crea los registros y prepara sus relaciones o datos derivados antes de devolverlos."""
        for values in vals_list:
            if values.get("output_fiber_id"):
                values.setdefault("employee_id", work_employee_id(self.env))
                values.setdefault("work_date", fields.Datetime.now())
            if values.get("output_fiber_id") and not values.get("state"):
                values["state"] = "connected"
        outputs = super().create(vals_list)
        outputs.mapped("output_fiber_id")._recompute_tray_state()
        outputs._sync_drop_cable_colors()
        return outputs

    def write(self, vals):
        """Actualiza los registros y mantiene coherentes sus campos y relaciones dependientes."""
        vals = dict(vals)
        if {"output_fiber_id", "state", "notes", "loss_db", "employee_id"}.intersection(vals):
            vals.setdefault("employee_id", work_employee_id(self.env))
            vals.setdefault("work_date", fields.Datetime.now())
        if "output_fiber_id" in vals and "state" not in vals:
            vals = dict(vals, state="connected" if vals["output_fiber_id"] else "free")
        if {"output_fiber_id", "state"}.intersection(vals):
            self._lock_connection()
            if vals.get("state") == "free" and self.mapped("downstream_splitter_ids"):
                raise ValidationError("Desconecta el splitter de destino antes de liberar esta salida.")
            if vals.get("state") == "free" and any(output.is_connected for output in self) and vals.get("output_fiber_id") is not False:
                raise ValidationError("Desconecta la salida antes de marcarla como libre.")
        old_fibers = self.mapped("output_fiber_id")
        result = super().write(vals)
        (old_fibers | self.mapped("output_fiber_id"))._recompute_tray_state()
        if {"output_fiber_id", "sequence"}.intersection(vals):
            self._sync_drop_cable_colors()
        if {"output_fiber_id", "state", "notes", "loss_db", "employee_id"}.intersection(vals):
            for output in self:
                output.node_id._log_work("tray", f"Salida {output.sequence} de {output.splitter_id.display_name} modificada.", employee_id=output.employee_id.id)
        return result

    def unlink(self):
        """Elimina los registros aplicando las comprobaciones y limpiezas necesarias en sus relaciones."""
        fibers = self.mapped("output_fiber_id")
        result = super().unlink()
        fibers._recompute_tray_state()
        return result
