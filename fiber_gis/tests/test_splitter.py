from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase


class TestSplitterManagement(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        node_model = cls.env["fiber.gis.node"]
        cls.source = node_model.create({
            "name": "Cabecera splitter",
            "code": "TEST-SPLITTER-SOURCE",
        })
        cls.box = node_model.create({
            "name": "CTO splitter",
            "code": "TEST-SPLITTER-BOX",
            "has_trays": True,
            "tray_count": 2,
            "latitude": 37.1800,
            "longitude": -3.6000,
        })
        cls.destination = node_model.create({
            "name": "Destino splitter",
            "code": "TEST-SPLITTER-DEST",
            "address": "Calle de prueba 1",
        })
        cls.customer_partner = cls.env["res.partner"].create({
            "name": "Cliente splitter",
            "street": "Calle cliente 2",
            "zip": "18001",
            "city": "Granada",
        })
        cls.customer = node_model.create({
            "name": "Cliente splitter",
            "code": "TEST-SPLITTER-CUSTOMER",
            "address": "Calle cliente 2",
            "node_kind": "ont",
            "partner_id": cls.customer_partner.id,
            "latitude": 37.1810,
            "longitude": -3.6010,
        })
        cable_model = cls.env["fiber.gis.cable"]
        cls.input_cable = cable_model.create({
            "name": "Cable de entrada splitter",
            "from_node_id": cls.source.id,
            "to_node_id": cls.box.id,
            "fiber_count": 12,
        })
        cls.output_cable = cable_model.create({
            "name": "Cable de salida splitter",
            "from_node_id": cls.box.id,
            "to_node_id": cls.destination.id,
            "fiber_count": 12,
        })
        cls.drop_cable = cable_model.create({
            "name": "Acometida cliente",
            "type_id": cls.env.ref("fiber_gis.type_cable_drop").id,
            "from_node_id": cls.box.id,
            "to_node_id": cls.customer.id,
            "fiber_count": 2,
        })
        cls.input_cable.action_generate_fibers()
        cls.output_cable.action_generate_fibers()
        cls.drop_cable.action_generate_fibers()
        cls.tray_1 = cls.box.tray_ids.sorted("sequence")[0]
        cls.tray_2 = cls.box.tray_ids.sorted("sequence")[1]

    def test_splitter_creates_outputs_and_tray_position(self):
        splitter = self.env["fiber.gis.splitter"].create({
            "tray_id": self.tray_1.id,
            "ratio": "1:8",
            "input_fiber_id": self.input_cable.fiber_ids[0].id,
        })

        self.assertEqual(len(splitter.output_ids), 8)
        self.assertEqual(splitter.output_count, 8)
        self.assertEqual(splitter.free_output_count, 8)
        self.assertEqual(splitter.nominal_loss_db, 10.4)
        self.assertEqual(len(splitter.tray_line_ids), 1)
        self.assertEqual(splitter.tray_line_ids.line_type, "splitter")

        first_output = splitter.output_ids.filtered(lambda output: output.sequence == 1)
        first_output.output_fiber_id = self.output_cable.fiber_ids[0]
        self.assertEqual(first_output.state, "connected")
        self.assertEqual(splitter.connected_output_count, 1)
        self.assertIn("Destino splitter", first_output.destination_label)
        self.assertEqual(self.output_cable.fiber_ids[0].state, "used")

        splitter.ratio = "1:16"
        self.assertEqual(splitter.nominal_loss_db, 13.7)
        splitter.write({"ratio": "1:32", "nominal_loss_db": 16.8})
        self.assertEqual(splitter.nominal_loss_db, 16.8)

    def test_ratio_cannot_shrink_over_occupied_output(self):
        splitter = self.env["fiber.gis.splitter"].create({
            "tray_id": self.tray_1.id,
            "ratio": "1:16",
            "input_fiber_id": self.input_cable.fiber_ids[1].id,
        })
        output_16 = splitter.output_ids.filtered(lambda output: output.sequence == 16)
        output_16.output_fiber_id = self.output_cable.fiber_ids[1]

        with self.assertRaises(UserError):
            splitter.ratio = "1:8"

    def test_moving_splitter_position_updates_splitter(self):
        splitter = self.env["fiber.gis.splitter"].create({
            "tray_id": self.tray_1.id,
            "ratio": "1:4",
            "input_fiber_id": self.input_cable.fiber_ids[2].id,
        })

        self.env["fiber.gis.tray.line"].action_move_to_tray(
            splitter.tray_line_ids.id,
            self.tray_2.id,
        )

        self.assertEqual(splitter.tray_id, self.tray_2)
        self.assertEqual(splitter.tray_line_ids.tray_id, self.tray_2)

    def test_tray_assistant_fuses_fiber_to_customer_drop(self):
        source_fiber = self.output_cable.fiber_ids[4]
        drop_fiber = self.drop_cable.fiber_ids[0]
        wizard = self.env["fiber.gis.cable.tray.wizard"].create({
            "operation": "customer_drop",
            "customer_drop_source": "fiber",
            "node_id": self.box.id,
            "tray_id": self.tray_1.id,
            "cable_id": self.output_cable.id,
            "customer_id": self.customer_partner.id,
            "customer_address": self.customer.address,
            "customer_latitude": self.customer.latitude,
            "customer_longitude": self.customer.longitude,
            "selected_fiber_ids": [(6, 0, [source_fiber.id])],
        })

        wizard.action_apply()

        line = self.tray_1.line_ids.filtered(
            lambda item: item.input_fiber_id == source_fiber
            and item.output_fiber_id == drop_fiber
        )
        self.assertEqual(len(line), 1)
        self.assertEqual(line.line_type, "fusion")

    def test_splitter_wizard_connects_free_output_to_customer_drop(self):
        splitter = self.env["fiber.gis.splitter"].create({
            "tray_id": self.tray_1.id,
            "ratio": "1:4",
            "input_fiber_id": self.input_cable.fiber_ids[5].id,
        })
        output = splitter.output_ids.filtered(lambda item: item.sequence == 1)
        drop_fiber = self.drop_cable.fiber_ids[1]
        wizard = self.env["fiber.gis.splitter.drop.wizard"].create({
            "splitter_id": splitter.id,
            "output_id": output.id,
            "customer_id": self.customer_partner.id,
            "customer_address": self.customer.address,
            "customer_latitude": self.customer.latitude,
            "customer_longitude": self.customer.longitude,
        })

        wizard.action_connect()

        self.assertEqual(output.output_fiber_id, self.drop_cable.fiber_ids[0])
        self.assertEqual(output.state, "connected")
        self.assertIn("Cliente splitter", output.destination_label)

        with self.assertRaises(UserError):
            splitter._connect_customer_drop(output, drop_fiber)

    def test_tray_assistant_connects_cable_fiber_to_splitter_output(self):
        splitter = self.env["fiber.gis.splitter"].create({
            "tray_id": self.tray_1.id,
            "ratio": "1:4",
            "input_fiber_id": self.input_cable.fiber_ids[8].id,
        })
        output = splitter.output_ids.filtered(lambda item: item.sequence == 2)
        fiber = self.output_cable.fiber_ids[8]
        wizard = self.env["fiber.gis.cable.tray.wizard"].create({
            "operation": "splitter_fusion",
            "node_id": self.box.id,
            "tray_id": self.tray_1.id,
            "cable_id": self.output_cable.id,
            "from_fiber": fiber.number,
            "to_fiber": fiber.number,
            "target_splitter_id": splitter.id,
            "target_splitter_output_id": output.id,
            "selected_fiber_ids": [(6, 0, [fiber.id])],
        })

        wizard.action_apply()

        self.assertEqual(output.output_fiber_id, fiber)
        self.assertEqual(output.state, "connected")
        self.assertEqual(fiber.state, "used")
        self.assertIn("Destino splitter", output.destination_label)

    def test_trace_continues_through_splitter_output(self):
        input_fiber = self.input_cable.fiber_ids[10]
        output_fiber = self.output_cable.fiber_ids[10]
        splitter = self.env["fiber.gis.splitter"].create({
            "tray_id": self.tray_1.id,
            "ratio": "1:4",
            "input_fiber_id": input_fiber.id,
        })
        splitter._connect_output_fiber(
            splitter.output_ids.filtered(lambda item: item.sequence == 1),
            output_fiber,
        )
        splitter._connect_output_fiber(
            splitter.output_ids.filtered(lambda item: item.sequence == 2),
            self.drop_cable.fiber_ids[0],
        )
        trace = self.env["fiber.gis.trace.wizard"].create({
            "node_id": self.destination.id,
            "fiber_id": output_fiber.id,
        })._get_trace_data()

        self.assertIn(self.input_cable.id, trace["cable_ids"])
        self.assertIn(self.output_cable.id, trace["cable_ids"])
        self.assertNotIn(self.drop_cable.id, trace["cable_ids"])
        self.assertIn(self.source.id, trace["node_ids"])
        self.assertTrue(any(
            "continua hacia el origen" in row["detail"]
            for row in trace["rows"]
        ))

    def test_customer_drop_is_created_with_map_endpoint(self):
        partner = self.env["res.partner"].create({
            "name": "Cliente nuevo de acometida",
            "ref": "CLI-00042",
            "street": "Calle nueva 8",
            "zip": "18002",
            "city": "Granada",
        })

        endpoint, cable, fiber = self.box._ensure_customer_drop(
            partner,
            "Calle nueva 8, 18002 Granada, Espana",
            37.1765,
            -3.5962,
        )

        self.assertEqual(endpoint.partner_id, partner)
        self.assertEqual(endpoint.code, "ID-CLI-00042")
        self.assertEqual(endpoint.map_icon, "customer_terminal")
        self.assertEqual(endpoint.node_kind, "ont")
        self.assertEqual(cable.type_id.code, "CABLE_DROP")
        self.assertEqual(cable.from_node_id, self.box)
        self.assertEqual(cable.to_node_id, endpoint)
        self.assertEqual(cable.code, "ID-CLI-00042")
        self.assertEqual(cable.total_fiber_count, 1)
        self.assertEqual(fiber.number, 1)

    def test_tray_assistant_connects_two_customer_drops_to_same_splitter(self):
        splitter = self.env["fiber.gis.splitter"].create({
            "tray_id": self.tray_1.id,
            "ratio": "1:4",
            "input_fiber_id": self.input_cable.fiber_ids[7].id,
        })
        for sequence in (1, 2):
            partner = self.env["res.partner"].create({
                "name": f"Cliente acometida {sequence}",
                "ref": f"DROP-{sequence:02d}",
                "street": f"Calle Acometida {sequence}",
                "zip": "18001",
                "city": "Granada",
            })
            output = splitter.output_ids.filtered(lambda item: item.sequence == sequence)
            wizard = self.env["fiber.gis.cable.tray.wizard"].create({
                "operation": "customer_drop",
                "customer_drop_source": "splitter",
                "node_id": self.box.id,
                "tray_id": self.tray_1.id,
                "cable_id": self.drop_cable.id,
                "from_fiber": 1,
                "to_fiber": 99,
                "customer_splitter_id": splitter.id,
                "customer_splitter_output_id": output.id,
                "customer_id": partner.id,
                "customer_address": f"Calle Acometida {sequence}, 18001 Granada, Espana",
                "customer_latitude": 37.1810 + sequence / 10000,
                "customer_longitude": -3.6010 - sequence / 10000,
            })

            wizard.action_apply()

            self.assertEqual(output.state, "connected")
            self.assertEqual(output.output_fiber_id.number, 1)
            self.assertEqual(output.output_fiber_id.cable_id.total_fiber_count, 1)
            self.assertEqual(output.output_fiber_id.cable_id.code, f"ID-DROP-{sequence:02d}")
            expected_color = self.env["fiber.gis.cable.fiber"].fiber_color(sequence)
            self.assertEqual(output.port_color, expected_color)
            self.assertEqual(output.output_fiber_id.cable_id.color, expected_color)

        connected_cables = splitter.output_ids.filtered(
            lambda output: output.sequence in (1, 2)
        ).mapped("output_fiber_id.cable_id")
        self.assertEqual(len(connected_cables), 2)

    def _make_splitter(self, **values):
        return self.env["fiber.gis.splitter"].create({
            "tray_id": self.tray_1.id, "ratio": "1:4", **values,
        })

    def test_tray_click_selects_exact_fiber_and_both_fusion_ends(self):
        left, right = self.input_cable.fiber_ids[2], self.output_cable.fiber_ids[6]
        line = self.env["fiber.gis.tray.line"].create({
            "tray_id": self.tray_1.id, "line_type": "fusion",
            "input_fiber_id": left.id, "output_fiber_id": right.id,
        })
        for selected, other in ((left, right), (right, left)):
            action = line.action_open_fiber(selected.id)
            self.assertEqual(action["views"], [(self.env.ref("fiber_gis.view_fiber_gis_cable_tray_wizard_form").id, "form")])
            wizard = self.env[action["res_model"]].browse(action["res_id"])
            self.assertEqual(wizard.source_line_id, line)
            self.assertEqual(wizard.cable_id, selected.cable_id)
            self.assertEqual(wizard.fusion_input_fiber_ids, selected)
            self.assertEqual(wizard.fusion_output_fiber_ids, other)
            self.assertIn("Calle de prueba 1", wizard.source_info_html)
            self.assertEqual(wizard.from_fiber, selected.number)
        with self.assertRaises(UserError):
            line.action_open_fiber(self.input_cable.fiber_ids[9].id)

    def test_rest_click_does_not_change_fibers_until_registered(self):
        fiber = self.input_cable.fiber_ids[4]
        line = self.env["fiber.gis.tray.line"].create({
            "tray_id": self.tray_1.id, "line_type": "free", "input_fiber_id": fiber.id,
        })
        action = line.action_open_fiber()
        self.assertEqual(action["views"], [(self.env.ref("fiber_gis.view_fiber_gis_cable_tray_wizard_form").id, "form")])
        wizard = self.env[action["res_model"]].browse(action["res_id"])
        self.assertEqual(wizard.selected_fiber_ids, fiber)
        self.assertEqual(line.line_type, "free")
        self.assertTrue(line.exists())

    def test_splitter_tray_click_opens_splitter(self):
        splitter = self._make_splitter(input_fiber_id=self.input_cable.fiber_ids[0].id)
        action = splitter.tray_line_ids.action_open_fiber()
        self.assertEqual(action["views"], [(self.env.ref("fiber_gis.view_fiber_gis_splitter_form").id, "form")])
        self.assertEqual(action["res_model"], "fiber.gis.splitter")
        self.assertEqual(action["res_id"], splitter.id)
        output_action = splitter.output_ids[0].action_manage_connection()
        self.assertEqual(output_action["views"], [(self.env.ref("fiber_gis.view_fiber_gis_splitter_drop_wizard_form").id, "form")])
        self.assertEqual(output_action["context"]["default_output_id"], splitter.output_ids[0].id)
        self.assertFalse(output_action["context"]["default_operation"])

    def test_output_wizard_creates_cascade_and_preserves_it_on_disconnect(self):
        parent = self._make_splitter(input_fiber_id=self.input_cable.fiber_ids[0].id)
        output = parent.output_ids[0]
        wizard = self.env["fiber.gis.splitter.drop.wizard"].create({
            "splitter_id": parent.id, "output_id": output.id,
            "operation": "splitter", "create_splitter": True,
            "tray_id": self.tray_2.id, "new_ratio": "1:8",
            "splitter_name": "Segundo nivel", "notes": "Instalado en bandeja 2",
        })
        wizard.action_connect()
        child = output.downstream_splitter_ids
        self.assertEqual(len(child), 1)
        self.assertFalse(child.input_fiber_id)
        self.assertEqual(child.notes, "Instalado en bandeja 2")
        self.assertTrue(output.is_connected)
        self.assertEqual(parent.connected_output_count, 1)
        self.assertEqual(child._upstream_fiber()[0], self.input_cable.fiber_ids[0])
        self.assertEqual(child.tray_line_ids.action_open_fiber()["res_id"], child.id)
        with self.assertRaises(UserError):
            wizard.action_connect()
        wizard.action_disconnect()
        self.assertTrue(child.exists())
        self.assertTrue(child.tray_line_ids.exists())
        self.assertFalse(child.input_output_id)
        self.assertFalse(output.is_connected)
        self.assertEqual(output.state, "free")

    def test_output_wizard_connects_existing_splitter(self):
        parent, child = self._make_splitter(), self._make_splitter(tray_id=self.tray_2.id)
        output = parent.output_ids[0]
        self.env["fiber.gis.splitter.drop.wizard"].create({
            "splitter_id": parent.id, "output_id": output.id, "operation": "splitter",
            "create_splitter": False, "target_splitter_id": child.id,
        }).action_connect()
        self.assertEqual(child.input_output_id, output)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            parent.write({"input_output_id": child.output_ids[0].id})

    def test_cascade_rejects_two_sources_and_occupied_port(self):
        parent = self._make_splitter()
        output = parent.output_ids[0]
        child = self._make_splitter(input_output_id=output.id)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            child.write({"input_fiber_id": self.input_cable.fiber_ids[0].id})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            output.write({"output_fiber_id": self.output_cable.fiber_ids[0].id})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            output.write({"output_fiber_id": False})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            output.write({"state": "free"})

    def test_cascade_rejects_remote_box_and_ratio_shrink(self):
        parent = self._make_splitter(ratio="1:8")
        self._make_splitter(input_output_id=parent.output_ids.filtered(lambda port: port.sequence == 8).id)
        with self.assertRaises(UserError), self.cr.savepoint():
            parent.write({"ratio": "1:4"})
        remote = self.env["fiber.gis.tray"].create({"name": "Remota", "node_id": self.destination.id})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self._make_splitter(tray_id=remote.id, input_output_id=parent.output_ids[0].id)

    def test_output_fusion_confirmation_and_upstream_trace_across_cascade(self):
        root_fiber, output_fiber = self.input_cable.fiber_ids[0], self.output_cable.fiber_ids[0]
        parent = self._make_splitter(input_fiber_id=root_fiber.id)
        child = self._make_splitter(input_output_id=parent.output_ids[0].id, tray_id=self.tray_2.id)
        output = child.output_ids[0]
        rest = self.env["fiber.gis.tray.line"].create({
            "tray_id": self.tray_1.id, "position": 2, "line_type": "free", "input_fiber_id": output_fiber.id,
        })
        action = self.env["fiber.gis.splitter.drop.wizard"].create({
            "splitter_id": child.id, "output_id": output.id, "operation": "fusion",
            "cable_id": self.output_cable.id, "fiber_id": output_fiber.id,
        }).action_connect()
        self.assertEqual(action["res_model"], "fiber.gis.cable.tray.confirm.wizard")
        self.assertTrue(rest.exists())
        self.assertFalse(output.output_fiber_id)
        wizard = self.env["fiber.gis.cable.tray.wizard"].browse(action["context"]["default_tray_wizard_id"])
        wizard.action_apply_confirmed()
        self.assertFalse(rest.exists())
        self.assertEqual(output.output_fiber_id, output_fiber)
        trace = self.env["fiber.gis.trace.wizard"].create({
            "node_id": self.destination.id, "fiber_id": output_fiber.id,
        })._get_trace_data()
        self.assertIn(self.input_cable.id, trace["cable_ids"])
        self.assertIn(self.source.id, trace["node_ids"])
        output._disconnect()
        self.assertTrue(output_fiber.exists())
        self.assertFalse(output.is_connected)
