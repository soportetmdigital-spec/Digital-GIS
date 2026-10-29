"""Pruebas aisladas de la presentación de las líneas de bandeja y del tubo de las fibras."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCSS = (ROOT / "static/src/scss/fiber_map.scss").read_text(encoding="utf-8")
NODE = (ROOT / "models/node.py").read_text(encoding="utf-8")


class TrayLayoutChecks(unittest.TestCase):
    def test_tray_line_grid_has_one_column_per_slot(self):
        block = SCSS[SCSS.index(".o_fiber_tray_line {"):]
        block = block[:block.index("}")]
        columns = re.search(r"grid-template-columns:\s*([^;]+);", block).group(1)
        # Tipo, entrada, flecha, salida, relación y papelera.
        self.assertEqual(len(re.findall(r"minmax\([^)]*\)|\d+px|auto", columns)), 6)

    def test_every_tray_line_emits_all_slots(self):
        body = NODE[NODE.index("    def _tray_line_visual_html(self, line):"):NODE.index("    def _fiber_endpoint_html(")]
        self.assertNotIn('arrow_html = ""', body)
        self.assertNotIn('output_html = ""', body)
        self.assertNotIn('if line.splitter_ratio else ""', body)

    def test_tube_is_shown_only_with_several_tubes(self):
        fiber = (ROOT / "models/fiber.py").read_text(encoding="utf-8")
        self.assertIn("fiber.cable_id.tube_count > 1", fiber)
        self.assertIn("if tube and fiber.show_tube:", NODE)
        self.assertIn("if fiber.show_tube:", (ROOT / "models/splitter.py").read_text(encoding="utf-8"))
        self.assertIn('t-if="item.show_tube"', (ROOT / "static/src/xml/fiber_color_checkboxes.xml").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
