"""Pruebas ORM: ejecutar con Odoo 19 y --test-tags /fiber_gis."""
from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase
from odoo.tests.common import new_test_user


class TestCableProfilesAndTechnicians(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tech = cls.env["hr.employee"].create({"name": "Tecnica GIS Ana"})
        cls.public_tech = cls.env["hr.employee.public"].browse(cls.tech.id)
        cls.source, cls.box, cls.end = cls.env["fiber.gis.node"].create([
            {"name": "Origen", "code": "QA-PROFILE-A", "has_trays": True, "tray_count": 1, "address": "Calle A 1"},
            {"name": "Caja", "code": "QA-PROFILE-B", "has_trays": True, "tray_count": 2, "address": "Calle B 2"},
            {"name": "Destino", "code": "QA-PROFILE-C", "address": "Calle C 3"},
        ])
        cls.profile = cls.env["fiber.gis.cable.profile"].create({"name": "Prueba 4x6", "tube_count": 4, "fiber_count": 6})
        cls.cable = cls.env["fiber.gis.cable"].create({
            "name": "Cable manual", "code": "ID-PRUEBA", "from_node_id": cls.source.id,
            "to_node_id": cls.box.id, "profile_id": cls.profile.id,
        })
        cls.other = cls.env["fiber.gis.cable"].create({
            "name": "Cable salida", "from_node_id": cls.box.id, "to_node_id": cls.end.id, "fiber_count": 12,
        })
        cls.tray = cls.box.tray_ids.sorted("sequence")[0]

    def wizard(self, **values):
        user = values.pop("user", None)
        defaults = {"operation": "rest", "node_id": self.box.id, "tray_id": self.tray.id,
                    "cable_id": self.cable.id, "employee_id": self.tech.id,
                    "selected_fiber_ids": [fields.Command.set(self.cable.fiber_ids[:1].ids)]}
        defaults.update(values)
        model = self.env["fiber.gis.cable.tray.wizard"]
        return (model.with_user(user) if user else model).create(defaults)

    def test_profile_copies_counts_and_generates_exact_fibers(self):
        self.assertEqual((self.cable.tube_count, self.cable.fiber_count, self.cable.total_fiber_count), (4, 6, 24))
        self.assertEqual(len(self.cable.fiber_ids), 24)
        self.assertEqual(self.cable.fiber_ids[6].tube, 2)
        self.assertEqual(self.cable.fiber_ids[6].color, self.cable.fiber_ids[0].color)
        self.assertTrue(self.cable.fiber_ids[0].tube_color)
        self.assertTrue(self.cable.fiber_ids[0].color)

    def test_changing_profile_updates_total_and_generates_remaining_fibers(self):
        """Comprueba que una nueva tipología actualiza el total y completa la lista sin sustituir fibras."""
        profile = self.env["fiber.gis.cable.profile"].create({
            "name": "Prueba 5x6", "tube_count": 5, "fiber_count": 6,
        })
        original_fiber_ids = self.cable.fiber_ids.ids

        self.cable.write({"profile_id": profile.id})

        self.assertEqual(self.cable.total_fiber_count, 30)
        self.assertEqual(len(self.cable.fiber_ids), 30)
        self.assertEqual(self.cable.fiber_ids[:24].ids, original_fiber_ids)
        self.assertEqual(self.cable.fiber_ids[24].tube, 5)
        self.assertTrue(self.cable.fiber_ids[24].tube_color)
        self.assertTrue(self.cable.fiber_ids[24].color)

    def test_profile_updates_archived_cable_without_replacing_ids(self):
        identifiers = self.cable.fiber_ids.ids
        self.cable.active = False
        self.profile.write({"tube_count": 5})
        self.assertEqual(self.cable.total_fiber_count, 30)
        self.assertEqual(self.cable.fiber_ids[:24].ids, identifiers)
        self.assertEqual(self.cable.name, "Cable manual")
        self.assertEqual(self.cable.code, "ID-PRUEBA")

    def test_reduction_rolls_back_catalogue_and_cables(self):
        identifiers = self.cable.fiber_ids.ids
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.profile.write({"tube_count": 1})
        self.assertEqual(self.profile.tube_count, 4)
        self.assertEqual(self.cable.fiber_ids.ids, identifiers)

    def test_same_total_profile_keeps_fusion(self):
        self.wizard(operation="fusion", other_cable_id=self.other.id,
                    fusion_input_fiber_ids=[fields.Command.set(self.cable.fiber_ids[:1].ids)],
                    fusion_output_fiber_ids=[fields.Command.set(self.other.fiber_ids[:1].ids)]).action_apply()
        line = self.tray.line_ids
        profile = self.env["fiber.gis.cable.profile"].create({"name": "24 fibras", "tube_count": 0, "fiber_count": 24})
        self.cable.write({"profile_id": profile.id})
        self.assertTrue(line.exists())
        self.assertEqual(line.input_fiber_id, self.cable.fiber_ids[0])
        self.assertFalse(self.cable.fiber_ids[0].tube)

    def test_rest_employee_and_actor_are_separate(self):
        self.wizard().action_apply()
        self.assertEqual(self.tray.line_ids.employee_id, self.public_tech)
        logs = self.box.work_log_ids.filtered(lambda log: log.employee_id == self.public_tech)
        self.assertTrue(logs)
        self.assertEqual(logs[0].user_id, self.env.user)
        self.assertEqual(logs[0].employee_name, self.tech.name)
        self.assertFalse(self.cable.fiber_ids[0].employee_id, "Sin inventar una revision manual por el cambio automatico de estado")

    def test_wizard_hides_fusions_and_splitter_inputs_only(self):
        rest_fiber = self.cable.fiber_ids[0]
        fused_fiber = self.cable.fiber_ids[1]
        splitter_fiber = self.cable.fiber_ids[2]
        self.wizard().action_apply()
        self.wizard(
            operation="fusion",
            other_cable_id=self.other.id,
            fusion_input_fiber_ids=[fields.Command.set(fused_fiber.ids)],
            fusion_output_fiber_ids=[fields.Command.set(self.other.fiber_ids[:1].ids)],
        ).action_apply()
        self.wizard(
            operation="splitter",
            selected_fiber_ids=[fields.Command.set(splitter_fiber.ids)],
        ).action_apply()

        at_box = self.wizard()
        self.assertIn(rest_fiber, at_box.available_fiber_ids)
        self.assertNotIn(fused_fiber, at_box.available_fiber_ids)
        self.assertNotIn(splitter_fiber, at_box.available_fiber_ids)
        self.assertIn(self.cable.fiber_ids[3], at_box.available_fiber_ids)

        at_source = self.env["fiber.gis.cable.tray.wizard"].create({
            "operation": "rest",
            "node_id": self.source.id,
            "tray_id": self.source.tray_ids[:1].id,
            "cable_id": self.cable.id,
        })
        self.assertIn(fused_fiber, at_source.available_fiber_ids)

    def test_pass_cable_links_incoming_and_outgoing_fibers_and_leaves_cut_fiber_free(self):
        cut_fiber = self.cable.fiber_ids[1]
        pass_output = self.env["fiber.gis.cable"].create({
            "name": "Cable de paso salida",
            "from_node_id": self.box.id,
            "to_node_id": self.end.id,
            "profile_id": self.profile.id,
        })
        wizard = self.wizard(
            operation="pass",
            pass_output_cable_id=pass_output.id,
            selected_fiber_ids=[fields.Command.set(cut_fiber.ids)],
        )

        wizard.action_apply()

        pass_lines = self.tray.line_ids.filtered(lambda line: line.line_type == "pass")
        cut_line = self.tray.line_ids.filtered(lambda line: line.line_type == "free")
        self.assertEqual(len(pass_lines), self.cable.total_fiber_count - 1)
        self.assertTrue(all(line.tray_id == self.tray for line in pass_lines | cut_line))
        first_pair = pass_lines.filtered(lambda line: line.input_fiber_id == self.cable.fiber_ids[0])
        self.assertEqual(first_pair.output_fiber_id, pass_output.fiber_ids[0])
        self.assertEqual(cut_line.input_fiber_id, cut_fiber)
        self.assertFalse(cut_line.output_fiber_id)
        edit_action = first_pair.action_open_fiber(self.cable.fiber_ids[0].id)
        self.assertEqual(edit_action["res_model"], "fiber.gis.tray")
        self.assertEqual(edit_action["res_id"], self.tray.id)

        connections, detail = self.env["fiber.gis.trace.wizard"]._trace_connections(
            self.box, self.cable.fiber_ids[0]
        )
        self.assertEqual(connections[0][0], pass_output.fiber_ids[0])
        self.assertIn("Continuidad de paso", connections[0][1])
        self.assertFalse(detail)

    def test_pass_cable_selectors_name_the_adjacent_boxes(self):
        incoming_name = self.cable.with_context(
            fiber_gis_node_id=self.box.id, fiber_gis_show_boca=True
        ).display_name
        outgoing_name = self.other.with_context(
            fiber_gis_node_id=self.box.id, fiber_gis_show_boca=True
        ).display_name
        self.assertIn("Cable que viene de Origen", incoming_name)
        self.assertIn("Cable que va a Destino", outgoing_name)

    def test_pass_default_uses_a_real_outgoing_cable_with_matching_tubes_and_fibers(self):
        exact = self.env["fiber.gis.cable"].create({
            "name": "Salida 4x6 real",
            "from_node_id": self.box.id,
            "to_node_id": self.end.id,
            "profile_id": self.profile.id,
        })
        wizard = self.wizard(operation="pass")

        selected = wizard._default_pass_output_cable()

        self.assertEqual(selected, exact)
        self.assertEqual(len(selected.fiber_ids), 24)
        self.assertEqual(selected.fiber_ids[0].tube, 1)
        self.assertEqual(selected.fiber_ids[6].tube, 2)

    def test_pass_can_register_more_than_thirty_jobs_in_one_tray(self):
        profile = self.env["fiber.gis.cable.profile"].create({
            "name": "Prueba 43 fibras sin límite", "tube_count": 0, "fiber_count": 43,
        })
        incoming = self.env["fiber.gis.cable"].create({
            "name": "Entrada 43 fibras", "from_node_id": self.source.id,
            "to_node_id": self.box.id, "profile_id": profile.id,
        })
        outgoing = self.env["fiber.gis.cable"].create({
            "name": "Salida 43 fibras", "from_node_id": self.box.id,
            "to_node_id": self.end.id, "profile_id": profile.id,
        })
        wizard = self.wizard(
            operation="pass", cable_id=incoming.id, pass_output_cable_id=outgoing.id,
            selected_fiber_ids=[fields.Command.clear()],
        )

        wizard.action_apply()

        lines = self.tray.line_ids.filtered(lambda line: line.line_type == "pass")
        self.assertEqual(len(lines), 43)
        self.assertEqual(self.tray.used_positions, 43)
        self.assertEqual(self.tray.free_positions, -1)

    def test_one_tray_can_keep_pass_strands_a_cut_fiber_and_a_splitter(self):
        pass_output = self.env["fiber.gis.cable"].create({
            "name": "Cable de paso mixto",
            "from_node_id": self.box.id,
            "to_node_id": self.end.id,
            "profile_id": self.profile.id,
        })
        cut_fibers = self.cable.fiber_ids[:2]
        self.wizard(
            operation="pass",
            pass_output_cable_id=pass_output.id,
            selected_fiber_ids=[fields.Command.set(cut_fibers.ids)],
        ).action_apply()

        splitter_wizard = self.wizard(
            operation="splitter",
            splitter_ratio="1:4",
            selected_fiber_ids=[fields.Command.set(cut_fibers[:1].ids)],
        )
        action = splitter_wizard.action_apply()
        self.assertEqual(action["res_model"], "fiber.gis.cable.tray.confirm.wizard")
        splitter_wizard.action_apply_confirmed()

        self.assertEqual(len(self.tray.line_ids.filtered(lambda line: line.line_type == "pass")), 22)
        self.assertEqual(
            self.tray.line_ids.filtered(lambda line: line.line_type == "free").input_fiber_id,
            cut_fibers[1],
        )
        self.assertEqual(self.box.splitter_ids.tray_id, self.tray)

    def test_pass_requires_both_cable_segments_to_face_the_box_correctly(self):
        wizard = self.wizard(
            operation="pass",
            pass_output_cable_id=self.cable.id,
            selected_fiber_ids=[fields.Command.set(self.cable.fiber_ids[:1].ids)],
        )
        with self.assertRaisesRegex(UserError, "distintos"):
            wizard.action_apply()

    def test_every_tray_operation_requires_an_explicit_tray(self):
        wizard = self.wizard(tray_id=False)
        with self.assertRaisesRegex(UserError, "Selecciona la bandeja"):
            wizard.action_apply()

    def test_opening_existing_fiber_preserves_it_in_assistant_choices(self):
        self.wizard().action_apply()
        line = self.tray.line_ids.filtered(lambda item: item.input_fiber_id == self.cable.fiber_ids[0])

        action = line.action_open_fiber(self.cable.fiber_ids[0].id)
        assistant = self.env[action["res_model"]].browse(action["res_id"])

        self.assertIn(self.cable.fiber_ids[0], assistant.available_fiber_ids)

    def test_moving_fibers_resequences_both_trays_by_tube_and_number(self):
        fibers = self.cable.fiber_ids
        source_lines = self.env["fiber.gis.tray.line"].create([
            {"tray_id": self.tray.id, "position": 1, "line_type": "free", "input_fiber_id": fibers[6].id},
            {"tray_id": self.tray.id, "position": 2, "line_type": "free", "input_fiber_id": fibers[0].id},
            {"tray_id": self.tray.id, "position": 3, "line_type": "free", "input_fiber_id": fibers[1].id},
        ])
        destination = self.box.tray_ids.sorted("sequence")[1]
        destination_line = self.env["fiber.gis.tray.line"].create({
            "tray_id": destination.id,
            "position": 1,
            "line_type": "free",
            "input_fiber_id": fibers[3].id,
        })

        self.env["fiber.gis.tray.line"].action_move_to_tray(source_lines[0].id, destination.id)

        self.assertEqual(self.tray.line_ids.sorted("position").mapped("input_fiber_number"), [1, 2])
        self.assertEqual(destination.line_ids.sorted("position").mapped("input_fiber_number"), [4, 7])
        self.assertEqual(source_lines[0].position, 2)
        self.assertEqual(destination_line.position, 1)

    def test_fusion_confirmation_preserves_selected_employee(self):
        self.wizard().action_apply()
        rest = self.tray.line_ids
        wizard = self.wizard(operation="fusion", other_cable_id=self.other.id,
                             fusion_input_fiber_ids=[fields.Command.set(self.cable.fiber_ids[:1].ids)],
                             fusion_output_fiber_ids=[fields.Command.set(self.other.fiber_ids[:1].ids)])
        action = wizard.action_apply()
        self.assertEqual(action["res_model"], "fiber.gis.cable.tray.confirm.wizard")
        self.assertTrue(rest.exists())
        wizard.action_apply_confirmed()
        self.assertFalse(rest.exists())
        self.assertEqual(self.tray.line_ids.employee_id, self.public_tech)

    def test_endpoint_details_are_local_to_each_end(self):
        self.env["fiber.gis.tray.line"].create({"tray_id": self.source.tray_ids.id, "line_type": "free", "input_fiber_id": self.cable.fiber_ids[0].id})
        self.wizard(operation="fusion", other_cable_id=self.other.id,
                    fusion_input_fiber_ids=[fields.Command.set(self.cable.fiber_ids[:1].ids)],
                    fusion_output_fiber_ids=[fields.Command.set(self.other.fiber_ids[6:7].ids)]).action_apply()
        fiber = self.cable.fiber_ids[0]
        self.assertIn("Fibra en punta", fiber.from_connection_summary)
        self.assertNotIn("Fusi\u00f3n", fiber.from_connection_summary)
        self.assertIn("Fusi\u00f3n", fiber.to_connection_summary)
        self.assertIn("F7", fiber.to_connection_summary)
        self.assertIn("Calle C 3", fiber.to_connection_summary)
        self.assertIn(self.tech.name, fiber.to_connection_summary)

    def test_splitter_installation_and_output_employee(self):
        self.wizard(operation="splitter", splitter_ratio="1:4").action_apply()
        splitter = self.box.splitter_ids
        self.assertEqual(splitter.employee_id, self.public_tech)
        self.assertEqual(splitter.tray_line_ids.employee_id, self.public_tech)
        output = splitter.output_ids[0]
        self.env["fiber.gis.splitter.drop.wizard"].create({
            "splitter_id": splitter.id, "output_id": output.id, "operation": "fusion",
            "cable_id": self.other.id, "fiber_id": self.other.fiber_ids[0].id, "employee_id": self.tech.id,
        }).action_connect()
        self.assertEqual(output.employee_id, self.public_tech)
        self.assertIn("salida 1", self.other.fiber_ids[0].from_connection_summary)
        self.assertIn(self.tech.name, self.other.fiber_ids[0].from_connection_summary)

    def test_cassette_splitter_ratios_are_available_in_tray_wizard(self):
        wizard_field = self.env["fiber.gis.cable.tray.wizard"]._fields["splitter_ratio"]
        options = dict(wizard_field._description_selection(self.env))
        self.assertIn("1:4 Casete", options)
        self.assertIn("1:8 Casete", options)

        for fiber_index, ratio, expected_outputs, expected_loss in (
            (0, "1:4 Casete", 4, 7.1),
            (1, "1:8 Casete", 8, 10.4),
        ):
            with self.subTest(ratio=ratio):
                wizard = self.wizard(
                    operation="splitter",
                    splitter_ratio=ratio,
                    selected_fiber_ids=[fields.Command.set([self.cable.fiber_ids[fiber_index].id])],
                )
                wizard.action_apply()
                splitter = self.box.splitter_ids.filtered(lambda item: item.ratio == ratio)
                self.assertEqual(len(splitter), 1)
                self.assertEqual(len(splitter.output_ids), expected_outputs)
                self.assertEqual(splitter.nominal_loss_db, expected_loss)

    def test_gis_user_can_select_employee_without_hr_access(self):
        user = new_test_user(self.env, login="gis_profile_user", groups="base.group_user,fiber_gis.group_fiber_gis_user")
        self.assertFalse(user.has_group("hr.group_hr_user"))
        self.public_tech.with_user(user).check_access("read")
        self.cable.with_user(user).write({"installation_employee_ids": [fields.Command.set(self.public_tech.ids)]})
        self.assertEqual(self.cable.installation_employee_ids, self.public_tech)
        self.wizard(user=user).action_apply()
        logs = self.box.work_log_ids.filtered(lambda log: log.user_id == user)
        self.assertTrue(logs)
        self.assertEqual(logs[0].employee_id, self.public_tech)

    def test_technical_history_is_available_for_all_main_gis_records(self):
        """Comprueba que el historial registra técnico, fecha y trabajo en las cuatro fichas GIS."""
        site = self.env["fiber.gis.site"].create({"name": "Sitio técnico QA"})
        self.wizard(operation="splitter", splitter_ratio="1:4").action_apply()
        splitter = self.box.splitter_ids[:1]
        self.assertTrue(splitter, "El asistente debe crear el splitter de prueba.")

        log_model = self.env["fiber.gis.node.work.log"]
        logs = log_model.create([
            {"node_id": self.box.id, "employee_id": self.public_tech.id, "work_type": "inspection", "description": "Revisión del elemento"},
            {"site_id": site.id, "employee_id": self.public_tech.id, "work_type": "maintenance", "description": "Mantenimiento del sitio"},
            {"cable_id": self.cable.id, "employee_id": self.public_tech.id, "work_type": "installation", "description": "Instalación del cable"},
            {"splitter_id": splitter.id, "employee_id": self.public_tech.id, "work_type": "repair", "description": "Reparación del splitter"},
        ])

        for parent, log in zip((self.box, site, self.cable, splitter), logs):
            self.assertIn(log, parent.work_log_ids)
            self.assertTrue(log.date)
            self.assertEqual(log.employee_id, self.public_tech)
            self.assertEqual(log.employee_name, self.tech.name)
            self.assertTrue(log.description)
