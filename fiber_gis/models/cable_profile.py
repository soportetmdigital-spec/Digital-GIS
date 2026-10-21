"""Catalogo de construcciones de cable, independiente de su uso GIS."""
from odoo import api, fields, models


class FiberGisCableProfile(models.Model):
    _name = "fiber.gis.cable.profile"
    _description = "Tipolog\u00eda de cable"
    _order = "name, id"

    name = fields.Char(string="Nombre", required=True)
    gis_type_id = fields.Many2one(
        "fiber.gis.asset.type",
        string="Tipo GIS",
        domain=[("category", "=", "cable"), ("active", "=", True)],
        ondelete="restrict",
    )
    tube_count = fields.Integer(string="N.\u00ba de tubos", default=0, required=True)
    fiber_count = fields.Integer(
        string="N.\u00ba de fibras", default=12, required=True,
        help="Con tubos: fibras por tubo. Sin tubos: numero total de fibras.",
    )
    total_fiber_count = fields.Integer(string="Total de fibras", compute="_compute_total", store=True)
    active = fields.Boolean(default=True)
    _counts_valid = models.Constraint("CHECK(tube_count >= 0 AND fiber_count > 0)", "Indica fibras positivas y cero o mas tubos.")

    def name_get(self):
        """Devuelve el nombre legible que se muestra en los campos relacionales de Odoo."""
        return [
            (profile.id, "%s - Tipo GIS: %s" % (
                profile.name,
                profile.gis_type_id.name if profile.gis_type_id else "Sin definir",
            ))
            for profile in self
        ]

    @api.depends("tube_count", "fiber_count")
    def _compute_total(self):
        """Calcula y actualiza «total» a partir de los datos actuales y sus relaciones."""
        for profile in self:
            profile.total_fiber_count = profile.fiber_count * (profile.tube_count or 1)

    def write(self, values):
        """Actualiza los registros y mantiene coherentes sus campos y relaciones dependientes."""
        result = super().write(values)
        if {"tube_count", "fiber_count"}.intersection(values):
            # Los cables conservan sus fibras y conexiones. Una reduccion incompatible se rechaza.
            for profile in self:
                self.env["fiber.gis.cable"].with_context(active_test=False).search([
                    ("profile_id", "=", profile.id),
                ]).write({"fiber_count": profile.fiber_count, "tube_count": profile.tube_count})
        return result
