"""Pruebas aisladas de la geometría de recorridos: elementos atravesados y división en tramos."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("route_geometry", ROOT / "models/route_geometry.py")
geometry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(geometry)

A, B, C = (37.1800, -3.6000), (37.1800, -3.5980), (37.1810, -3.5980)


class RouteGeometryChecks(unittest.TestCase):
    def test_candidates_are_ordered_along_the_route(self):
        nodes = [("far", 37.1830, -3.5990), ("second", 37.1805, -3.5980), ("first", 37.18001, -3.5990)]
        found = geometry.route_candidates([A, B, C], nodes, 3.0)
        self.assertEqual([item["key"] for item in found], ["first", "second"])
        self.assertEqual(found[0]["segment"], 0)
        self.assertEqual(found[1]["segment"], 1)
        self.assertLess(found[0]["distance"], 3.0)

    def test_split_route_at_pass_nodes(self):
        middle = (37.1800, -3.5990)
        passes = geometry.route_candidates([A, B, C], [("m", *middle), ("b", *B)], 1.0)
        pieces = geometry.split_route([A, B, C], ["aerial", "facade"], passes)
        self.assertEqual([piece[0] for piece in pieces], [[A, middle], [middle, B], [B, C]])
        self.assertEqual([piece[1] for piece in pieces], [["aerial"], ["aerial"], ["facade"]])

    def test_geometry_json_is_lon_lat(self):
        data = json.loads(geometry.geometry_json([A, B]))
        self.assertEqual(data["type"], "LineString")
        self.assertEqual(data["coordinates"][0], [A[1], A[0]])


if __name__ == "__main__":
    unittest.main()
