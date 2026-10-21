"""Acciones comunes para abrir ubicaciones desde las fichas GIS."""

from urllib.parse import quote_plus


def google_maps_action(latitude, longitude, fallback_query):
    """Prepara la acción para abrir una ubicación en Google Maps."""
    if latitude and longitude:
        query = f"{latitude},{longitude}"
    else:
        query = fallback_query()
    return {
        "type": "ir.actions.act_url",
        "name": "Abrir en Google Maps",
        "target": "new",
        "url": f"https://www.google.com/maps/search/?api=1&query={quote_plus(query)}",
    }
