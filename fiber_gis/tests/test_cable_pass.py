"""Cables que pasan por elementos: al trazarlos en el mapa y al revisar el cableado existente."""
import json

from odoo.tests import TransactionCase, new_test_user


class TestCablePass(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        node_model = cls.env["fiber.gis.node"]
        cls.origin = node_model.create({
            "name": "Origen paso", "code": "TEST-PASS-A", "latitude": 37.1800, "longitude": -3.6000,
            "cable_entry_count": 4,
        })
        cls.middle = node_model.create({
            "name": "Caja de paso", "code": "TEST-PASS-M", "latitude": 37.1800, "longitude": -3.5990,
            "cable_entry_count": 4,
        })
        cls.destination = node_model.create({
            "name": "Destino paso", "code": "TEST-PASS-B", "latitude": 37.1800, "longitude": -3.5980,
            "cable_entry_count": 4, "has_trays": True, "tray_count": 1,
        })
        cls.profile = cls.env["fiber.gis.cable.profile"].create({"name": "2x4 paso", "tube_count": 2, "fiber_count": 4})
        cls.manager = new_test_user(
            cls.env, login="gis_pass_manager", groups="base.group_user,fiber_gis.group_fiber_gis_manager",
        )

    def _pass_lines(self, node):
        return self.env["fiber.gis.tray.line"].search([("node_id", "=", node.id), ("line_type", "=", "pass")])

    def test_map_cable_over_an_element_can_be_left_as_pass(self):
        cable_model = self.env["fiber.gis.cable"]
        candidates = cable_model.get_map_route_pass_candidates(self.origin.id, self.destination.id, [], 3.0)
        self.assertEqual([item["id"] for item in candidates], [self.middle.id])
        self.middle.tray_ids.unlink()
        self.middle.write({"has_trays": False, "tray_count": 0})
        self.assertFalse(self.middle.tray_ids)

        created = cable_model.create_from_map(
            self.origin.id, self.destination.id, [], False, "underground",
            self.profile.id, 1, 1, [self.middle.id],
        )
        first, second = cable_model.browse(created["cable_ids"])
        self.assertEqual((first.from_node_id, first.to_node_id), (self.origin, self.middle))
        self.assertEqual((second.from_node_id, second.to_node_id), (self.middle, self.destination))
        self.assertEqual((first.from_boca, second.to_boca), (1, 1))
        self.assertNotEqual(first.to_boca, second.from_boca)

        result = cable_model.finalize_map_cable(created["cable_ids"], self.profile.id)
        self.assertTrue(self.middle.tray_ids, "La caja sin bandejas recibe la bandeja 1.")
        lines = self._pass_lines(self.middle)
        self.assertEqual(len(lines), 8)
        self.assertEqual(lines.mapped("tray_id"), self.middle.tray_ids.sorted("sequence")[:1])
        self.assertEqual(result["pass_results"][0]["created"], 8)
        self.assertEqual({line.input_fiber_id.number for line in lines}, {line.output_fiber_id.number for line in lines})

    def test_answering_no_keeps_a_single_cable(self):
        created = self.env["fiber.gis.cable"].create_from_map(
            self.origin.id, self.destination.id, [], False, "underground", self.profile.id, 1, 1, [],
        )
        self.assertEqual(len(created["cable_ids"]), 1)
        self.env["fiber.gis.cable"].finalize_map_cable(created["cable_ids"], False)
        self.assertFalse(self._pass_lines(self.middle))

    def test_review_splits_existing_cable_and_keeps_destination_operations(self):
        cable = self.env["fiber.gis.cable"].create({
            "name": "Cable existente", "from_node_id": self.origin.id, "to_node_id": self.destination.id,
            "from_boca": 1, "to_boca": 1, "profile_id": self.profile.id, "state": "installed",
            "geometry_geojson": json.dumps({"type": "LineString", "coordinates": [[-3.6000, 37.1800], [-3.5980, 37.1800]]}),
        })
        fiber_3 = cable.fiber_ids.filtered(lambda fiber: fiber.number == 3)
        tray = self.destination.tray_ids[:1]
        end_line = self.env["fiber.gis.tray.line"].create({"tray_id": tray.id, "line_type": "free", "input_fiber_id": fiber_3.id})

        review = self.env["fiber.gis.cable.pass.review"].with_user(self.manager).create({"tolerance_m": 3.0})
        review.action_search()
        crossing = review.line_ids.filtered(lambda line: line.cable_id == cable and line.node_id == self.middle)
        self.assertEqual(len(crossing), 1)
        crossing.leave_pass = True
        review.action_apply()

        self.assertEqual(cable.to_node_id, self.middle)
        last = self.env["fiber.gis.cable"].search([("from_node_id", "=", self.middle.id), ("to_node_id", "=", self.destination.id)])
        self.assertEqual(len(last), 1)
        self.assertEqual((last.to_boca, last.state, last.profile_id), (1, "installed", self.profile))
        self.assertEqual(end_line.input_fiber_id.cable_id, last, "La operación del destino pasa al último tramo.")
        self.assertEqual(end_line.input_fiber_id.number, 3)
        self.assertEqual(len(self._pass_lines(self.middle)), 8)
        self.assertFalse(review.line_ids.filtered(lambda line: line.cable_id == cable and line.node_id == self.middle))
