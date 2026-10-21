"""Tipos maestros usados para clasificar elementos, cables y fibras."""

from odoo import fields, models


class FiberGisAssetType(models.Model):
    _name = "fiber.gis.asset.type"
    _description = "Tipo de elemento de fibra"
    _order = "sequence, name"

    name = fields.Char(string="Nombre", required=True, translate=True)
    code = fields.Char(string="C\u00f3digo", required=True)
    category = fields.Selection(
        [
            ("node", "Equipo o punto"),
            ("cable", "Cable"),
            ("fiber", "Fibra"),
        ],
        required=True,
        default="node",
    )
    sequence = fields.Integer(string="Secuencia", default=10)
    color = fields.Char(default="#2f80ed")
    active = fields.Boolean(string="Activo", default=True)
    node_category_ids = fields.Many2many(
        "fiber.gis.node.category", "fiber_gis_model_function_rel",
        "type_id", "node_category_id", string="Modelos compatibles",
    )

    _code_unique = models.Constraint(
        "UNIQUE(code)",
        "El c\u00f3digo del tipo debe ser \u00fanico.",
    )
