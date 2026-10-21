"""Pruebas unitarias de la geometria comun de los planos GIS."""

import base64
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "models"))

from map_geometry import (  # noqa: E402
    catastro_wms_png_data_uri,
    fit_bbox_to_aspect,
    latlon_to_web_mercator,
    project_map_point,
)
from map_actions import google_maps_action  # noqa: E402


PNG_SAMPLE = b"\x89PNG\r\n\x1a\nprueba"


class FakeResponse:
    """Respuesta HTTP minima para simular la descarga del WMS."""

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return PNG_SAMPLE


class MapGeometryChecks(unittest.TestCase):
    def test_coordinates_project_to_canvas_center(self):
        min_x, min_y, max_x, max_y = fit_bbox_to_aspect(-100, -50, 100, 50, 2)
        center = project_map_point(0, 0, min_x, min_y, max_x, max_y, 800, 400)
        self.assertEqual(center, (400.0, 200.0))

    def test_web_mercator_clamps_polar_latitude(self):
        x, y = latlon_to_web_mercator(90, 0)
        self.assertEqual(x, 0)
        self.assertLessEqual(y, 20037508.342789244)

    def test_catastro_returns_png_data_uri_and_uses_timeout(self):
        with patch("map_geometry.urllib.request.urlopen", return_value=FakeResponse()) as open_url:
            result = catastro_wms_png_data_uri(1, 2, 3, 4, 640, 480, "prueba", 17)
        self.assertEqual(result, "data:image/png;base64," + base64.b64encode(PNG_SAMPLE).decode("ascii"))
        self.assertEqual(open_url.call_args.kwargs["timeout"], 17)

    def test_catastro_failure_or_non_png_returns_false(self):
        with patch("map_geometry.urllib.request.urlopen", side_effect=TimeoutError):
            self.assertFalse(catastro_wms_png_data_uri(1, 2, 3, 4, 640, 480, "prueba", 1))
        response = FakeResponse()
        response.read = lambda: b"respuesta XML de error"
        with patch("map_geometry.urllib.request.urlopen", return_value=response):
            self.assertFalse(catastro_wms_png_data_uri(1, 2, 3, 4, 640, 480, "prueba", 1))

    def test_google_maps_uses_coordinates_and_lazily_falls_back_to_address(self):
        fallback = Mock(return_value="Calle Real 1, Granada")
        action = google_maps_action(37.1, -3.6, fallback)
        self.assertIn("37.1%2C-3.6", action["url"])
        fallback.assert_not_called()
        action = google_maps_action(False, False, fallback)
        self.assertIn("Calle+Real+1%2C+Granada", action["url"])
        fallback.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
