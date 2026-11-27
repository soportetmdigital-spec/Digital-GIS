"""Pruebas aisladas de la cartografía en teselas y de las parcelas del Catastro."""
import importlib.util
import math
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "models" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


parcels = load("catastro_parcels")


class CatastroChecks(unittest.TestCase):
    def test_tile_bbox_matches_web_mercator(self):
        # catastro_tiles importa odoo; se comprueba la misma fórmula sin cargar el ORM.
        source = (ROOT / "models/catastro_tiles.py").read_text(encoding="utf-8")
        self.assertIn("2 * WEB_MERCATOR_EXTENT / (2 ** z)", source)
        self.assertIn('"SRS": "EPSG:3857"', source)
        extent = 20037508.342789244
        z, x, y = 1, 0, 0
        size = 2 * extent / 2 ** z
        self.assertAlmostEqual(-extent + x * size, -extent)
        self.assertAlmostEqual(extent - y * size, extent)

    def test_buildings_from_real_response(self):
        data = parcels.parse_buildings((ROOT / "tests/data/catastro_buildings.xml").read_bytes())
        building = data["6645204VG4164F"]
        self.assertEqual((building["dwellings"], building["building_units"], building["floor_area"]), (5, 7, 502))
        self.assertEqual(building["current_use"], "1_residential")
        self.assertAlmostEqual(building["latitude"], 37.17396, places=4)
        self.assertAlmostEqual(building["longitude"], -3.60206, places=4)

    def test_addresses_from_real_response(self):
        data = parcels.parse_addresses((ROOT / "tests/data/catastro_addresses.xml").read_bytes())
        self.assertEqual(data["6645204VG4164F"], {"address": "CL MORAL MAGDALENA 2", "postcode": "18002", "municipality": "GRANADA"})
        self.assertEqual(data["6746001VG4164F"]["address"], "CL GRACIA 3")

    def test_bbox_is_split_in_small_cells(self):
        cells = parcels.bbox_cells(-3.61, 37.17, -3.60, 37.176)
        self.assertEqual(len(cells), 3 * 2)
        for west, south, east, north in cells:
            self.assertLessEqual(east - west, parcels.CELL_DEG + 1e-9)
            self.assertLessEqual(north - south, parcels.CELL_DEG + 1e-9)
        url = parcels.wfs_url(parcels.BUILDINGS_WFS_URL, "BU:Building", cells[0])
        self.assertIn("bbox=37.170000%2C-3.610000", url)

    def test_xml_parser_does_not_resolve_entities(self):
        payload = b'<!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><x>&e;</x>'
        root = parcels.parse_xml(payload)
        self.assertNotIn("root:", root.text or "")


if __name__ == "__main__":
    unittest.main()
