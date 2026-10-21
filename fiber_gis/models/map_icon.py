"""Utilidades para previsualizar iconos tecnicos del mapa."""

from html import escape


MAP_ICON_PATHS = {
    "diamond": "M 0 -10 L 10 0 L 0 10 L -10 0 Z",
    "triangle": "M 0 -11 L 11 10 L -11 10 Z",
    "star": "M 0 -12 L 3 -4 L 11 -4 L 5 1 L 7 10 L 0 5 L -7 10 L -5 1 L -11 -4 L -3 -4 Z",
    "network": "M -11 -11 H 11 V 11 H -11 Z M -7 -7 V 7 H 7 V -7 Z M -2 -2 H 2 V 2 H -2 Z",
    "olt": "M -11 -10 H 11 V 10 H -11 Z M -7 -6 H 7 V -3 H -7 Z M -7 -1 H 7 V 2 H -7 Z M -7 4 H 7 V 7 H -7 Z",
    "odf": "M -10 -10 H 10 V 10 H -10 Z M -6 -6 H -2 V -2 H -6 Z M 2 -6 H 6 V -2 H 2 Z M -6 2 H -2 V 6 H -6 Z M 2 2 H 6 V 6 H 2 Z",
    "cto": "M 0 -12 L 11 -5 V 7 L 0 12 L -11 7 V -5 Z M -5 -4 H 5 V 4 H -5 Z",
    "cabinet": "M -9 -12 H 9 V 12 H -9 Z M -5 -8 H 5 V -5 H -5 Z M -5 -2 H 5 V 1 H -5 Z M -5 4 H 5 V 8 H -5 Z",
    "closure": "M -12 -7 H 12 V 7 H -12 Z M -7 -3 H 7 V 3 H -7 Z M -14 -2 H -12 V 2 H -14 Z M 12 -2 H 14 V 2 H 12 Z",
    "manhole": "M 0 -11 C 7 -11 12 -6 12 0 C 12 6 7 11 0 11 C -7 11 -12 6 -12 0 C -12 -6 -7 -11 0 -11 Z M 0 -6 C -4 -6 -7 -3 -7 0 C -7 3 -4 6 0 6 C 4 6 7 3 7 0 C 7 -3 4 -6 0 -6 Z",
    "pole": "M -2 -12 H 2 V 12 H -2 Z M -9 -8 H 9 V -5 H -9 Z M -7 3 H 7 V 6 H -7 Z",
    "splitter": "M -11 -3 H -2 V -8 H 2 V -3 H 11 V 3 H 2 V 8 H -2 V 3 H -11 Z",
    "rack": "M -11 -12 H 11 V 12 H -11 Z M -7 -8 H 7 V -5 H -7 Z M -7 -2 H 7 V 1 H -7 Z M -7 4 H 7 V 7 H -7 Z M -8 10 H -5 V 12 H -8 Z M 5 10 H 8 V 12 H 5 Z",
    "ont": "M -10 -7 H 10 V 7 H -10 Z M -6 -3 H 2 V 1 H -6 Z M 5 -2 H 8 V 2 H 5 Z M -4 7 H 4 V 11 H -4 Z",
    "customer_terminal": "M -13 -8 H 13 V 8 H -13 Z M -9 -4 H 5 V 0 H -9 Z M 8 -3 H 11 V 3 H 8 Z",
    "tray": "M -12 -8 H 12 V 8 H -12 Z M -8 -4 H 8 V -1 H -8 Z M -8 2 H 8 V 5 H -8 Z",
}


def map_icon_preview_html(icon, color, label):
    """Genera la vista previa HTML del icono que se muestra en el mapa."""
    icon = icon or "circle"
    color = escape(color or "#334155")
    label = escape(label or "Icono")
    if icon == "square":
        shape = f"<rect x='10' y='10' width='28' height='28' rx='5' fill='{color}'/>"
    elif icon == "circle":
        shape = f"<circle cx='24' cy='24' r='15' fill='{color}'/>"
    else:
        path = escape(MAP_ICON_PATHS.get(icon, MAP_ICON_PATHS["network"]))
        shape = f"<path d='{path}' fill='{color}' fill-rule='evenodd' transform='translate(24 24)'/>"
    return (
        "<div class='o_fiber_gis_icon_preview'>"
        "<svg viewBox='0 0 48 48' aria-hidden='true'>"
        f"{shape}"
        "</svg>"
        f"<span>{label}</span>"
        "</div>"
    )
