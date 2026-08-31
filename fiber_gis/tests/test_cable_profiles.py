"""Pruebas ORM: ejecutar con Odoo 19 y --test-tags /fiber_gis."""
from odoo import fields
from odoo.exceptions import ValidationError
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
        self.assertIn("Resto", fiber.from_connection_summary)
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
