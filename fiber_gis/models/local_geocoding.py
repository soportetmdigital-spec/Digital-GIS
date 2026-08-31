"""Filtros y formato postal de las respuestas de OpenStreetMap, sin acceso a red."""

import unicodedata


LOCALITIES = {"granada": "Granada", "santa_fe": "Santa Fe"}


def normalize_place(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    return " ".join("".join(char for char in text if not unicodedata.combining(char)).casefold().split())


def municipality_key(item):
    """No confundir la provincia de Granada con Granada capital."""
    address = item.get("address") or {}
    if normalize_place(address.get("country_code")) != "es":
        return None
    locality = next((address[key] for key in ("city", "town", "village", "municipality") if address.get(key)), "")
    return {"granada": "granada", "santa fe": "santa_fe"}.get(normalize_place(locality))


def short_address(item):
    """Solo via, numero y municipio; nunca inferir un portal que no exista."""
    area_key = municipality_key(item)
    if not area_key:
        return ""
    address = item.get("address") or {}
    road = next((address[key] for key in ("road", "pedestrian", "residential", "path", "square") if address.get(key)), "")
    parts = [str(road).strip()]
    if road and address.get("house_number"):
        parts.append(str(address["house_number"]).strip())
    parts.append(LOCALITIES[area_key])
    return ", ".join(part for part in parts if part)
