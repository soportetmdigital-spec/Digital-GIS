"""Copia de seguridad completa y restauración sin duplicados."""
import base64
import io
import json
import zipfile

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user

PIXEL_PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


class TestBackupRestore(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager = new_test_user(
            cls.env, login="gis_backup_manager",
            groups="base.group_user,fiber_gis.group_fiber_gis_manager",
        )
        cls.technician = new_test_user(
            cls.env, login="gis_backup_technician",
            groups="base.group_user,fiber_gis.group_fiber_gis_user",
        )
        node_model = cls.env["fiber.gis.node"]
        cls.source = node_model.create({"name": "Origen copia", "code": "TEST-BACKUP-SOURCE"})
        cls.box = node_model.create({
            "name": "CTO copia", "code": "TEST-BACKUP-BOX", "has_trays": True, "tray_count": 2,
            "latitude": 37.18, "longitude": -3.60,
        })
        cls.cable = cls.env["fiber.gis.cable"].create({
            "name": "Cable copia", "from_node_id": cls.source.id, "to_node_id": cls.box.id, "fiber_count": 12,
        })
        cls.splitter = cls.env["fiber.gis.splitter"].create({
            "tray_id": cls.box.tray_ids.sorted("sequence")[0].id,
            "ratio": "1:4",
            "input_fiber_id": cls.cable.fiber_ids.sorted("number")[0].id,
        })
        cls.env["fiber.gis.node.photo"].create({"node_id": cls.box.id, "image": PIXEL_PNG})
        cls.plan = cls.env["fiber.gis.deployment.plan"].create({"name": "Plan copia"})
        cls.box.deployment_plan_id = cls.plan
        cls.env["fiber.gis.splice.document"].create({
            "node_id": cls.box.id, "kind": "excel", "file_name": "Carta copia.xlsx",
            "file_data": base64.b64encode(b"carta de empalme"),
        })
        cabinet = cls.env["fiber.gis.cabinet"].create({"name": "Cabecera copia", "height_u": 6, "node_id": cls.box.id})
        equipment = cls.env["fiber.gis.cabinet.equipment"]
        panel = equipment.create({"cabinet_id": cabinet.id, "name": "Panel copia", "kind": "patch_panel", "position_u": 1})
        switch = equipment.create({"cabinet_id": cabinet.id, "name": "Switch copia", "kind": "switch", "position_u": 3})
        panel.port_ids.filtered(lambda port: port.number == 2).fiber_id = cls.cable.fiber_ids.sorted("number")[1]
        cls.env["fiber.gis.cabinet.interconnection"].create({
            "group_cabinet_id": cabinet.id, "from_equipment_id": panel.id, "from_port": 1,
            "to_equipment_id": switch.id, "to_port": 1,
        })

    def _counts(self):
        wizard_model = self.env["fiber.gis.settings.wizard"]
        return {
            name: self.env[name].with_context(active_test=False).search_count([])
            for name in wizard_model._backup_model_names()
        }

    def _backup(self):
        wizard = self.env["fiber.gis.settings.wizard"].with_user(self.manager).create({})
        content, _name = wizard._build_backup_zip()
        return wizard, content

    def test_restore_recreates_the_same_records_without_duplicates(self):
        before = self._counts()
        wizard, content = self._backup()
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual(manifest["format"], 2)
            for name in ("fiber.gis.cabinet", "fiber.gis.splice.document", "fiber.gis.deployment.plan"):
                self.assertIn(name, manifest["models"])
        wizard.write({"backup_file": base64.b64encode(content)})
        wizard.action_restore_backup()
        self.assertEqual(self._counts(), before)

        box = self.env["fiber.gis.node"].search([("code", "=", "TEST-BACKUP-BOX")])
        self.assertEqual(len(box), 1)
        self.assertEqual(len(box.tray_ids), 2)
        self.assertEqual(box.deployment_plan_id.name, "Plan copia")
        photo = self.env["fiber.gis.node.photo"].search([("node_id", "=", box.id)])
        self.assertTrue(photo.image)
        cable = self.env["fiber.gis.cable"].search([("name", "=", "Cable copia")])
        self.assertEqual(len(cable.fiber_ids), 12)
        splitter = self.env["fiber.gis.splitter"].search([("node_id", "=", box.id)])
        self.assertEqual(len(splitter), 1)
        self.assertEqual(len(splitter.output_ids), 4)
        self.assertEqual(len(splitter.tray_line_ids), 1)
        self.assertEqual(splitter.input_fiber_id.cable_id, cable)
        self.assertEqual(splitter.input_fiber_id.state, "used")
        document = self.env["fiber.gis.splice.document"].search([("node_id", "=", box.id)])
        self.assertEqual(base64.b64decode(document.file_data), b"carta de empalme")
        cabinet = self.env["fiber.gis.cabinet"].search([("name", "=", "Cabecera copia")])
        self.assertEqual(cabinet.node_id, box)
        panel = cabinet.equipment_ids.filtered(lambda item: item.kind == "patch_panel")
        self.assertEqual(len(panel.port_ids), 24)
        assigned = panel.port_ids.filtered("fiber_id")
        self.assertEqual(assigned.number, 2)
        self.assertEqual(assigned.fiber_id, cable.fiber_ids.filtered(lambda fiber: fiber.number == 2))
        self.assertEqual(len(cabinet.interconnection_ids), 1)

    def test_only_managers_can_use_settings_and_backups(self):
        with self.assertRaises(AccessError):
            self.env["fiber.gis.settings.wizard"].with_user(self.technician).create({})
        wizard = self.env["fiber.gis.settings.wizard"].create({})
        for action in ("action_create_backup", "action_restore_backup", "action_save_settings"):
            with self.subTest(action=action), self.assertRaises(AccessError):
                getattr(wizard.with_user(self.technician), action)()
        config_menu = self.env.ref("fiber_gis.menu_fiber_gis_config")
        self.assertEqual(config_menu.group_ids, self.env.ref("fiber_gis.group_fiber_gis_manager"))

    def test_cable_profile_display_name_includes_gis_type(self):
        profile = self.env["fiber.gis.cable.profile"].create({"name": "Perfil copia", "fiber_count": 4})
        self.assertEqual(profile.display_name, "Perfil copia - Tipo GIS: Sin definir")
