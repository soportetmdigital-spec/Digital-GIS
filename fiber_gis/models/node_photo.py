"""Fotos de instalacion o trabajos realizadas por tecnicos."""

from odoo import fields, models


class FiberGisNodePhoto(models.Model):
    _name = "fiber.gis.node.photo"
    _description = "Foto de elemento"
    _order = "date desc, id desc"

    node_id = fields.Many2one("fiber.gis.node", string="Elemento", required=True, ondelete="cascade")
    image = fields.Image(string="Foto", required=True)
    comment = fields.Text(string="Comentario")
    date = fields.Datetime(string="Fecha", default=fields.Datetime.now, required=True)
    user_id = fields.Many2one("res.users", string="Tecnico", default=lambda self: self.env.user, required=True)
