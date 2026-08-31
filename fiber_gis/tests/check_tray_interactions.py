"""Pruebas aisladas sin Odoo y muestras HTML generadas por los metodos reales."""

import ast
import html
import json
from pathlib import Path
import sys
from types import MethodType, SimpleNamespace
import unittest

from lxml import etree

ROOT = Path(__file__).resolve().parents[1]


class Empty:
    def __bool__(self):
        return False

    def __getattr__(self, name):
        return self


EMPTY = Empty()


class Record(SimpleNamespace):
    def ensure_one(self):
        return self

    def check_access(self, operation):
        assert operation == "read"


def method(module, name):
    tree = ast.parse((ROOT / "models" / module).read_text(encoding="utf-8-sig"))
    function = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name)
    function.decorator_list = []
    namespace = {"html": html, "UserError": ValueError,
                 "fields": SimpleNamespace(Command=SimpleNamespace(set=lambda ids: (6, 0, ids)))}
    exec(compile(ast.Module(body=[function], type_ignores=[]), module, "exec"), namespace)
    return namespace[name]


def splitter(identifier, source=EMPTY, fiber=EMPTY):
    record = Record(id=identifier, display_name=f"Splitter {identifier}", input_output_id=source,
                    input_fiber_id=fiber, env={"fiber.gis.cable.fiber": EMPTY})
    record._upstream_fiber = MethodType(method("splitter.py", "_upstream_fiber"), record)
    return record


def action_samples():
    """Ejecuta las acciones Python reales, sin normalizacion de call_button."""
    view_ids = {
        "fiber_gis.view_fiber_gis_cable_tray_wizard_form": 101,
        "fiber_gis.view_fiber_gis_splitter_form": 102,
        "fiber_gis.view_fiber_gis_splitter_drop_wizard_form": 103,
    }

    class Env(dict):
        def ref(self, xmlid):
            return Record(id=view_ids[xmlid])

    class Fiber(Record):
        def __or__(self, other):
            return (self, other) if other else (self,)

        def exists(self):
            return self

    class WizardModel:
        def create(self, values):
            self.values = values
            return Record(id=201, _name="fiber.gis.cable.tray.wizard")

    left = Fiber(id=11, ids=[11], number=6, cable_id=Record(id=1))
    right = Fiber(id=12, ids=[12], number=3, cable_id=Record(id=2))
    wizard = WizardModel()
    env = Env({
        "fiber.gis.cable.fiber": Record(browse=lambda identifier: {11: left, 12: right}[identifier]),
        "fiber.gis.splitter.output": Record(search=lambda *args, **kwargs: EMPTY),
        "fiber.gis.cable.tray.wizard": wizard,
    })
    line = Record(id=41, splitter_id=EMPTY, node_id=Record(id=30), tray_id=Record(id=1),
                  input_fiber_id=left, output_fiber_id=right, line_type="fusion", notes=False, env=env)
    results = {}
    for identifier in (0, 11, 12):
        action = method("tray.py", "action_open_fiber")(line, identifier)
        results[f"fiber-{identifier}"] = {"action": action, "values": wizard.values}
    line.line_type, line.output_fiber_id = "free", EMPTY
    results["rest"] = {"action": method("tray.py", "action_open_fiber")(line), "values": wizard.values}
    root = Record(id=50, display_name="Splitter principal", _name="fiber.gis.splitter", env=env)
    root.action_open_form = MethodType(method("splitter.py", "action_open_form"), root)
    line.splitter_id = root
    results["splitter"] = {"action": method("tray.py", "action_open_fiber")(line)}
    line.splitter_id = EMPTY
    env["fiber.gis.splitter.output"].search = lambda *args, **kwargs: Record(splitter_id=root)
    results["connected-output"] = {"action": method("tray.py", "action_open_fiber")(line)}
    for number in range(1, 5):
        output = Record(id=60 + number, sequence=number, splitter_id=root, env=env)
        results[f"output-{60 + number}"] = {"action": method("splitter.py", "action_manage_connection")(output)}
    return results


def samples():
    node = Record(id=30)
    remote = Record(display_name="Caja de destino", address="Calle San Ant\u00f3n 63, Granada")
    cable = Record(display_name="Cable principal", from_node_id=node, to_node_id=remote)
    fiber = Record(id=11, number=6, tube=2, tube_color="#ffa500", color="#ffffff", cable_id=cable)
    other_cable = Record(display_name="Cable de salida", from_node_id=node, to_node_id=remote)
    other = Record(id=12, number=3, tube=0, tube_color=False, color="#008000", cable_id=other_cable)
    for name in ("_fiber_endpoint_html", "_fiber_endpoint_label", "_format_fiber_endpoint", "_tray_line_visual_html"):
        setattr(node, name, MethodType(method("node.py", name), node))
    line = Record(id=41, line_type="fusion", position=1, input_fiber_id=fiber, output_fiber_id=other,
                  input_tube=fiber.tube, input_tube_color=fiber.tube_color, input_fiber_color=fiber.color,
                  output_tube=0, output_tube_color=False, output_fiber_color=other.color,
                  splitter_id=EMPTY, splitter_ratio=False, notes=False,
                  _fields={"line_type": Record(selection=[("fusion", "Fusi\u00f3n")])})
    root = splitter(50, fiber=fiber)
    root._fiber_html = MethodType(method("splitter.py", "_fiber_html"), root)
    root._fiber_remote_label = lambda item: node._fiber_endpoint_label(item) if item else ""
    root.name, root.ratio, root.connected_output_count, root.output_count = "Splitter principal", "1:4", 1, 4
    ports = [Record(id=60 + i, sequence=i, output_fiber_id=other if i == 1 else EMPTY,
                    downstream_splitter_ids=[], destination_label=node._fiber_endpoint_label(other),
                    state="connected" if i == 1 else "free",
                    _fields={"state": Record(selection=[("free", "Libre")])}) for i in range(1, 5)]

    class Ports(list):
        def sorted(self, key):
            return sorted(self, key=lambda item: getattr(item, key))

    root.output_ids = Ports(ports)
    return {
        "tray": node._tray_line_visual_html(line),
        "context": "<div class='o_fiber_context_info'><strong>Situaci\u00f3n actual: Bandeja 1 - Fusi\u00f3n</strong>"
                   + node._fiber_endpoint_html(fiber, fiber.tube, fiber.tube_color, fiber.color)
                   + node._fiber_endpoint_html(other, 0, False, other.color) + "</div>",
        "splitter": method("splitter.py", "_build_diagram_html")(root),
        "actions": action_samples(),
    }


class TrayInteractionChecks(unittest.TestCase):
    def test_raw_actions_include_form_views(self):
        for name, sample in action_samples().items():
            with self.subTest(action=name):
                action = sample["action"]
                self.assertEqual(action["type"], "ir.actions.act_window")
                self.assertEqual(action["target"], "new")
                self.assertTrue(action.get("views"), "La llamada directa no completa views")
                self.assertEqual([view[1] for view in action["views"]], ["form"])
                expected = 103 if name.startswith("output-") else 102 if name in ("splitter", "connected-output") else 101
                self.assertEqual(action["views"][0][0], expected)

    def test_actions_preserve_selected_cable_and_fiber(self):
        actions = action_samples()
        for identifier, cable, number in ((11, 1, 6), (12, 2, 3)):
            values = actions[f"fiber-{identifier}"]["values"]
            self.assertEqual(values["cable_id"], cable)
            self.assertEqual(values["source_fiber_id"], identifier)
            self.assertEqual(values["from_fiber"], number)
            self.assertEqual(values["fusion_input_fiber_ids"], [(6, 0, [identifier])])
        self.assertEqual(actions["rest"]["values"]["operation"], "rest")
        self.assertEqual(actions["splitter"]["action"]["res_id"], 50)
        for identifier in range(61, 65):
            self.assertEqual(actions[f"output-{identifier}"]["action"]["context"]["default_output_id"], identifier)

    def test_upstream_three_splitters(self):
        fiber = Record(id=501)
        first = splitter(1, fiber=fiber)
        second = splitter(2, source=Record(sequence=3, splitter_id=first))
        third = splitter(3, source=Record(sequence=2, splitter_id=second))
        result, path = third._upstream_fiber()
        self.assertIs(result, fiber)
        self.assertEqual(path, ["Splitter 3", "salida 2", "Splitter 2", "salida 3", "Splitter 1"])

    def test_disconnected_cascade_does_not_invent_fiber(self):
        self.assertFalse(splitter(1)._upstream_fiber()[0])

    def test_cycle_is_stopped(self):
        first, second = splitter(1), splitter(2)
        first.input_output_id = Record(sequence=1, splitter_id=second)
        second.input_output_id = Record(sequence=1, splitter_id=first)
        with self.assertRaisesRegex(ValueError, "circuito cerrado"):
            first._upstream_fiber()

    def test_html_identity_before_cable_on_both_sides(self):
        doc = etree.HTML(samples()["tray"])
        endpoints = doc.xpath("//span[@data-fiber-id]")
        self.assertEqual([item.get("data-fiber-id") for item in endpoints], ["11", "12"])
        self.assertIn("T2", "".join(endpoints[0][0].itertext()))
        self.assertIn("F6", "".join(endpoints[0][0].itertext()))
        self.assertEqual(endpoints[0][1].tag, "b")
        self.assertIn("F3", "".join(endpoints[1][0].itertext()))
        self.assertIn("Granada", endpoints[1].find("em").get("title"))

    def test_output_buttons_have_stable_identifiers(self):
        doc = etree.HTML(samples()["splitter"])
        self.assertEqual(doc.xpath("//button/@data-output-id"), ["61", "62", "63", "64"])
        self.assertEqual(doc.xpath("//div[@data-splitter-id]/@data-splitter-id"), ["50"])

    def test_view_has_three_operations_and_confirmation(self):
        doc = etree.parse(str(ROOT / "views/fiber_gis_splitter_views.xml"))
        self.assertFalse(doc.xpath("//header/button[@name='action_connect_customer_drop']"))
        self.assertTrue(doc.xpath("//button[@name='action_disconnect']/@confirm"))
        self.assertTrue(doc.xpath("//page[@name='observaciones']/field[@name='notes']"))
        self.assertEqual(doc.xpath("//button[@name='action_open_connected_splitter']/@invisible"), ["not has_child_splitter"])

    def test_python310_and_xml_syntax(self):
        for path in ROOT.rglob("*.py"):
            ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path), feature_version=(3, 10))
        for path in ROOT.rglob("*.xml"):
            etree.parse(str(path))

    def test_changed_views_reference_declared_fields_and_methods(self):
        schemas = {}
        methods = {}
        for path in (ROOT / "models").glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            for cls in (item for item in tree.body if isinstance(item, ast.ClassDef)):
                model = next((item.value.value for item in cls.body if isinstance(item, ast.Assign)
                              and any(isinstance(target, ast.Name) and target.id == "_name" for target in item.targets)
                              and isinstance(item.value, ast.Constant)), None)
                if not model:
                    continue
                schema = schemas.setdefault(model, {"id": None, "display_name": None})
                methods[model] = {item.name for item in cls.body if isinstance(item, ast.FunctionDef)}
                for item in cls.body:
                    if isinstance(item, ast.Assign) and isinstance(item.value, ast.Call):
                        call = item.value
                        if isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name) and call.func.value.id == "fields":
                            relation = call.args[0].value if call.args and isinstance(call.args[0], ast.Constant) else None
                            for target in item.targets:
                                if isinstance(target, ast.Name):
                                    schema[target.id] = relation

        def visit(element, model):
            if element.tag == "field":
                name = element.get("name")
                self.assertIn(name, schemas[model], f"{model}.{name} no esta declarado")
                relation = schemas[model][name]
                if relation in schemas:
                    model = relation
            if element.tag == "button" and element.get("type") == "object":
                self.assertIn(element.get("name"), methods[model])
            for child in element:
                visit(child, model)

        for filename in ("fiber_gis_splitter_views.xml", "fiber_gis_cable_tray_wizard_views.xml",
                         "fiber_gis_cable_views.xml", "fiber_gis_cable_profile_views.xml",
                         "fiber_gis_tray_views.xml", "fiber_gis_node_views.xml"):
            doc = etree.parse(str(ROOT / "views" / filename))
            for record in doc.xpath("//record[@model='ir.ui.view']"):
                model = record.find("field[@name='model']").text
                visit(record.find("field[@name='arch']")[0], model)


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(TrayInteractionChecks))
    if not result.wasSuccessful():
        sys.exit(1)
    if len(sys.argv) > 1:
        destination = Path(sys.argv[1])
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "tray_samples.json").write_text(json.dumps(samples(), ensure_ascii=False), encoding="utf-8")
