"""Registros de trabajos realizados sobre elementos y bandejas."""

from odoo import api, fields, models


def work_employee_id(env):
    """Solo directorio publico: no concede acceso a expedientes privados de RR. HH."""
    employees = env["hr.employee.public"]
    if "fiber_gis_employee_id" in env.context:
        employee = employees.browse(env.context["fiber_gis_employee_id"]).exists()
        if employee:
            employee.check_access("read")
        return employee.id or False
    employees = employees.search([("user_id", "=", env.uid), ("company_id", "=", env.company.id)], limit=2)
    return employees.id if len(employees) == 1 else False


class FiberGisNodeWorkLog(models.Model):
    _name = "fiber.gis.node.work.log"
    _description = "Registro de trabajos en elemento"
    _order = "date desc, id desc"

    node_id = fields.Many2one("fiber.gis.node", string="Elemento", ondelete="set null")
    node_name = fields.Char(string="Nombre del elemento")
    date = fields.Datetime(string="Fecha", default=fields.Datetime.now, required=True)
    user_id = fields.Many2one("res.users", string="Registrado por", default=lambda self: self.env.user, required=True)
    employee_id = fields.Many2one("hr.employee.public", string="T\u00e9cnico")
    employee_name = fields.Char(string="Nombre del tecnico registrado", readonly=True)
    work_type = fields.Selection(
        [
            ("manual", "Trabajo manual"),
            ("element", "Modificacion de elemento"),
            ("tray", "Bandeja"),
            ("delete", "Borrado"),
        ],
        string="Tipo de trabajo",
        default="manual",
        required=True,
    )
    description = fields.Text(string="Descripcion")

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            employee_id = values["employee_id"] if "employee_id" in values else work_employee_id(self.env)
            employee = self.env["hr.employee.public"].browse(employee_id).exists()
            values.setdefault("employee_id", employee.id or False)
            values.setdefault("employee_name", employee.name if employee else False)
        return super().create(vals_list)

    def write(self, values):
        values = dict(values)
        if "employee_id" in values:
            employee = self.env["hr.employee.public"].browse(values["employee_id"]).exists()
            values["employee_name"] = employee.name if employee else False
        return super().write(values)
