"""Botón «Obtener dirección»: dirección a partir de las coordenadas guardadas."""
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase


class TestReverseGeocode(TransactionCase):
    def setUp(self):
        super().setUp()
        site_model = type(self.env["fiber.gis.site"])
        # Sin red ni espera entre peticiones: se simula la respuesta de OpenStreetMap.
        self.enterContext(patch.object(site_model, "_nominatim_wait_for_request_slot", return_value=None))
        self.enterContext(patch.object(
            site_model, "_nominatim_reverse_geocode", return_value="Calle Recogidas 12, Granada",
        ))

    def test_node_address_from_saved_coordinates(self):
        node = self.env["fiber.gis.node"].create({
            "name": "CTO dirección", "code": "TEST-REV-ADDR", "latitude": 37.1700, "longitude": -3.6010,
        })
        action = node.action_reverse_geocode()
        self.assertEqual(node.address, "Calle Recogidas 12, Granada")
        self.assertEqual(action["params"]["message"], "Calle Recogidas 12, Granada")
        self.assertEqual(action["params"]["next"]["tag"], "soft_reload")

    def test_site_address_from_saved_coordinates(self):
        site = self.env["fiber.gis.site"].create({"name": "Sitio dirección", "latitude": 37.1700, "longitude": -3.6010})
        site.action_reverse_geocode()
        self.assertEqual(site.street, "Calle Recogidas 12, Granada")

    def test_requires_coordinates(self):
        node = self.env["fiber.gis.node"].create({"name": "Sin coordenadas", "code": "TEST-REV-NOCOORD"})
        with self.assertRaises(UserError):
            node.action_reverse_geocode()
