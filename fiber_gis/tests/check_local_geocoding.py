"""Pruebas aisladas sin Odoo: python -B fiber_gis/tests/check_local_geocoding.py.

Se ejecutan los metodos reales de consulta con respuestas simuladas. No sustituye
a test_geocoding ni a test_node_models en una base de pruebas de Odoo.
"""

import ast
import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("local_geocoding", ROOT / "models/local_geocoding.py")
local = importlib.util.module_from_spec(spec)
spec.loader.exec_module(local)


class UserError(Exception):
    pass


# Extrae las consultas sin inicializar el ORM, manteniendo intacta su logica.
tree = ast.parse((ROOT / "models/site.py").read_text(encoding="utf-8"))
model = next(node for node in tree.body if isinstance(node, ast.ClassDef))
method_names = {"_nominatim_geocode", "search_map_streets", "reverse_geocode_coordinates", "_nominatim_reverse_geocode"}
methods = [node for node in model.body if isinstance(node, ast.FunctionDef) and node.name in method_names]
for method in methods:
    method.decorator_list = []
areas = next(node for node in tree.body if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "_MAP_STREET_AREAS" for target in node.targets))
namespace = {
    "UserError": UserError, "municipality_key": local.municipality_key,
    "normalize_place": local.normalize_place, "short_address": local.short_address,
}
exec(compile(ast.fix_missing_locations(ast.Module(body=[areas, *methods], type_ignores=[])), "site-isolated", "exec"), namespace)


class Service:
    def __init__(self, response):
        self.response = response
        self.cache = {}
        self.requests = []

    def _nominatim_request(self, endpoint, params):
        self.requests.append((endpoint, params))
        return self.response

    def _nominatim_cache_get(self, key):
        return self.cache.get(key)

    def _nominatim_cache_set(self, key, value):
        self.cache[key] = value


for name in method_names:
    setattr(Service, name, namespace[name])


def result(city="Granada", **values):
    item = {
        "lat": "37.178", "lon": "-3.601", "name": "Calle San Anton", "addresstype": "road",
        "address": {"road": "Calle San Anton", "house_number": "63B", "city": city, "country_code": "es"},
        "display_name": "63B, Calle San Anton, Centro, Granada, Andalucia, 18005, Espana",
    }
    item.update(values)
    return item


class LocalGeocodingChecks(unittest.TestCase):
    def test_short_address(self):
        self.assertEqual(local.short_address(result()), "Calle San Anton, 63B, Granada")

    def test_no_invented_house_number(self):
        item = result("Santa Fe")
        item["address"].pop("house_number")
        self.assertEqual(local.short_address(item), "Calle San Anton, Santa Fe")

    def test_city_instead_of_province(self):
        for name in ("Armilla", "Maracena", "Atarfe", "Peligros"):
            item = result(name)
            item["address"]["province"] = "Granada"
            self.assertIsNone(local.municipality_key(item))

    def test_wrong_country(self):
        item = result()
        item["address"]["country_code"] = "ni"
        self.assertEqual(local.short_address(item), "")

    def test_locality_must_be_known(self):
        self.assertIsNone(local.municipality_key({"address": {"county": "Granada", "country_code": "es"}}))

    def test_accents_retained(self):
        item = result()
        item["address"]["road"] = "Calle Pe\u00f1\u00f3n"
        self.assertEqual(local.short_address(item), "Calle Pe\u00f1\u00f3n, 63B, Granada")

    def test_first_result_from_neighbor_is_skipped(self):
        service = Service([result("Armilla"), result()])
        self.assertEqual(service._nominatim_geocode("San Anton"), {"lat": 37.178, "lng": -3.601})
        self.assertEqual(service.requests[0][1]["bounded"], 1)

    def test_no_allowed_results(self):
        service = Service([result("Maracena")])
        with self.assertRaises(UserError):
            service._nominatim_geocode("Maracena")

    def test_explicit_santa_fe(self):
        service = Service([result(), result("Santa Fe", lon="-3.717")])
        self.assertEqual(service._nominatim_geocode("Real, Santa Fe")["lng"], -3.717)

    def test_cache_does_not_reuse_old_global_results(self):
        service = Service([result()])
        service.cache["search|test"] = {"lat": 0, "lng": 0}
        first = service._nominatim_geocode("test")
        second = service._nominatim_geocode("test")
        self.assertEqual(first, second)
        self.assertEqual(len(service.requests), 1)
        self.assertNotEqual(first["lat"], 0)

    def test_streets_only_from_context_municipality(self):
        service = Service([result(), result("Santa Fe"), result("Armilla")])
        self.assertEqual(len(service.search_map_streets("test", "granada")), 1)
        results = service.search_map_streets("test", "santa_fe")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["municipality"], "Santa Fe")

    def test_reverse_is_short_and_cached(self):
        service = Service(result())
        service.cache["reverse|37.1780000|-3.6010000"] = {"address": "old verbose value"}
        first = service.reverse_geocode_coordinates(37.178, -3.601)
        second = service.reverse_geocode_coordinates(37.178, -3.601)
        self.assertEqual(first["address"], "Calle San Anton, 63B, Granada")
        self.assertEqual(first, second)
        self.assertEqual(len(service.requests), 1)

    def test_reverse_outside_allowed_towns(self):
        service = Service(result("Armilla"))
        self.assertEqual(service.reverse_geocode_coordinates(37.15, -3.62)["address"], "")

    def test_invalid_coordinates(self):
        service = Service(result())
        self.assertTrue(service.reverse_geocode_coordinates("bad", -3.6)["warning"])
        self.assertTrue(service.reverse_geocode_coordinates(123, -3.6)["warning"])
        self.assertFalse(service.requests)


if __name__ == "__main__":
    unittest.main(verbosity=2)
