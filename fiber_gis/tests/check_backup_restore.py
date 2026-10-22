"""Pruebas aisladas de permisos de Ajustes y de la copia de seguridad completa."""
import ast
import csv
from pathlib import Path
from types import SimpleNamespace as Field
import unittest

ROOT = Path(__file__).resolve().parents[1]


def method(path, name):
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8-sig"))
    function = next(item for item in ast.walk(tree) if isinstance(item, ast.FunctionDef) and item.name == name)
    function.decorator_list = []
    namespace = {}
    exec(compile(ast.Module(body=[function], type_ignores=[]), path, "exec"), namespace)
    return namespace[name]


class BackupRestoreChecks(unittest.TestCase):
    def test_configuration_menus_are_restricted_to_managers(self):
        # En Odoo 19 un prefijo «-» en groups de menuitem quita el grupo (Command.unlink).
        for filename in ("views/fiber_gis_menus.xml", "views/fiber_gis_settings_views.xml"):
            text = (ROOT / filename).read_text(encoding="utf-8")
            self.assertNotIn('groups="-', text)
        self.assertIn('groups="fiber_gis.group_fiber_gis_manager"', (ROOT / "views/fiber_gis_menus.xml").read_text(encoding="utf-8"))

    def test_settings_wizard_is_manager_only(self):
        with (ROOT / "security/ir.model.access.csv").open(encoding="utf-8") as handle:
            rows = [row for row in csv.DictReader(handle) if row["model_id:id"] == "model_fiber_gis_settings_wizard"]
        self.assertEqual([row["group_id:id"] for row in rows], ["fiber_gis.group_fiber_gis_manager"])
        source = (ROOT / "models/settings.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        actions = [item for item in ast.walk(tree) if isinstance(item, ast.FunctionDef) and item.name.startswith("action_")]
        self.assertTrue(actions)
        for action in actions:
            calls = {node.func.attr for node in ast.walk(action) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
            self.assertIn("_check_fiber_gis_manager", calls, action.name)

    def test_backup_includes_every_persistent_model(self):
        names = method("models/settings.py", "_backup_model_names")(None)
        for name in (
            "fiber.gis.deployment.plan", "fiber.gis.splice.document", "fiber.gis.cabinet.catalog",
            "fiber.gis.cabinet", "fiber.gis.cabinet.equipment", "fiber.gis.cabinet.port",
            "fiber.gis.cabinet.interconnection",
        ):
            self.assertIn(name, names)
        self.assertEqual(len(names), len(set(names)))
        self.assertLess(names.index("fiber.gis.splitter.output"), names.index("fiber.gis.tray.line"))

    def test_restorable_fields(self):
        restorable = method("models/settings.py", "_is_restorable_field")
        self.assertTrue(restorable(None, Field(store=True, type="binary", compute=None, readonly=False)))
        self.assertTrue(restorable(None, Field(store=True, type="many2many", compute=None, readonly=False)))
        self.assertFalse(restorable(None, Field(store=True, type="one2many", compute=None, readonly=False)))
        self.assertFalse(restorable(None, Field(store=False, type="many2many", compute="_compute", readonly=True)))
        self.assertFalse(restorable(None, Field(store=True, type="float", compute="_compute_related", readonly=True)))

    def test_binary_values_from_old_backups_are_decoded(self):
        decode = method("models/settings.py", "_restore_binary_value")
        self.assertEqual(decode(None, "b'iVBORw0'"), "iVBORw0")
        self.assertEqual(decode(None, "iVBORw0"), "iVBORw0")
        self.assertFalse(decode(None, False))

    def test_restore_does_not_regenerate_child_records(self):
        for filename in ("models/node.py", "models/cable.py", "models/splitter.py", "models/cabinet.py"):
            self.assertIn('context.get("fiber_gis_restore")', (ROOT / filename).read_text(encoding="utf-8"))

    def test_cable_profile_uses_compute_display_name(self):
        source = (ROOT / "models/cable_profile.py").read_text(encoding="utf-8")
        self.assertNotIn("def name_get", source)
        self.assertIn("def _compute_display_name", source)


if __name__ == "__main__":
    unittest.main()
