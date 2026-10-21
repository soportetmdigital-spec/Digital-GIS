"""Crea las filas persistentes de la biblioteca de equipos del rack."""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["fiber.gis.cabinet.catalog"]._sync_defaults()
