from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Migra los datos existentes a la estructura de esta versión, conservando las relaciones y valores válidos."""
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    profiles = env["fiber.gis.cable.profile"].search([])
    for cable in env["fiber.gis.cable"].with_context(active_test=False).search([
        ("profile_id", "=", False),
    ]):
        profile = profiles.filtered(lambda item: (
            item.tube_count == cable.tube_count
            and item.fiber_count == cable.fiber_count
        ))[:1]
        if profile:
            values = {"profile_id": profile.id}
            if profile.gis_type_id and not cable.type_id:
                values["type_id"] = profile.gis_type_id.id
            cable.write(values)
