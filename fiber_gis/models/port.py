"""Puertos f\u00edsicos o l\u00f3gicos dentro de los equipos de fibra."""

from odoo import api, fields, models
from .work_log import work_employee_id


class FiberGisPort(models.Model):
    _name = "fiber.gis.port"
    _description = "Puerto de equipo de fibra"
    _order = "node_id, sequence, name"

    name = fields.Char(string="Nombre", required=True)
    sequence = fields.Integer(string="Secuencia", default=10)
    node_id = fields.Many2one("fiber.gis.node", required=True, ondelete="cascade")
    port_type = fields.Selection(
        [
            ("fiber", "Fibra"),
            ("pon", "PON"),
            ("ethernet", "Ethernet"),
            ("tray", "Bandeja"),
            ("other", "Otro"),
        ],
        default="fiber",
        required=True,
    )
    direction = fields.Selection(
        [("in", "Entrada"), ("out", "Salida"), ("both", "Bidireccional")],
        default="both",
        required=True,
    )
    status = fields.Selection(
        [
            ("free", "Libre"),
            ("used", "Usado"),
            ("reserved", "Reservado"),
            ("fault", "Averiado"),
        ],
        default="free",
        required=True,
    )
    fiber_id = fields.Many2one("fiber.gis.cable.fiber", string="Fibra")
    notes = fields.Text(string="Notas")
    employee_id = fields.Many2one("hr.employee.public", string="T\u00e9cnico")
    work_date = fields.Datetime(string="Fecha del trabajo")

    @api.model_create_multi
    def create(self, vals_list):
        """Crea los registros y prepara sus relaciones o datos derivados antes de devolverlos."""
        for values in vals_list:
            if values.get("fiber_id"):
                values.setdefault("employee_id", work_employee_id(self.env))
                values.setdefault("work_date", fields.Datetime.now())
        ports = super().create(vals_list)
        for port in ports.filtered("fiber_id"):
            port.node_id._log_work("manual", f"Fibra conectada al puerto {port.name}.", employee_id=port.employee_id.id)
        return ports

    def write(self, values):
        """Actualiza los registros y mantiene coherentes sus campos y relaciones dependientes."""
        values = dict(values)
        work = bool({"fiber_id", "status", "notes", "employee_id"}.intersection(values))
        if work:
            values.setdefault("employee_id", work_employee_id(self.env))
            values.setdefault("work_date", fields.Datetime.now())
        result = super().write(values)
        if work:
            for port in self:
                port.node_id._log_work("manual", f"Puerto {port.name} modificado.", employee_id=port.employee_id.id)
        return result
