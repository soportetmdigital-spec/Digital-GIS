"""Elimina entradas repetidas del menú de importación de cartas."""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Conserva el menú canónico y elimina copias antiguas bajo Configuración."""
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    canonical = env.ref("fiber_gis.menu_fiber_gis_splice_import", raise_if_not_found=False)
    if not canonical:
        return

    siblings = env["ir.ui.menu"].search([("parent_id", "=", canonical.parent_id.id)])
    duplicates = siblings.filtered(
        lambda menu: menu.id != canonical.id and menu.name == canonical.name
    )
    duplicates.unlink()
