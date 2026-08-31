from odoo.tests import TransactionCase


class TestManholeTypes(TransactionCase):
    def test_model_dimensions_are_copied_to_manhole(self):
        manhole_type = self.env["fiber.gis.manhole.type"].create({
            "name": "Arqueta de prueba",
            "code": "TEST_MANHOLE",
            "length_cm": 80,
            "width_cm": 70,
            "depth_cm": 82,
        })

        manhole = self.env["fiber.gis.node"].create({
            "name": "Arqueta automatica",
            "code": "ARQ-TEST-AUTO",
            "node_kind": "manhole",
            "manhole_model_id": manhole_type.id,
        })

        self.assertEqual(manhole.manhole_length_cm, 80)
        self.assertEqual(manhole.manhole_width_cm, 70)
        self.assertEqual(manhole.manhole_depth_cm, 82)

    def test_explicit_measure_can_override_catalog(self):
        manhole_type = self.env["fiber.gis.manhole.type"].create({
            "name": "Arqueta ajustable",
            "code": "TEST_MANHOLE_CUSTOM",
            "length_cm": 60,
            "width_cm": 60,
            "depth_cm": 80,
        })

        manhole = self.env["fiber.gis.node"].create({
            "name": "Arqueta con medida real",
            "code": "ARQ-TEST-REAL",
            "node_kind": "manhole",
            "manhole_model_id": manhole_type.id,
            "manhole_depth_cm": 95,
        })

        self.assertEqual(manhole.manhole_length_cm, 60)
        self.assertEqual(manhole.manhole_width_cm, 60)
        self.assertEqual(manhole.manhole_depth_cm, 95)
