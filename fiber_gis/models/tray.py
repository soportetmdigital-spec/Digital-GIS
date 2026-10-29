"""Bandejas interiores de cajas, CTO, ODF y equipos de fibra."""

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from .work_log import work_employee_id
from .splitter_options import SPLITTER_RATIO_SELECTION


class FiberGisTray(models.Model):
    _name = "fiber.gis.tray"
    _description = "Bandeja de fibra"
    _order = "node_id, sequence, name"

    name = fields.Char(string="Nombre", required=True, default="Bandeja")
    node_id = fields.Many2one("fiber.gis.node", string="Elemento", required=True, ondelete="cascade")
    sequence = fields.Integer(string="Secuencia", default=10)
    tray_type = fields.Selection(
        [
            ("fusion", "Fusiones"),
            ("splitter", "Splitter"),
            ("reserve", "Reserva de fibras"),
            ("mixed", "Mixta"),
        ],
        string="Uso principal",
        default="mixed",
        required=True,
    )
    capacity = fields.Integer(
        string="Capacidad",
        default=30,
        help="Campo heredado. Las bandejas no tienen límite de trabajos.",
    )
    line_ids = fields.One2many("fiber.gis.tray.line", "tray_id", string="Contenido")
    used_positions = fields.Integer(string="Posiciones usadas", compute="_compute_used_positions")
    free_positions = fields.Integer(string="Posiciones libres", compute="_compute_used_positions")
    notes = fields.Text(string="Observaciones")

    @api.depends("line_ids.line_type")
    def _compute_used_positions(self):
        """Calcula y actualiza «usadas posiciones» a partir de los datos actuales y sus relaciones."""
        for tray in self:
            tray.used_positions = len(tray.line_ids.filtered(
                lambda line: line.line_type not in ("free", "pending_cancel")
            ))
            tray.free_positions = -1

    def unlink(self):
        """Elimina los registros aplicando las comprobaciones y limpiezas necesarias en sus relaciones."""
        fibers = (
            self.mapped("line_ids.input_fiber_id")
            | self.mapped("line_ids.output_fiber_id")
            | self.mapped("line_ids.splitter_id.output_ids.output_fiber_id")
        )
        result = super().unlink()
        fibers._recompute_tray_state()
        return result


class FiberGisTrayLine(models.Model):
    _name = "fiber.gis.tray.line"
    _description = "Posicion de bandeja de fibra"
    _order = "tray_id, position, id"

    tray_id = fields.Many2one("fiber.gis.tray", string="Bandeja", required=True, ondelete="cascade")
    node_id = fields.Many2one("fiber.gis.node", related="tray_id.node_id", string="Elemento", store=True)
    position = fields.Integer(string="Posicion", default=1, required=True)
    line_type = fields.Selection(
        [
            ("free", "Fibra en punta"),
            ("pending_cancel", "Fibra pendiente de anular"),
            ("pass", "Sangría"),
            ("fusion", "Fusion"),
            ("splitter", "Splitter"),
        ],
        string="Tipo",
        default="free",
        required=True,
    )
    input_fiber_id = fields.Many2one("fiber.gis.cable.fiber", string="Fibra entrada")
    output_fiber_id = fields.Many2one("fiber.gis.cable.fiber", string="Fibra salida")
    input_cable_id = fields.Many2one("fiber.gis.cable", related="input_fiber_id.cable_id", string="Cable entrada", store=True)
    output_cable_id = fields.Many2one("fiber.gis.cable", related="output_fiber_id.cable_id", string="Cable salida", store=True)
    input_fiber_number = fields.Integer(related="input_fiber_id.number", string="N. fibra entrada", store=True)
    output_fiber_number = fields.Integer(related="output_fiber_id.number", string="N. fibra salida", store=True)
    input_tube = fields.Integer(related="input_fiber_id.tube", string="Tubo entrada", store=True)
    output_tube = fields.Integer(related="output_fiber_id.tube", string="Tubo salida", store=True)
    input_fiber_color = fields.Char(related="input_fiber_id.color", string="Color entrada")
    output_fiber_color = fields.Char(related="output_fiber_id.color", string="Color salida")
    input_tube_color = fields.Char(related="input_fiber_id.tube_color", string="Color tubo entrada")
    output_tube_color = fields.Char(related="output_fiber_id.tube_color", string="Color tubo salida")
    input_show_tube = fields.Boolean(related="input_fiber_id.show_tube", string="Mostrar tubo entrada")
    output_show_tube = fields.Boolean(related="output_fiber_id.show_tube", string="Mostrar tubo salida")
    splitter_id = fields.Many2one(
        "fiber.gis.splitter",
        string="Splitter",
        ondelete="cascade",
        index=True,
    )
    splitter_ratio = fields.Selection(
        SPLITTER_RATIO_SELECTION,
        string="Relacion splitter",
    )
    loss_db = fields.Float(string="Perdida (dB)")
    work_date = fields.Datetime(string="Fecha", default=fields.Datetime.now)
    technician_id = fields.Many2one("res.users", string="Usuario anterior", default=lambda self: self.env.user)
    employee_id = fields.Many2one("hr.employee.public", string="T\u00e9cnico")
    state = fields.Selection(
        [
            ("planned", "Planificado"),
            ("done", "Realizado"),
            ("fault", "Incidencia"),
        ],
        string="Estado",
        default="done",
        required=True,
    )
    notes = fields.Text(string="Observaciones")

    _tray_position_unique = models.Constraint(
        "UNIQUE(tray_id, position)",
        "La posicion debe ser unica dentro de cada bandeja.",
    )

    def action_open_fiber(self, fiber_id=False):
        """Ejecuta la acción de usuario «apertura fibra» y devuelve el resultado correspondiente a Odoo."""
        self.ensure_one()
        self.check_access("read")
        if self.splitter_id:
            return self.splitter_id.action_open_form()
        fiber = self.env["fiber.gis.cable.fiber"].browse(int(fiber_id)).exists() if fiber_id else self.input_fiber_id
        if not fiber or fiber not in (self.input_fiber_id | self.output_fiber_id):
            raise UserError("La fibra seleccionada ya no pertenece a este registro de bandeja.")
        if self.line_type == "pass":
            view_id = self.env.ref("fiber_gis.view_fiber_gis_tray_form").id
            return {
                "type": "ir.actions.act_window",
                "name": self.tray_id.display_name,
                "res_model": "fiber.gis.tray",
                "res_id": self.tray_id.id,
                "view_mode": "form",
                "views": [(view_id, "form")],
                "target": "current",
            }
        output = self.env["fiber.gis.splitter.output"].search([
            ("node_id", "=", self.node_id.id), ("output_fiber_id", "=", fiber.id),
        ], limit=1)
        if output:
            return output.splitter_id.action_open_form()
        other = self.output_fiber_id if fiber == self.input_fiber_id else self.input_fiber_id
        values = {
            "source_line_id": self.id, "source_fiber_id": fiber.id,
            "node_id": self.node_id.id, "tray_id": self.tray_id.id,
            "cable_id": fiber.cable_id.id, "from_fiber": fiber.number, "to_fiber": fiber.number,
            "operation": (
                "fusion" if self.line_type == "fusion"
                else "pending_cancel" if self.line_type == "pending_cancel"
                else "rest"
            ),
            "selected_fiber_ids": [fields.Command.set(fiber.ids)], "notes": self.notes,
        }
        if self.line_type == "fusion" and other:
            values.update({
                "other_cable_id": other.cable_id.id, "other_tray_id": self.tray_id.id,
                "other_from_fiber": other.number,
                "fusion_input_fiber_ids": [fields.Command.set(fiber.ids)],
                "fusion_output_fiber_ids": [fields.Command.set(other.ids)],
            })
        wizard = self.env["fiber.gis.cable.tray.wizard"].create(values)
        # orm.call devuelve la accion directamente, sin el clean_action de call_button.
        view_id = self.env.ref("fiber_gis.view_fiber_gis_cable_tray_wizard_form").id
        return {
            "type": "ir.actions.act_window", "name": "Asistente Bandejas",
            "res_model": wizard._name, "res_id": wizard.id, "view_mode": "form", "target": "new",
            "views": [(view_id, "form")],
            "context": {"active_model": "fiber.gis.node", "active_id": self.node_id.id},
        }

    @api.model
    def action_move_to_tray(self, line_id, tray_id):
        """Ejecuta la acción de usuario «move destino bandeja» y devuelve el resultado correspondiente a Odoo."""
        line = self.browse(int(line_id)).exists()
        tray = self.env["fiber.gis.tray"].browse(int(tray_id)).exists()
        if not line or not tray:
            raise UserError("No se ha encontrado la fibra o la bandeja de destino.")
        line.check_access("write")
        tray.check_access("read")
        if line.tray_id == tray:
            return True
        if line.node_id != tray.node_id:
            raise UserError("Solo se puede mover dentro del mismo elemento.")
        old_tray = line.tray_id
        old_tray_name = old_tray.display_name
        if line.splitter_id:
            line.splitter_id.write({"tray_id": tray.id})
            description = f"Splitter movido de {old_tray_name} a {tray.display_name}."
        else:
            temporary_position = min(old_tray.line_ids.mapped("position") or [0]) - 1
            line.with_context(skip_fiber_gis_work_log=True).write({"position": temporary_position})
            position = (max(tray.line_ids.mapped("position")) if tray.line_ids else 0) + 1
            line.with_context(skip_fiber_gis_work_log=True).write({"tray_id": tray.id, "position": position})
            description = f"Registro de bandeja movido de {old_tray_name} a {tray.display_name}."
        self._resequence_tray_lines(old_tray | tray)
        line.node_id._log_work("tray", description)
        return True

    @api.model
    def _resequence_tray_lines(self, trays):
        """Reordena cada bandeja por tubo y número de fibra, manteniendo posiciones únicas."""
        self.env.flush_all()
        for tray in trays:
            lines = self.search([("tray_id", "=", tray.id)])
            if not lines:
                continue
            lines.check_access("write")
            ordered = lines.sorted(key=self._logical_fiber_order)
            identifiers = lines.ids
            temporary_offset = max(identifiers, default=0) + 1
            self.env.cr.execute(
                "UPDATE fiber_gis_tray_line SET position = -id - %s WHERE id = ANY(%s)",
                (temporary_offset, identifiers),
            )
            case_sql = " ".join("WHEN %s THEN %s" for _line in ordered)
            parameters = [value for position, line in enumerate(ordered, start=1) for value in (line.id, position)]
            self.env.cr.execute(
                f"UPDATE fiber_gis_tray_line SET position = CASE id {case_sql} ELSE position END "
                "WHERE id = ANY(%s)",
                (*parameters, identifiers),
            )
            lines.invalidate_recordset(["position"])
            lines.modified(["position"])

    def _logical_fiber_order(self, line):
        """Devuelve la clave de orden físico: tubo, fibra y cable para desempatar."""
        fiber = line.input_fiber_id or line.splitter_id.input_fiber_id or line.output_fiber_id
        if not fiber:
            return (1, 0, 0, "", 0, 0, line.id)
        output = line.output_fiber_id
        return (
            0,
            fiber.tube or 0,
            fiber.number or 0,
            (fiber.cable_id.display_name or "").casefold(),
            output.tube or 0,
            output.number or 0,
            line.id,
        )

    @api.model
    def action_delete_visual_line(self, line_id):
        """Ejecuta la acción de usuario «borrado visual línea» y devuelve el resultado correspondiente a Odoo."""
        line = self.browse(int(line_id)).exists()
        if not line:
            raise UserError("No se ha encontrado el registro de bandeja.")
        if line.splitter_id:
            line.splitter_id.unlink()
        else:
            line.unlink()
        return True

    @api.constrains("line_type", "input_fiber_id", "output_fiber_id", "tray_id", "splitter_id")
    def _check_fibers(self):
        """Valida «fibras» antes de guardar y rechaza los datos que incumplen las reglas del modelo."""
        for line in self:
            if line.line_type == "fusion" and not line.input_fiber_id:
                raise ValidationError("Indica la fibra de entrada.")
            if line.line_type == "splitter" and not (line.input_fiber_id or line.splitter_id):
                raise ValidationError("Indica la fibra de entrada o el splitter.")
            if line.line_type == "fusion" and not line.output_fiber_id:
                raise ValidationError("Indica la fibra de salida para una fusion.")
            if line.input_fiber_id and line.input_fiber_id == line.output_fiber_id:
                raise ValidationError("No se puede conectar una fibra consigo misma.")
            if line.line_type == "pass" and line.output_fiber_id and line.input_fiber_id.cable_id == line.output_fiber_id.cable_id:
                raise ValidationError("La continuidad de paso debe enlazar dos tramos de cable distintos.")
            if line.line_type == "pass" and line.output_fiber_id:
                if line.input_fiber_id.cable_id.to_node_id != line.node_id:
                    raise ValidationError("El cable de entrada debe llegar al elemento donde está la bandeja.")
                if line.output_fiber_id.cable_id.from_node_id != line.node_id:
                    raise ValidationError("El cable de salida debe partir del elemento donde está la bandeja.")
            line._check_fiber_not_repeated_in_node(line.input_fiber_id)
            line._check_fiber_not_repeated_in_node(line.output_fiber_id)

    def _check_fiber_not_repeated_in_node(self, fiber):
        """Impide registrar dos veces la misma fibra del mismo cable en un elemento."""
        if not fiber or not self.node_id:
            return
        domain = [
            ("node_id", "=", self.node_id.id),
            ("id", "!=", self.id),
            "|",
            ("input_fiber_id", "=", fiber.id),
            ("output_fiber_id", "=", fiber.id),
        ]
        if self.search_count(domain):
            raise ValidationError(
                f"La fibra {fiber.number} del cable {fiber.cable_id.display_name} ya esta registrada en este elemento."
            )
        own_splitter = self.splitter_id if self.line_type == "splitter" else self.env["fiber.gis.splitter"]
        splitter_domain = [
            ("node_id", "=", self.node_id.id),
            ("id", "not in", own_splitter.ids),
            ("input_fiber_id", "=", fiber.id),
        ]
        output_domain = [
            ("splitter_id.node_id", "=", self.node_id.id),
            ("splitter_id", "not in", own_splitter.ids),
            ("output_fiber_id", "=", fiber.id),
        ]
        if self.env["fiber.gis.splitter"].search_count(splitter_domain) or self.env[
            "fiber.gis.splitter.output"
        ].search_count(output_domain):
            raise ValidationError(
                f"La fibra {fiber.number} del cable {fiber.cable_id.display_name} ya esta usada por un splitter."
            )

    @api.model_create_multi
    def create(self, vals_list):
        """Crea los registros y prepara sus relaciones o datos derivados antes de devolverlos."""
        for values in vals_list:
            if values.get("line_type") == "pass" and not (values.get("input_fiber_id") and values.get("output_fiber_id")):
                raise ValidationError("Una sangría de paso necesita una fibra de entrada y otra de salida.")
            values.setdefault("employee_id", work_employee_id(self.env))
        lines = super().create(vals_list)
        lines._sync_fiber_states()
        for line in lines:
            line.node_id._log_work("tray", "Bandeja modificada.", employee_id=line.employee_id.id)
        return lines

    def write(self, vals):
        """Actualiza los registros y mantiene coherentes sus campos y relaciones dependientes."""
        vals = dict(vals)
        if {"line_type", "input_fiber_id", "output_fiber_id"}.intersection(vals):
            for line in self:
                line_type = vals.get("line_type", line.line_type)
                output_id = vals.get("output_fiber_id", line.output_fiber_id.id)
                input_id = vals.get("input_fiber_id", line.input_fiber_id.id)
                if line_type == "pass" and not (input_id and output_id):
                    raise ValidationError("Una sangría de paso necesita una fibra de entrada y otra de salida.")
        if {"tray_id", "line_type", "input_fiber_id", "output_fiber_id", "loss_db", "notes", "state", "employee_id"}.intersection(vals):
            vals.setdefault("work_date", fields.Datetime.now())
            vals.setdefault("employee_id", work_employee_id(self.env))
        old_fibers = self.mapped("input_fiber_id") | self.mapped("output_fiber_id")
        result = super().write(vals)
        (old_fibers | self.mapped("input_fiber_id") | self.mapped("output_fiber_id"))._recompute_tray_state()
        if vals and not self.env.context.get("skip_fiber_gis_work_log"):
            for line in self:
                line.node_id._log_work("tray", "Bandeja modificada.", employee_id=line.employee_id.id)
        return result

    def unlink(self):
        """Elimina los registros aplicando las comprobaciones y limpiezas necesarias en sus relaciones."""
        fibers = self.mapped("input_fiber_id") | self.mapped("output_fiber_id")
        nodes = self.mapped("node_id")
        splitters = self.mapped("splitter_id")
        result = super().unlink()
        if splitters and not self.env.context.get("skip_splitter_unlink"):
            splitters.with_context(skip_tray_line_unlink=True).unlink()
        fibers._recompute_tray_state()
        nodes._log_work("tray", "Contenido de bandeja borrado.")
        return result

    def _sync_fiber_states(self):
        """Sincroniza «fibra estados» entre los registros relacionados y evita duplicar los datos existentes."""
        (self.mapped("input_fiber_id") | self.mapped("output_fiber_id"))._recompute_tray_state()
