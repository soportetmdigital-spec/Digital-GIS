"""Capas del mapa recordadas por usuario en res.users.settings."""
from odoo.tests import TransactionCase, new_test_user


class TestMapLayers(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.technician = new_test_user(
            cls.env, login="gis_layers_technician", groups="base.group_user,fiber_gis.group_fiber_gis_user",
        )
        cls.other = new_test_user(
            cls.env, login="gis_layers_other", groups="base.group_user,fiber_gis.group_fiber_gis_user",
        )

    def test_layers_are_saved_per_user(self):
        settings = self.env["res.users.settings"].with_user(self.technician)
        self.assertEqual(settings.get_fiber_gis_map_layers(), {})
        saved = settings.set_fiber_gis_map_layers({
            "sites": False, "nodes": True, "cables": True, "customers": False, "dropCables": False,
            "hiddenNodeKinds": ["manhole", "pole", "manhole"], "unknown": True,
        })
        self.assertEqual(saved, {
            "sites": False, "nodes": True, "cables": True, "customers": False, "dropCables": False,
            "hiddenNodeKinds": ["manhole", "pole"],
        })
        self.assertEqual(settings.get_fiber_gis_map_layers(), saved)
        self.assertEqual(self.env["res.users.settings"].with_user(self.other).get_fiber_gis_map_layers(), {})
