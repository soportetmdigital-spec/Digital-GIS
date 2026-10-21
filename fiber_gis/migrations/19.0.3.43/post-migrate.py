"""Completa las bocas de cable al actualizar desde una versión anterior."""


def migrate(cr, version):
    """Asigna valores predeterminados a equipos y modelos sin alterar los valores válidos."""
    if not version:
        return

    cr.execute(
        "UPDATE fiber_gis_node_category "
        "SET cable_entry_count = 4 "
        "WHERE cable_entry_count IS NULL OR cable_entry_count < 1"
    )
    cr.execute(
        "UPDATE fiber_gis_node AS node "
        "SET cable_entry_count = COALESCE(NULLIF(category.cable_entry_count, 0), 4) "
        "FROM fiber_gis_node_category AS category "
        "WHERE node.node_category_id = category.id "
        "AND (node.cable_entry_count IS NULL OR node.cable_entry_count < 1)"
    )
    cr.execute(
        "UPDATE fiber_gis_node "
        "SET cable_entry_count = 4 "
        "WHERE cable_entry_count IS NULL OR cable_entry_count < 1"
    )
