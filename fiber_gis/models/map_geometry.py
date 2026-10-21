"""Operaciones comunes para representar coordenadas en planos estáticos."""

import base64
import math
import urllib.error
import urllib.parse
import urllib.request


CATASTRO_WMS_URL = "https://ovc.catastro.meh.es/Cartografia/WMS/ServidorWMS.aspx"
WEB_MERCATOR_LIMIT = 20037508.342789244


def latlon_to_web_mercator(latitude, longitude):
    """Convierte latitud/longitud a metros Web Mercator y limita latitudes extremas."""
    clipped_latitude = max(min(latitude, 85.05112878), -85.05112878)
    x = longitude * WEB_MERCATOR_LIMIT / 180.0
    y = math.log(math.tan((90.0 + clipped_latitude) * math.pi / 360.0))
    y *= WEB_MERCATOR_LIMIT / math.pi
    y = max(min(y, WEB_MERCATOR_LIMIT), -WEB_MERCATOR_LIMIT)
    return x, y


def fit_bbox_to_aspect(min_x, min_y, max_x, max_y, target_aspect):
    """Ajusta los límites del plano a su proporción sin recortar los puntos."""
    bbox_width = max(max_x - min_x, 1)
    bbox_height = max(max_y - min_y, 1)
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2
    if bbox_width / bbox_height < target_aspect:
        bbox_width = bbox_height * target_aspect
    else:
        bbox_height = bbox_width / target_aspect
    return (
        center_x - bbox_width / 2,
        center_y - bbox_height / 2,
        center_x + bbox_width / 2,
        center_y + bbox_height / 2,
    )


def project_map_point(latitude, longitude, min_x, min_y, max_x, max_y, width, height):
    """Transforma una coordenada geográfica en un punto del lienzo SVG."""
    mercator_x, mercator_y = latlon_to_web_mercator(latitude, longitude)
    x = ((mercator_x - min_x) / max(max_x - min_x, 0.000001)) * width
    y = ((max_y - mercator_y) / max(max_y - min_y, 0.000001)) * height
    return round(x, 1), round(y, 1)


def catastro_wms_png_data_uri(min_x, min_y, max_x, max_y, width, height, user_agent, timeout):
    """Descarga la imagen WMS del Catastro y devuelve un URI PNG seguro o False."""
    params = urllib.parse.urlencode({
        "SERVICE": "WMS",
        "VERSION": "1.1.1",
        "REQUEST": "GetMap",
        "FORMAT": "image/png",
        "TRANSPARENT": "FALSE",
        "SRS": "EPSG:3857",
        "LAYERS": "Catastro",
        "STYLES": "",
        "BBOX": f"{min_x},{min_y},{max_x},{max_y}",
        "WIDTH": str(width),
        "HEIGHT": str(height),
    })
    request = urllib.request.Request(
        f"{CATASTRO_WMS_URL}?{params}",
        headers={"User-Agent": user_agent},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read()
    except (urllib.error.URLError, TimeoutError, OSError):
        return False
    if not payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return False
    encoded = base64.b64encode(payload).decode("ascii")
    return f"data:image/png;base64,{encoded}"
