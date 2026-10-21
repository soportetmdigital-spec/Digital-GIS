"""Conserva una sola entrada del importador de cartas de empalme."""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Borra menús duplicados sin tocar el menú ni su identificador XML canónicos."""
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    canonical = env.ref("fiber_gis.menu_fiber_gis_splice_import", raise_if_not_found=False)
    if not canonical:
        return

    duplicates = env["ir.ui.menu"].search([
        ("parent_id", "=", canonical.parent_id.id),
        ("name", "=", canonical.name),
        ("id", "!=", canonical.id),
    ])
    duplicates.unlink()
