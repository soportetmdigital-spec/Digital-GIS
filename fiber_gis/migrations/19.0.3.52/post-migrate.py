"""Activa y prepara bandejas para los modelos de cajas acordados."""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Activa las bandejas de esos modelos una sola vez sin modificar matrículas ni nombres."""
    if not version:
        return

    cr.execute(
        "UPDATE fiber_gis_node_category SET has_trays = TRUE "
        "WHERE code IN ('CTO', 'CTO_INTERNAL', 'BOX', 'CLOSURE')"
    )
    cr.execute(
        "UPDATE fiber_gis_node "
        "SET has_trays = TRUE, tray_count = GREATEST(COALESCE(tray_count, 0), 1) "
        "WHERE node_kind IN ('cto', 'box', 'closure')"
    )

    env = api.Environment(cr, SUPERUSER_ID, {"skip_fiber_gis_work_log": True})
    nodes = env["fiber.gis.node"].with_context(active_test=False).search([
        ("node_kind", "in", ["cto", "box", "closure"]),
    ])
    nodes._ensure_trays_from_count()
