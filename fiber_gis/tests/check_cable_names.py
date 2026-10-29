"""Pruebas aisladas de nombres manuales, tipologias, extremos y empleados."""
import ast
from datetime import datetime
from pathlib import Path
from types import MethodType, SimpleNamespace as Record
import unittest

ROOT = Path(__file__).resolve().parents[1]


def method(path, name):
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8-sig"))
    function = next(item for item in ast.walk(tree) if isinstance(item, ast.FunctionDef) and item.name == name)
    function.decorator_list = []
    namespace = {"ValidationError": ValueError, "fields": Record(Datetime=Record(context_timestamp=lambda self, value: value))}
    exec(compile(ast.Module(body=[function], type_ignores=[]), path, "exec"), namespace)
    return namespace[name]


class Records(list):
    def __or__(self, other):
        return Records(list(self) + [item for item in other if all(item is not old for old in self)])
    def filtered(self, predicate):
        return Records(item for item in self if predicate(item))
    def sorted(self, field):
        return Records(sorted(self, key=lambda item: getattr(item, field)))


class CableChecks(unittest.TestCase):
    def test_no_automatic_name_hooks_remain(self):
        for filename in ("models/cable.py", "models/node.py", "migrations/19.0.3.35.0/post-cable-names.py"):
            self.assertNotIn("_refresh_endpoint_names", (ROOT / filename).read_text(encoding="utf-8-sig"))
        tree = ast.parse((ROOT / "models/cable.py").read_text(encoding="utf-8-sig"))
        cls = next(item for item in tree.body if isinstance(item, ast.ClassDef))
        name = next(item.value for item in cls.body if isinstance(item, ast.Assign) and item.targets[0].id == "name")
        self.assertFalse(any(keyword.arg == "readonly" for keyword in name.keywords))

    def test_restore_only_generated_names(self):
        restore = method("migrations/19.0.3.37.0/post-cable-profiles.py", "original_manual_name")
        cable = Record(from_node_id=Record(code="A", name="Origen"), to_node_id=Record(code="B", name="Destino", address="Calle Real 5"),
                       name="A B Calle Real 5", previous_name="Cable elegido por tecnico")
        self.assertEqual(restore(cable), cable.previous_name)
        cable.name = "Ya corregido"
        self.assertFalse(restore(cable))
        cable.previous_name = False
        self.assertFalse(restore(cable))

    def test_profile_totals(self):
        profiles = [Record(tube_count=0, fiber_count=12), Record(tube_count=4, fiber_count=6)]
        method("models/cable_profile.py", "_compute_total")(profiles)
        self.assertEqual([item.total_fiber_count for item in profiles], [12, 24])

    def test_profile_overrides_stale_form_counts(self):
        profile = Record(id=7, tube_count=4, fiber_count=6, gis_type_id=False)
        profile.exists = lambda: profile
        model = Record(browse=lambda identifier: profile)
        values = method("models/cable.py", "_prepare_profile_values")(
            Record(env={"fiber.gis.cable.profile": model}), {"profile_id": 7, "fiber_count": 12, "tube_count": 0, "name": "Manual"})
        self.assertEqual(values, {"profile_id": 7, "fiber_count": 6, "tube_count": 4, "name": "Manual"})

    def test_reduction_rejected_without_deleting_fibers(self):
        fibers = Records([Record(number=1), Record(number=12)])
        cable = Record(fiber_count=6, tube_count=0, fiber_ids=fibers, profile_id=False)
        with self.assertRaisesRegex(ValueError, "No se puede reducir"):
            method("models/cable.py", "_check_fiber_topology")([cable])
        self.assertEqual([fiber.number for fiber in fibers], [1, 12])

    def test_profile_mismatch_rejected(self):
        cable = Record(fiber_count=12, tube_count=0, fiber_ids=Records(), profile_id=Record(fiber_count=6, tube_count=4))
        with self.assertRaisesRegex(ValueError, "coincidir"):
            method("models/cable.py", "_check_fiber_topology")([cable])

    def fiber(self):
        fiber = Record(tray_input_line_ids=Records(), tray_output_line_ids=Records(), splitter_input_ids=Records(),
                       splitter_output_ids=Records(), port_ids=Records())
        fiber._operation_detail = MethodType(method("models/fiber.py", "_operation_detail"), fiber)
        fiber._endpoint_connections = MethodType(method("models/fiber.py", "_endpoint_connections"), fiber)
        return fiber

    def test_each_end_has_its_own_operation(self):
        fiber = self.fiber()
        origin = Record(display_name="Caja A", address="Calle Real 5")
        destination = Record(display_name="Caja B", address="Calle Sol 8", _fiber_endpoint_label=lambda other: "Caja C - Calle Luna 2")
        other = Record(number=7, tube=2, show_tube=True, cable_id=Record(display_name="Cable manual"))
        common = dict(splitter_id=False, tray_id=Record(display_name="Bandeja 1"), employee_id=Record(name="Ana"), work_date=datetime(2026, 8, 28, 10, 30))
        fiber.tray_input_line_ids = Records([
            Record(node_id=origin, position=1, line_type="free", input_fiber_id=fiber, output_fiber_id=False, **common),
            Record(node_id=destination, position=2, line_type="fusion", input_fiber_id=fiber, output_fiber_id=other, **common),
        ])
        left, right = fiber._endpoint_connections(origin), fiber._endpoint_connections(destination)
        self.assertIn("Fibra en punta", left)
        self.assertNotIn("Fusi\u00f3n", left)
        self.assertIn("Fusi\u00f3n", right)
        self.assertIn("Cable manual T2 F7", right)
        self.assertIn("Calle Luna 2", right)
        self.assertIn("Ana", right)
        self.assertIn("28/08/2026 10:30", right)

    def test_splitter_details_without_duplicate_tray_entry(self):
        fiber = self.fiber()
        node = Record(display_name="CTO", address="Calle Luz 3")
        splitter = Record(node_id=node, display_name="SP1", ratio="1:8", tray_id=Record(display_name="Bandeja 2"), employee_id=False, work_date=False)
        fiber.splitter_input_ids = Records([splitter])
        fiber.tray_input_line_ids = Records([Record(node_id=node, position=1, splitter_id=splitter)])
        self.assertEqual(fiber._endpoint_connections(node).count("SP1"), 1)
        fiber.splitter_input_ids = Records()
        fiber.splitter_output_ids = Records([Record(node_id=node, splitter_id=splitter, sequence=5, employee_id=Record(name="Luis"), work_date=False)])
        self.assertIn("salida 5", fiber._endpoint_connections(node))
        self.assertIn("Luis", fiber._endpoint_connections(node))

    def test_unconnected_end_is_not_globally_marked_used(self):
        self.assertIn("Sin conexi\u00f3n registrada", self.fiber()._endpoint_connections(Record(display_name="Caja D", address=False)))

    def test_persistent_employee_defaults_do_not_rewrite_history(self):
        for filename in ("tray.py", "splitter.py", "work_log.py", "port.py", "fiber.py"):
            tree = ast.parse((ROOT / "models" / filename).read_text(encoding="utf-8-sig"))
            for item in ast.walk(tree):
                if isinstance(item, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "employee_id" for target in item.targets) and isinstance(item.value, ast.Call):
                    if isinstance(item.value.func, ast.Attribute) and item.value.func.attr == "Many2one":
                        self.assertEqual(item.value.args[0].value, "hr.employee.public")
                        self.assertNotIn("default", [keyword.arg for keyword in item.value.keywords])

    def test_selected_employee_context_propagation(self):
        for filename in ("cable_tray_wizard.py", "splitter_drop_wizard.py"):
            self.assertIn("self.with_context(fiber_gis_employee_id=self.employee_id.id or False)", (ROOT / "models" / filename).read_text(encoding="utf-8-sig"))
        self.assertIn('with_context(skip_fiber_work_log=True).write', (ROOT / "models/fiber.py").read_text(encoding="utf-8-sig"))

    def test_employee_selector_does_not_guess(self):
        helper = method("models/work_log.py", "work_employee_id")
        class Employees(Records):
            @property
            def id(self):
                return self[0].id if self else False
            def search(self, domain, limit):
                return self
            def browse(self, identifier):
                return Employees(item for item in self if item.id == identifier)
            def exists(self):
                return self
            def check_access(self, mode):
                assert mode == "read"
        class Env(dict):
            context = {}
            uid = 9
            company = Record(id=1)
        employees = Employees([Record(id=101), Record(id=102)])
        env = Env({"hr.employee.public": employees})
        self.assertFalse(helper(env))
        employees.pop()
        self.assertEqual(helper(env), 101)
        env.context = {"fiber_gis_employee_id": False}
        self.assertFalse(helper(env))
        env.context = {"fiber_gis_employee_id": 101}
        self.assertEqual(helper(env), 101)


if __name__ == "__main__":
    unittest.main(verbosity=2)
