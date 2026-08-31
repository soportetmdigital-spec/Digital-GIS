from unittest.mock import patch

from odoo.tests import TransactionCase
from odoo.exceptions import UserError

from ..models.local_geocoding import municipality_key, short_address


class TestOpenStreetMapGeocoding(TransactionCase):
    def setUp(self):
        super().setUp()
        self.parameters = self.env["ir.config_parameter"].sudo()
        self.parameters.set_param(
            "fiber_gis.nominatim_url", "https://nominatim.openstreetmap.org"
        )
        self.parameters.set_param("fiber_gis.google_maps_api_key", "unused-google-key")

    def test_site_coordinates_use_openstreetmap_and_cache_result(self):
        site = self.env["fiber.gis.site"].create({
            "name": "Sitio prueba OpenStreetMap",
            "street": "Calle Gran Via de Colon, 5",
            "city": "Granada",
        })
        response = [{"lat": "37.178056", "lon": "-3.600833", "address": {"city": "Granada", "country_code": "es"}}]

        with patch.object(
            type(site), "_nominatim_request", autospec=True, return_value=response
        ) as request_mock:
            site.action_geocode_openstreetmap()
            site.action_geocode_openstreetmap()

        self.assertEqual(request_mock.call_count, 1)
        self.assertAlmostEqual(site.latitude, 37.178056, places=6)
        self.assertAlmostEqual(site.longitude, -3.600833, places=6)

    def test_reverse_geocoding_uses_openstreetmap_and_cache_result(self):
        site_model = self.env["fiber.gis.site"]
        response = {
            "display_name": "5, Gran Via de Colon, Centro, Granada, 18001, Espana",
            "address": {"road": "Gran Via de Colon", "house_number": "5", "city": "Granada", "country_code": "es"},
        }

        with patch.object(
            type(site_model), "_nominatim_request", autospec=True, return_value=response
        ) as request_mock:
            first = site_model.reverse_geocode_coordinates(37.178056, -3.600833)
            second = site_model.reverse_geocode_coordinates(37.178056, -3.600833)

        self.assertEqual(request_mock.call_count, 1)
        self.assertEqual(first["provider"], "OpenStreetMap")
        self.assertEqual(first["address"], "Gran Via de Colon, 5, Granada")
        self.assertEqual(second["address"], first["address"])

    def test_province_does_not_count_as_granada_city(self):
        self.assertIsNone(municipality_key({"address": {"town": "Armilla", "province": "Granada", "country_code": "es"}}))
        self.assertIsNone(municipality_key({"address": {"county": "Granada", "country_code": "es"}}))
        self.assertIsNone(municipality_key({"address": {"city": "Granada", "country_code": "ni"}}))

    def test_santa_fe_address_without_house_number(self):
        item = {"address": {"road": "Calle Real", "town": "Santa Fe", "country_code": "es", "postcode": "18320"}}
        self.assertEqual(short_address(item), "Calle Real, Santa Fe")

    def test_search_skips_neighboring_towns(self):
        site = self.env["fiber.gis.site"]
        response = [
            {"lat": "37.15", "lon": "-3.62", "address": {"town": "Armilla", "country_code": "es"}},
            {"lat": "37.178", "lon": "-3.601", "address": {"city": "Granada", "country_code": "es"}},
        ]
        with patch.object(type(site), "_nominatim_request", return_value=response) as request:
            result = site._nominatim_geocode("Prueba municipios")
        self.assertEqual(result, {"lat": 37.178, "lng": -3.601})
        self.assertEqual(request.call_args.args[1]["bounded"], 1)

    def test_unknown_locality_fails_without_guessing(self):
        site = self.env["fiber.gis.site"]
        with patch.object(type(site), "_nominatim_request", return_value=[{"lat": "37.17", "lon": "-3.60"}]):
            with self.assertRaises(UserError):
                site._nominatim_geocode("Consulta sin municipio")

    def test_street_results_match_selected_municipality(self):
        site = self.env["fiber.gis.site"]
        response = [
            {"name": "Calle Real", "addresstype": "road", "lat": "37.178", "lon": "-3.601", "address": {"road": "Calle Real", "city": "Granada", "country_code": "es"}},
            {"name": "Calle Real", "addresstype": "road", "lat": "37.189", "lon": "-3.717", "address": {"road": "Calle Real", "town": "Santa Fe", "country_code": "es"}},
        ]
        with patch.object(type(site), "_nominatim_request", return_value=response):
            results = site.search_map_streets("Calle Real test", "santa_fe")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["municipality"], "Santa Fe")
        self.assertAlmostEqual(results[0]["longitude"], -3.717)
