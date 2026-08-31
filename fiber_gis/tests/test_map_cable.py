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
        )
        cable = self.env["fiber.gis.cable"].browse(result["id"])
        geometry = json.loads(cable.geometry_geojson)

        self.assertEqual(cable.from_node_id, self.origin)
        self.assertEqual(cable.to_node_id, self.destination)
        self.assertFalse(cable.deployment_plan_id)
        self.assertEqual(cable.route_kind, "facade")
        self.assertEqual(cable.type_id, self.distribution_type)
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

    def test_map_rejects_non_cable_asset_type(self):
        with self.assertRaises(ValidationError):
            self.env["fiber.gis.cable"].create_from_map(
                self.origin.id,
                self.destination.id,
                [],
                False,
                "facade",
                self.node_type.id,
            )

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
