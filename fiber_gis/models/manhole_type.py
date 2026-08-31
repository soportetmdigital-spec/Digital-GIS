"""Catalogo editable de modelos y dimensiones interiores de arquetas."""

from odoo import fields, models


class FiberGisManholeType(models.Model):
    _name = "fiber.gis.manhole.type"
    _description = "Tipo de arqueta de telecomunicaciones"
    _order = "sequence, name"

    sequence = fields.Integer(string="Secuencia", default=10)
    name = fields.Char(string="Modelo", required=True, index=True)
    code = fields.Char(string="C\u00f3digo", required=True, index=True)
    manufacturer = fields.Char(string="Fabricante / familia")
    standard_reference = fields.Char(string="Norma o referencia t\u00e9cnica")
    length_cm = fields.Float(string="Largo interior (cm)", required=True)
    width_cm = fields.Float(string="Ancho interior (cm)", required=True)
    depth_cm = fields.Float(string="Profundidad interior (cm)", required=True)
    usual_use = fields.Char(string="Uso habitual")
    active = fields.Boolean(string="Activo", default=True)
    notes = fields.Text(string="Observaciones")

    _code_unique = models.Constraint(
        "UNIQUE(code)",
        "El c\u00f3digo del tipo de arqueta debe ser \u00fanico.",
    )
    _dimensions_positive = models.Constraint(
        "CHECK(length_cm > 0 AND width_cm > 0 AND depth_cm > 0)",
        "Las tres medidas interiores deben ser mayores que cero.",
    )
