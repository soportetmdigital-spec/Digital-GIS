import json

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase


class TestMapCable(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        node_model = cls.env["fiber.gis.node"]
        cls.origin = node_model.create({
            "name": "Origen mapa",
            "code": "TEST-MAP-ORIGIN",
            "latitude": 37.1762,
            "longitude": -3.5978,
        })
        cls.destination = node_model.create({
            "name": "Destino mapa",
            "code": "TEST-MAP-DESTINATION",
            "latitude": 37.1814,
            "longitude": -3.5881,
        })
        cls.distribution_type = cls.env["fiber.gis.asset.type"].search([
            ("category", "=", "cable"),
            ("code", "=", "CABLE_DISTRIBUTION"),
        ], limit=1)
        cls.node_type = cls.env["fiber.gis.asset.type"].search([
            ("category", "=", "node"),
        ], limit=1)

    def test_create_direct_cable_from_map(self):
        result = self.env["fiber.gis.cable"].create_from_map(
            self.origin.id,
            self.destination.id,
            [],
            False,
            "facade",
            self.distribution_type.id,
            1,
            1,
        )
        cable = self.env["fiber.gis.cable"].browse(result["id"])
        geometry = json.loads(cable.geometry_geojson)

        self.assertEqual(cable.from_node_id, self.origin)
        self.assertEqual(cable.to_node_id, self.destination)
        self.assertFalse(cable.deployment_plan_id)
        self.assertEqual(cable.route_kind, "facade")
        self.assertEqual(cable.type_id, self.distribution_type)
        self.assertEqual((cable.from_boca, cable.to_boca), (1, 1))
        self.assertEqual(self.env["fiber.gis.cable"].get_available_bocas(self.origin.id), [2, 3, 4])
        self.assertEqual(len(geometry["coordinates"]), 2)
        self.assertEqual(len(cable.segment_ids), 1)
        self.assertGreater(cable.length_m, 0)

    def test_create_map_cable_in_deployment(self):
        plan = self.env["fiber.gis.deployment.plan"].create({
            "name": "Prueba de trazado en despliegue",
        })
        via_point = [37.179, -3.592]
        result = self.env["fiber.gis.cable"].create_from_map(
            self.origin.id,
            self.destination.id,
            [via_point],
            plan.id,
            "aerial",
            False,
            2,
            2,
        )
        cable = self.env["fiber.gis.cable"].browse(result["id"])
        geometry = json.loads(cable.geometry_geojson)

        self.assertEqual(cable.deployment_plan_id, plan)
        self.assertEqual(cable.state, "planned")
        self.assertEqual(cable.route_kind, "aerial")
        self.assertEqual(len(geometry["coordinates"]), 3)
        self.assertEqual(len(cable.segment_ids), 2)
        self.assertEqual(set(cable.segment_ids.mapped("route_kind")), {"aerial"})

        cable.write({"route_kind": "underground"})
        self.assertEqual(set(cable.segment_ids.mapped("route_kind")), {"underground"})
        self.assertEqual(set(json.loads(cable.route_segment_kinds)), {"underground"})

    def test_continued_map_cable_registers_fibers_as_pass_in_first_tray(self):
        middle = self.env["fiber.gis.node"].create({
            "name": "Caja intermedia de trazado",
            "code": "TEST-MAP-MIDDLE",
            "latitude": 37.1781,
            "longitude": -3.5935,
            "has_trays": True,
            "tray_count": 1,
        })
        cable_model = self.env["fiber.gis.cable"]
        temporary_profile = self.env["fiber.gis.cable.profile"].create({
            "name": "Tipología provisional de trazado",
            "gis_type_id": self.distribution_type.id,
            "tube_count": 0,
            "fiber_count": 2,
        })
        final_profile = self.env["fiber.gis.cable.profile"].create({
            "name": "Tipología final de trazado",
            "gis_type_id": self.distribution_type.id,
            "tube_count": 2,
            "fiber_count": 4,
        })
        incoming = cable_model.create_from_map(
            self.origin.id, middle.id, [], False, "facade",
            temporary_profile.id, 1, 1,
        )
        outgoing = cable_model.create_from_map(
            middle.id, self.destination.id, [], False, "facade",
            temporary_profile.id, 2, 1,
        )
        final_result = cable_model.finalize_map_cable_chain(
            [incoming["id"], outgoing["id"]], final_profile.id,
        )

        tray = middle.tray_ids.sorted(lambda item: (item.sequence, item.id))[:1]
        incoming_cable = cable_model.browse(incoming["id"])
        outgoing_cable = cable_model.browse(outgoing["id"])
        pass_lines = tray.line_ids.filtered(lambda line: line.line_type == "pass")

        self.assertTrue(tray)
        self.assertEqual(final_result["sangria_results"][0]["tray"], tray.display_name)
        self.assertEqual(final_result["profile"], final_profile.display_name)
        self.assertEqual(incoming_cable.profile_id, final_profile)
        self.assertEqual(outgoing_cable.profile_id, final_profile)
        self.assertEqual(incoming_cable.total_fiber_count, 8)
        self.assertEqual(outgoing_cable.total_fiber_count, 8)
        self.assertEqual(len(pass_lines), 8)
        self.assertEqual(len(incoming_cable.fiber_ids), 8)
        self.assertEqual(len(outgoing_cable.fiber_ids), 8)
        self.assertEqual(
            {line.input_fiber_id.cable_id.id for line in pass_lines},
            {incoming_cable.id},
        )
        self.assertEqual(
            {line.output_fiber_id.cable_id.id for line in pass_lines},
            {outgoing_cable.id},
        )
        self.assertEqual(
            {line.input_fiber_id.number for line in pass_lines},
            {line.output_fiber_id.number for line in pass_lines},
        )

    def test_map_rejects_non_cable_asset_type(self):
        with self.assertRaises(ValidationError):
            self.env["fiber.gis.cable"].create_from_map(
                self.origin.id,
                self.destination.id,
                [],
                False,
                "facade",
                self.node_type.id,
                4,
                4,
            )

    def test_map_rejects_a_boca_already_used(self):
        cable_model = self.env["fiber.gis.cable"]
        cable_model.create_from_map(
            self.origin.id, self.destination.id, [], False, "facade",
            self.distribution_type.id, 1, 1,
        )
        with self.assertRaises(ValidationError):
            cable_model.create_from_map(
                self.origin.id, self.destination.id, [], False, "facade",
                self.distribution_type.id, 1, 2,
            )

    def test_cable_bocas_can_be_changed_and_still_validate_occupancy(self):
        cable_model = self.env["fiber.gis.cable"]
        first = cable_model.create_from_map(
            self.origin.id, self.destination.id, [], False, "facade",
            self.distribution_type.id, 1, 1,
        )
        second = cable_model.create_from_map(
            self.origin.id, self.destination.id, [], False, "facade",
            self.distribution_type.id, 2, 2,
        )
        first_cable = cable_model.browse(first["id"])
        first_cable.write({"from_boca": 3, "to_boca": 3})
        self.assertEqual((first_cable.from_boca, first_cable.to_boca), (3, 3))

        with self.assertRaises(ValidationError), self.cr.savepoint():
            first_cable.write({"from_boca": 2})

        self.assertEqual(first_cable.from_boca, 3)
        self.assertEqual(cable_model.browse(second["id"]).from_boca, 2)

    def test_tray_selector_names_cable_with_its_local_boca(self):
        result = self.env["fiber.gis.cable"].create_from_map(
            self.origin.id, self.destination.id, [], False, "facade",
            self.distribution_type.id, 1, 1,
        )
        cable = self.env["fiber.gis.cable"].browse(result["id"])
        cable.code = "TEST-BOCA"

        origin_label = cable.with_context(
            fiber_gis_node_id=self.origin.id, fiber_gis_show_boca=True,
        ).display_name
        destination_label = cable.with_context(
            fiber_gis_node_id=self.destination.id, fiber_gis_show_boca=True,
        ).display_name

        self.assertIn("Boca 1", origin_label)
        self.assertIn("Boca 1", destination_label)
        self.assertNotIn("entrada", origin_label.lower())
        self.assertNotIn("salida", origin_label.lower())
        self.assertNotIn("entrada", destination_label.lower())
        self.assertNotIn("salida", destination_label.lower())
        self.assertIn("TEST-BOCA", origin_label)
        self.assertNotIn("Boca de", cable.display_name)

    def test_new_manhole_defaults_to_black_square(self):
        manhole = self.env["fiber.gis.node"].create({
            "name": "Arqueta cuadrada prueba",
            "node_kind": "manhole",
        })
        self.assertEqual(manhole.map_icon, "square")
        self.assertEqual(manhole.color, "#000000")

    def test_internal_cto_model_defaults_to_two_bocas(self):
        model = self.env.ref("fiber_gis.node_category_cto_internal")
        internal_cto = self.env["fiber.gis.node"].create({
            "name": "CTO interior de prueba",
            "code": "TEST-CTO-INTERNAL-BOCAS",
            "node_category_id": model.id,
        })
        self.assertEqual(model.cable_entry_count, 2)
        self.assertEqual(internal_cto.cable_entry_count, 2)

    def test_manual_name_preserved_when_endpoints_change(self):
        self.destination.address = "Calle San Ant\u00f3n 63, Granada"
        cable = self.env["fiber.gis.cable"].create({
            "name": "Nombre importado", "code": "ID-1234",
            "from_node_id": self.origin.id, "to_node_id": self.destination.id,
            "fiber_count": 12,
        })
        cable.action_generate_fibers()
        fibers, segments = cable.fiber_ids.ids, cable.segment_ids.ids
        geometry = cable.geometry_geojson
        self.assertEqual(cable.name, "Nombre importado")
        self.assertFalse(cable.previous_name)
        cable.active = False
        self.origin.code = "TEST-MAP-UPDATED"
        self.destination.address = "  Calle Elvira  12, Granada "
        self.assertEqual(cable.name, "Nombre importado")
        self.assertFalse(cable.previous_name)
        self.assertEqual(cable.code, "ID-1234")
        self.assertEqual(cable.fiber_ids.ids, fibers)
        self.assertEqual(cable.segment_ids.ids, segments)
        self.assertEqual(cable.geometry_geojson, geometry)

    def test_new_endpoint_keeps_manual_name(self):
        cable = self.env["fiber.gis.cable"].create({
            "name": "Cable escrito a mano",
            "from_node_id": self.origin.id, "to_node_id": self.destination.id,
        })
        third = self.env["fiber.gis.node"].create({
            "name": "Otra caja", "code": "TEST-MAP-THIRD", "address": "Calle Real 5, Santa Fe",
        })
        cable.to_node_id = third
        self.assertEqual(cable.name, "Cable escrito a mano")
