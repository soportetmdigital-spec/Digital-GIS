"""Enlaces l\u00f3gicos de servicio que usan fibras de la red."""

from odoo import fields, models


class FiberGisLogicalLink(models.Model):
    _name = "fiber.gis.logical.link"
    _description = "Enlace l\u00f3gico sobre fibra"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(string="Nombre", tracking=True)
    code = fields.Char(string="Matricula", tracking=True)
    customer_id = fields.Many2one("res.partner", string="Cliente")
    from_node_id = fields.Many2one("fiber.gis.node", required=True, string="Origen")
    to_node_id = fields.Many2one("fiber.gis.node", required=True, string="Destino")
    fiber_ids = fields.Many2many("fiber.gis.cable.fiber", string="Fibras usadas")
    service_type = fields.Selection(
        [
            ("backbone", "Backbone"),
            ("ftth", "FTTH"),
            ("enterprise", "Empresa"),
            ("transport", "Transporte"),
            ("other", "Otro"),
        ],
        default="ftth",
        required=True,
    )
    state = fields.Selection(
        [
            ("planned", "Planificado"),
            ("active", "Activo"),
            ("maintenance", "Mantenimiento"),
            ("down", "Ca\u00eddo"),
            ("retired", "Retirado"),
        ],
        default="planned",
        required=True,
        tracking=True,
    )
    notes = fields.Text(string="Notas")

    _logical_link_code_unique = models.Constraint(
        "UNIQUE(code)",
        "La matricula del enlace debe ser unica.",
    )
