"""Actualiza solo la categoría predeterminada Arqueta."""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Establece el estilo solicitado para Arqueta sin tocar elementos existentes."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    category = env.ref("fiber_gis.node_category_manhole", raise_if_not_found=False)
    if category:
        category.write({"name": "Arqueta", "map_icon": "square", "color": "#000000"})
