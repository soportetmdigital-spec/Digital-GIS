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
    _description = "Registro técnico de elementos GIS"
    _order = "date desc, id desc"

    node_id = fields.Many2one("fiber.gis.node", string="Elemento de red", ondelete="set null", index=True)
    node_name = fields.Char(string="Nombre del elemento")
    site_id = fields.Many2one("fiber.gis.site", string="Sitio", ondelete="set null", index=True)
    site_name = fields.Char(string="Nombre del sitio")
    cable_id = fields.Many2one("fiber.gis.cable", string="Cable", ondelete="set null", index=True)
    cable_name = fields.Char(string="Nombre del cable")
    splitter_id = fields.Many2one("fiber.gis.splitter", string="Splitter", ondelete="set null", index=True)
    splitter_name = fields.Char(string="Nombre del splitter")
    date = fields.Datetime(string="Fecha y hora", default=fields.Datetime.now, required=True)
    user_id = fields.Many2one("res.users", string="Registrado por", default=lambda self: self.env.user, required=True)
    employee_id = fields.Many2one("hr.employee.public", string="T\u00e9cnico")
    employee_name = fields.Char(string="T\u00e9cnico registrado", readonly=True)
    work_type = fields.Selection(
        [
            ("manual", "Trabajo manual"),
            ("element", "Modificaci\u00f3n de elemento"),
            ("tray", "Bandeja"),
            ("delete", "Borrado"),
            ("installation", "Instalaci\u00f3n"),
            ("maintenance", "Mantenimiento"),
            ("repair", "Reparaci\u00f3n"),
            ("inspection", "Revisi\u00f3n"),
        ],
        string="Tipo de trabajo",
        default="manual",
        required=True,
    )
    description = fields.Text(string="Trabajo realizado")

    @api.model
    def _prepare_parent_names(self, values):
        """Guarda el nombre del registro relacionado como referencia permanente del historial."""
        parents = (
            ("node_id", "node_name", "fiber.gis.node"),
            ("site_id", "site_name", "fiber.gis.site"),
            ("cable_id", "cable_name", "fiber.gis.cable"),
            ("splitter_id", "splitter_name", "fiber.gis.splitter"),
        )
        for relation, name_field, model_name in parents:
            if relation not in values or name_field in values:
                continue
            parent = self.env[model_name].browse(values[relation]).exists()
            values[name_field] = parent.display_name if parent else False
        return values

    @api.model_create_multi
    def create(self, vals_list):
        """Crea los registros y prepara sus relaciones o datos derivados antes de devolverlos."""
        for values in vals_list:
            self._prepare_parent_names(values)
            employee_id = values["employee_id"] if "employee_id" in values else work_employee_id(self.env)
            employee = self.env["hr.employee.public"].browse(employee_id).exists()
            values.setdefault("employee_id", employee.id or False)
            values.setdefault("employee_name", employee.name if employee else False)
        return super().create(vals_list)

    def write(self, values):
        """Actualiza los registros y mantiene coherentes sus campos y relaciones dependientes."""
        values = dict(values)
        self._prepare_parent_names(values)
        if "employee_id" in values:
            employee = self.env["hr.employee.public"].browse(values["employee_id"]).exists()
            values["employee_name"] = employee.name if employee else False
        return super().write(values)
