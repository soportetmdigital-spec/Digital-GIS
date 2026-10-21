from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, new_test_user


class TestCabinet(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cabinets = cls.env["fiber.gis.cabinet"]
        cls.cabinet = cls.cabinets.create({"name": "Cabecera pruebas", "height_u": 6})

    def _create_fiber(self, label):
        node_category = self.env["fiber.gis.node.category"].search([], limit=1)
        node_a = self.env["fiber.gis.node"].create({"name": f"Origen {label}", "node_category_id": node_category.id})
        node_b = self.env["fiber.gis.node"].create({"name": f"Destino {label}", "node_category_id": node_category.id})
        profile = self.env["fiber.gis.cable.profile"].search([], limit=1)
        cable = self.env["fiber.gis.cable"].create({
            "name": f"Cable {label}", "from_node_id": node_a.id, "to_node_id": node_b.id,
            "profile_id": profile.id,
        })
        return cable.fiber_ids[:1]

    def test_catalog_adds_patch_and_creates_numbered_ports(self):
        self.cabinet.action_create_equipment("patch_panel")
        panel = self.cabinet.equipment_ids
        self.assertEqual(panel.kind, "patch_panel")
        self.assertEqual(len(panel.port_ids), 24)
        self.assertEqual(panel.port_ids.mapped("number"), list(range(1, 25)))

    def test_library_port_count_edit_updates_catalog_and_equipment(self):
        self.cabinet.action_create_equipment("patch_panel", 1)
        panel = self.cabinet.equipment_ids
        result = self.cabinets.save_catalog_item(self.cabinet.id, "patch_panel", "Panel actualizado", 1, 20, False, "", {}, False)
        self.assertEqual(panel.port_count, 20)
        self.assertEqual(panel.port_ids.mapped("number"), list(range(1, 21)))
        item = next(row for row in result["catalog"] if row["kind"] == "patch_panel")
        self.assertEqual((item["name"], item["port_count"]), ("Panel actualizado", 20))

    def test_library_port_count_cannot_remove_a_connected_interconnection(self):
        self.cabinet.action_create_equipment("patch_panel", 1)
        self.cabinet.action_create_equipment("mikrotik_crs326", 2)
        panel, switch = self.cabinet.equipment_ids.sorted("position_u")
        self.cabinets.create_interconnection(panel.id, 24, switch.id, 1)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.cabinets.save_catalog_item(self.cabinet.id, "patch_panel", "Panel", 1, 20, False, "", {}, False)

    def test_expanded_catalog_includes_high_density_odf_and_common_rack_hardware(self):
        catalog = self.env["fiber.gis.cabinet.equipment"]._catalog()
        for kind in ("odf_96", "switch_48", "firewall", "server", "nas", "shelf_sliding", "cable_manager", "pdu", "fan_panel"):
            self.assertIn(kind, catalog)
        self.cabinet.action_create_equipment("odf_96", 1)
        odf = self.cabinet.equipment_ids
        self.assertEqual(odf.port_count, 96)
        self.assertEqual(len(odf.port_ids), 96)

    def test_catalog_adds_conceptdraw_rack_sizes_and_devices(self):
        catalog = self.env["fiber.gis.cabinet.equipment"]._catalog()
        expected = {
            "server_1u": (1, 2), "server_3u": (3, 2), "raid_2u": (2, 0),
            "raid_3u": (3, 0), "kvm_switch": (1, 0), "monitor_7u": (7, 0),
            "monitor_8u": (8, 0), "ups_managed": (2, 0), "power_strip": (1, 0),
        }
        for kind, dimensions in expected.items():
            with self.subTest(kind=kind):
                self.assertIn(kind, catalog)
                self.assertEqual((catalog[kind]["height_u"], catalog[kind]["port_count"]), dimensions)

    def test_fhu_48f_sc_upc_panel_creates_24_duplex_adapter_ports(self):
        self.cabinet.action_create_equipment("fhu_panel_48f", 1)
        panel = self.cabinet.equipment_ids
        self.assertEqual(panel.port_count, 24)
        self.assertEqual(len(panel.port_ids), 24)
        self.assertEqual(panel.port_ids.mapped("number"), list(range(1, 25)))

    def test_catalog_contains_real_mikrotik_and_zyxel_switch_models_and_can_rename(self):
        catalog = self.env["fiber.gis.cabinet.equipment"]._catalog()
        self.assertEqual(catalog["mikrotik_crs326"]["name"], "MikroTik CRS326-24G-2S+RM")
        self.assertEqual(catalog["zyxel_gs1920"]["name"], "Zyxel GS1920-24HPv2")
        self.cabinet.action_create_equipment("mikrotik_crs326", 1)
        equipment = self.cabinet.equipment_ids
        self.env["fiber.gis.cabinet"].rename_equipment(equipment.id, "Switch principal")
        self.assertEqual(equipment.name, "Switch principal")
        with self.assertRaises(ValidationError):
            self.env["fiber.gis.cabinet"].rename_equipment(equipment.id, "  ")

    def test_multiple_racks_share_header_and_can_register_interconnections(self):
        self.cabinets.add_cabinet_rack(self.cabinet.id)
        second_rack = self.cabinets.search([("rack_group_id", "=", self.cabinet.id)], limit=1)
        self.assertTrue(second_rack)
        self.cabinet.action_create_equipment("fhu_panel_48f", 1)
        second_rack.action_create_equipment("mikrotik_crs326", 1)
        panel = self.cabinet.equipment_ids
        switch = second_rack.equipment_ids
        result = self.cabinets.create_interconnection(panel.id, 1, switch.id, 2, "Panel a switch", "ethernet")
        self.assertEqual(len(result["racks"]), 2)
        self.assertEqual(len(result["interconnections"]), 1)
        self.assertEqual(result["interconnections"][0]["from_port"], 1)
        self.assertEqual(result["interconnections"][0]["to_port"], 2)
        self.cabinets.move_equipment_to_rack(switch.id, self.cabinet.id, 2)
        self.assertEqual(switch.cabinet_id, self.cabinet)
        refreshed = self.cabinets.get_cabinet_editor_data(self.cabinet.id)
        self.assertEqual(len(refreshed["interconnections"]), 1)
        self.assertEqual(refreshed["interconnections"][0]["to_rack_id"], self.cabinet.id)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.cabinets.create_interconnection(panel.id, 1, switch.id, 2, "Duplicada", "ethernet")

    def test_port_count_edits_keep_panel_ports_in_sync(self):
        self.cabinet.action_create_equipment("patch_panel", 1)
        panel = self.cabinet.equipment_ids
        panel.write({"port_count": 20})
        self.assertEqual(len(panel.port_ids), 20)
        panel.write({"port_count": 24})
        self.assertEqual(panel.port_ids.mapped("number"), list(range(1, 25)))

    def test_panel_cannot_shrink_while_removed_ports_have_fibers(self):
        self.cabinet.action_create_equipment("patch_panel", 1)
        panel = self.cabinet.equipment_ids
        fiber = self._create_fiber("panel-shrink")
        panel.port_ids.filtered(lambda port: port.number == 24).fiber_id = fiber
        with self.assertRaises(ValidationError), self.cr.savepoint():
            panel.write({"port_count": 20})

    def test_panel_cannot_be_written_with_zero_ports(self):
        self.cabinet.action_create_equipment("patch_panel", 1)
        panel = self.cabinet.equipment_ids
        with self.assertRaises(ValidationError), self.cr.savepoint():
            panel.write({"port_count": 0})

    def test_changing_equipment_kind_resynchronizes_ports(self):
        self.cabinet.action_create_equipment("patch_panel", 1)
        panel = self.cabinet.equipment_ids
        panel.write({"kind": "switch"})
        self.assertEqual(panel.port_count, 48)
        self.assertFalse(panel.port_ids)

    def test_equipment_cannot_overlap_or_exceed_rack(self):
        self.cabinet.action_create_equipment("odf", 2)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.cabinet.action_create_equipment("router", 3)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.cabinet.action_create_equipment("olt", 6)

    def test_batch_equipment_create_checks_overlaps_together(self):
        equipment_model = self.env["fiber.gis.cabinet.equipment"]
        with self.assertRaises(ValidationError), self.cr.savepoint():
            equipment_model.create([
                {"cabinet_id": self.cabinet.id, "name": "Equipo A", "kind": "router", "position_u": 2, "height_u": 1, "port_count": 0},
                {"cabinet_id": self.cabinet.id, "name": "Equipo B", "kind": "router", "position_u": 2, "height_u": 1, "port_count": 0},
            ])

    def test_each_fiber_can_be_assigned_once_and_released(self):
        self.cabinet.action_create_equipment("patch_panel", 1)
        panel = self.cabinet.equipment_ids
        first, second = panel.port_ids[:2]
        fiber = self._create_fiber("cabinet")
        first.write({"fiber_id": fiber.id})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            second.write({"fiber_id": fiber.id})
        first.write({"fiber_id": False})
        second.write({"fiber_id": fiber.id})
        self.assertEqual(second.fiber_id, fiber)

    def test_editor_data_excludes_fibers_already_used_in_another_cabinet(self):
        fiber = self._create_fiber("available")
        cabinet_node = fiber.cable_id.from_node_id
        self.cabinet.node_id = cabinet_node
        self.cabinet.action_create_equipment("patch_panel", 1)
        self.cabinet.equipment_ids.port_ids[0].fiber_id = fiber
        other = self.cabinets.create({"name": "Otra cabecera", "height_u": 4, "node_id": cabinet_node.id})
        other.action_create_equipment("patch_panel", 1)
        result = self.env["fiber.gis.cable.fiber"].search_cabinet_fibers(other.id, "available")
        self.assertNotIn(fiber.id, [item["id"] for item in result["fibers"]])

    def test_fiber_picker_only_includes_fibers_connected_to_cabinet_node(self):
        fiber = self._create_fiber("incoming")
        unrelated = self._create_fiber("unrelated")
        self.cabinet.node_id = fiber.cable_id.from_node_id
        result = self.env["fiber.gis.cable.fiber"].search_cabinet_fibers(self.cabinet.id, "incoming")
        ids = [item["id"] for item in result["fibers"]]
        self.assertIn(fiber.id, ids)
        self.assertNotIn(unrelated.id, ids)

    def test_searchable_picker_finds_matching_fibers_at_the_cabinet_node(self):
        fiber = self._create_fiber("searchable")
        self.cabinet.node_id = fiber.cable_id.from_node_id
        result = self.env["fiber.gis.cable.fiber"].search_cabinet_fibers(self.cabinet.id, "searchable")
        self.assertIn(fiber.id, [item["id"] for item in result["fibers"]])
        self.assertFalse(result["truncated"])
        self.assertEqual(self.env["fiber.gis.cable.fiber"].search_cabinet_fibers(self.cabinet.id, "x")["fibers"], [])

    def test_only_managers_can_open_or_mutate_cabinet(self):
        self.cabinet.action_create_equipment("switch")
        equipment_id = self.cabinet.equipment_ids.id
        user = new_test_user(self.env, login="cabinet_tech", groups="fiber_gis.group_fiber_gis_user")
        cabinet = self.cabinet.with_user(user)
        with self.assertRaises(UserError):
            cabinet.action_open_editor()
        with self.assertRaises(UserError):
            cabinet.action_create_equipment("switch")
        with self.assertRaises(UserError):
            cabinet.rename_equipment(equipment_id, "Nombre no autorizado")

