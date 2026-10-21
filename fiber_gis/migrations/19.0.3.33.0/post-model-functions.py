"""Conserva las relaciones anteriores al separar modelo y funcion."""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Migra los datos existentes a la estructura de esta versión, conservando las relaciones y valores válidos."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["fiber.gis.node.category"]._initialize_model_functions()
