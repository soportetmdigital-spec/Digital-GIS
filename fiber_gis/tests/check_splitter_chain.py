"""Comprueba el recorrido de cascadas de splitters sin requerir Odoo."""

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]


def splitter_upstream_chain(splitter):
    """Carga la función pura de recorrido desde el módulo de producción."""
    tree = ast.parse((ROOT / "models" / "splitter.py").read_text(encoding="utf-8-sig"))
    function = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "splitter_upstream_chain"
    )
    namespace = {}
    exec(compile(ast.Module(body=[function], type_ignores=[]), "splitter.py", "exec"), namespace)
    return namespace[function.name](splitter)


def splitter_options():
    """Carga las opciones y cálculos puros de relación del módulo."""
    path = ROOT / "models" / "splitter_options.py"
    namespace = {}
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), namespace)
    return namespace


def splitter(identifier, source=False, fiber=False):
    """Crea un splitter sencillo con una salida de entrada simulada."""
    record = SimpleNamespace(id=identifier, input_fiber_id=fiber, input_output_id=False)
    if source:
        record.input_output_id = SimpleNamespace(splitter_id=source, sequence=1)
    return record


class SplitterChainChecks(unittest.TestCase):
    def test_cassette_ratios_have_expected_outputs_and_default_losses(self):
        options = splitter_options()
        choices = dict(options["SPLITTER_RATIO_SELECTION"])
        self.assertEqual(choices["1:4 Casete"], "1:4 Casete")
        self.assertEqual(choices["1:8 Casete"], "1:8 Casete")
        self.assertEqual(options["splitter_output_count"]("1:4 Casete"), 4)
        self.assertEqual(options["splitter_output_count"]("1:8 Casete"), 8)
        self.assertEqual(options["splitter_default_loss_db"]("1:4 Casete"), 7.1)
        self.assertEqual(options["splitter_default_loss_db"]("1:8 Casete"), 10.4)

    def test_chain_stops_at_root_fed_by_cable_fiber(self):
        root = splitter(1, fiber="fibra-1")
        middle = splitter(2, source=root)
        downstream = splitter(3, source=middle)
        chain, has_cycle = splitter_upstream_chain(downstream)
        self.assertEqual([item.id for item in chain], [3, 2, 1])
        self.assertFalse(has_cycle)

    def test_cycle_is_reported_without_repeating_the_record(self):
        first = splitter(1)
        second = splitter(2, source=first)
        first.input_output_id = SimpleNamespace(splitter_id=second, sequence=1)
        chain, has_cycle = splitter_upstream_chain(first)
        self.assertEqual([item.id for item in chain], [1, 2])
        self.assertTrue(has_cycle)

    def test_unconnected_splitter_is_a_finite_chain(self):
        chain, has_cycle = splitter_upstream_chain(splitter(1))
        self.assertEqual([item.id for item in chain], [1])
        self.assertFalse(has_cycle)


if __name__ == "__main__":
    unittest.main()
