"""Rutas HTTP de Fiber GIS: imágenes de iconos del mapa."""

from odoo import http
from odoo.http import request


class FiberGisController(http.Controller):
    @http.route("/fiber_gis/map_icon/<string:code>", type="http", auth="user", methods=["GET"], readonly=True)
    def map_icon(self, code, **kwargs):
        """Imagen de un icono personalizado del mapa, con su transparencia original."""
        icon = request.env["fiber.gis.map.icon"].with_context(active_test=False).search([("code", "=", code)], limit=1)
        if not icon or not icon.image:
            raise request.not_found()
        stream = request.env["ir.binary"]._get_image_stream_from(icon, "image")
        # La URL lleva la versión de la imagen (?v=...), así que el navegador puede guardarla un día.
        return stream.get_response(max_age=86400 if kwargs.get("v") else 0)

    @http.route("/fiber_gis/catastro/<int:z>/<int:x>/<int:y>.png", type="http", auth="user", methods=["GET"], readonly=True)
    def catastro_tile(self, z, x, y, **kwargs):
        """Tesela de cartografía del Catastro desde la caché del servidor (memoria, disco o Catastro)."""
        payload = request.env["fiber.gis.catastro.tiles"].get_tile_png(z, x, y)
        if not payload:
            raise request.not_found()
        return request.make_response(payload, headers=[
            ("Content-Type", "image/png"),
            # El navegador también guarda la tesela un día y no vuelve a pedirla al moverse por el mapa.
            ("Cache-Control", "private, max-age=86400"),
        ])
