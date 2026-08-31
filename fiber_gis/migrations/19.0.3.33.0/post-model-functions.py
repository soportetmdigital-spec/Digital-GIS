"""Conserva las relaciones anteriores al separar modelo y funcion."""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["fiber.gis.node.category"]._initialize_model_functions()
