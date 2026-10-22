"""Pruebas aisladas del render del mapa: elementos SVG por cable e interacción de arrastre."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "static/src/js/fiber_map.js").read_text(encoding="utf-8")
XML = (ROOT / "static/src/xml/fiber_map.xml").read_text(encoding="utf-8")
SCSS = (ROOT / "static/src/scss/fiber_map.scss").read_text(encoding="utf-8")


def method_body(name):
    match = re.search(rf"\n    {name}\([^)]*\) {{\r?\n(.*?)\r?\n    }}\r?\n", JS, re.S)
    assert match, name
    return match.group(1)


class MapRenderChecks(unittest.TestCase):
    def test_one_hit_path_per_cable(self):
        cables = XML[XML.index('<g class="o_fiber_gis_cables">'):XML.index('<g t-if="state.cableDraftMode"')]
        self.assertEqual(cables.count("o_fiber_gis_cable_hit"), 1)
        hit = cables[cables.rindex("<path", 0, cables.index("o_fiber_gis_cable_hit")):]
        hit = hit[:hit.index("/>")]
        self.assertNotIn("segment", hit)
        self.assertIn("cableRender.path", hit)

    def test_segment_paths_are_single_lines(self):
        # Una línea por tramo: el navegador solo genera los guiones visibles de una recta.
        self.assertIn("this.pointsPath(points, index, index + 1)", method_body("cableRenderData"))

    def test_hidden_hit_area_is_not_painted_but_clickable(self):
        block = SCSS[SCSS.index(".o_fiber_gis_cable_hit {"):]
        block = block[:block.index("}")]
        self.assertIn("visibility: hidden", block)
        self.assertIn("pointer-events: stroke", block)

    def test_pressing_a_cable_pans_and_click_still_selects(self):
        pointer_down = method_body("onMapPointerDown")
        self.assertIn('owner?.kind === "cable" && this.state.cableDraftMode', pointer_down)
        self.assertNotIn("setPointerCapture", method_body("onBackgroundPointerDown"))
        self.assertIn("setPointerCapture(this._panPointerStart.pointerId)", method_body("onPointerMove"))

    def test_projected_cable_vertices_are_cached(self):
        self.assertIn("cached.projected", method_body("cablePoints"))


if __name__ == "__main__":
    unittest.main()
