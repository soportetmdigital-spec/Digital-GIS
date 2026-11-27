"""Iconos del mapa subidos por los responsables."""
import base64
import io

from PIL import Image

from odoo.exceptions import ValidationError
from odoo.tests import HttpCase, TransactionCase, tagged


def transparent_png():
    """PNG de 64x64 con fondo transparente y un círculo opaco."""
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    for x in range(64):
        for y in range(64):
            if (x - 32) ** 2 + (y - 32) ** 2 < 20 ** 2:
                image.putpixel((x, y), (220, 38, 38, 255))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue())


class TestMapIcons(TransactionCase):
    def test_uploaded_icon_is_selectable_and_keeps_transparency(self):
        icon = self.env["fiber.gis.map.icon"].create({"name": "CTO Exterior Ñ", "image": transparent_png()})
        self.assertEqual(icon.code, "cto_exterior_n")
        value = "custom_cto_exterior_n"
        self.assertIn(value, dict(self.env["fiber.gis.node"]._selection_map_icon()))
        self.assertIn(value, dict(self.env["fiber.gis.site"]._selection_map_icon()))
        self.assertIn(value, dict(self.env["fiber.gis.node.category"]._selection_map_icon()))

        node = self.env["fiber.gis.node"].create({"name": "Con icono", "code": "TEST-ICON", "map_icon": value})
        self.assertEqual(node.map_icon, value)
        self.assertIn("/fiber_gis/map_icon/cto_exterior_n", node.map_icon_preview_html)

        stored = Image.open(io.BytesIO(base64.b64decode(icon.image)))
        self.assertEqual(stored.mode, "RGBA")
        self.assertEqual(stored.getpixel((0, 0))[3], 0, "El fondo sigue siendo transparente.")
        self.assertEqual(self.env["fiber.gis.map.icon"].get_map_icons()[0]["value"], value)

        with self.assertRaises(ValidationError):
            icon.unlink()
        second = self.env["fiber.gis.map.icon"].create({"name": "CTO Exterior Ñ", "image": transparent_png()})
        self.assertEqual(second.code, "cto_exterior_n_2")

    def test_svg_icons_are_accepted(self):
        svg = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><circle cx="5" cy="5" r="4" fill="red"/></svg>'
        icon = self.env["fiber.gis.map.icon"].create({"name": "Vector", "image": base64.b64encode(svg)})
        self.assertEqual(base64.b64decode(icon.image), svg)


@tagged("post_install", "-at_install")
class TestMapIconRoute(HttpCase):
    def test_route_serves_icon_image(self):
        self.env["fiber.gis.map.icon"].create({"name": "Ruta", "image": transparent_png()})
        self.authenticate("admin", "admin")
        response = self.url_open("/fiber_gis/map_icon/ruta?v=1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Content-Type"], "image/png")
        self.assertTrue(response.content.startswith(b"\x89PNG"))
        self.assertEqual(self.url_open("/fiber_gis/map_icon/no_existe").status_code, 404)
