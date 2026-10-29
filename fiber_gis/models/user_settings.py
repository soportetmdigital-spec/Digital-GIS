"""Preferencias del mapa de Fiber GIS guardadas en los ajustes de cada usuario."""

from odoo import api, fields, models

# Capas del mapa que el usuario puede ocultar y se recuerdan entre sesiones.
MAP_LAYER_KEYS = ("sites", "nodes", "cables", "customers", "dropCables")


class ResUsersSettings(models.Model):
    _inherit = "res.users.settings"

    fiber_gis_map_layers = fields.Json(string="Capas del mapa Fiber GIS")

    @api.model
    def _fiber_gis_clean_map_layers(self, values):
        """Normaliza las capas recibidas del mapa y descarta claves desconocidas."""
        values = values if isinstance(values, dict) else {}
        layers = {key: bool(values[key]) for key in MAP_LAYER_KEYS if key in values}
        hidden_kinds = values.get("hiddenNodeKinds")
        if isinstance(hidden_kinds, list):
            layers["hiddenNodeKinds"] = sorted({str(kind) for kind in hidden_kinds if kind})
        return layers

    @api.model
    def get_fiber_gis_map_layers(self):
        """Devuelve las capas del mapa guardadas para el usuario actual."""
        settings = self._find_or_create_for_user(self.env.user)
        return self._fiber_gis_clean_map_layers(settings.fiber_gis_map_layers)

    @api.model
    def set_fiber_gis_map_layers(self, values):
        """Guarda las capas del mapa del usuario actual; nunca las de otro usuario."""
        settings = self._find_or_create_for_user(self.env.user)
        layers = self._fiber_gis_clean_map_layers(values)
        settings.sudo().write({"fiber_gis_map_layers": layers})
        return layers
