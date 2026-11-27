"""Cartografía del Catastro servida por Odoo en teselas, con caché en memoria y en disco.

El mapa pide teselas fijas de 512 px en la proyección Web Mercator (EPSG:3857). Cada tesela se descarga
una sola vez del servicio WMS del Catastro y se guarda junto al filestore de la base de datos; las
siguientes peticiones, de cualquier usuario, se sirven desde la memoria del proceso o desde el disco.
"""

import json
import logging
import math
import os
import shutil
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict

from odoo import api, fields, models
from odoo.tools import config

_logger = logging.getLogger(__name__)

CATASTRO_WMS_URL = "https://ovc.catastro.meh.es/Cartografia/WMS/ServidorWMS.aspx"
USER_AGENT = "FiberGIS/19.0 (Odoo 19)"
TILE_SIZE = 512
MIN_ZOOM = 10
MAX_ZOOM = 21
WEB_MERCATOR_EXTENT = 20037508.342789244
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MEMORY_TILES = 400
DEFAULT_MAX_AGE_DAYS = 30
# Pocas descargas simultáneas por proceso para no saturar el servicio del Catastro.
_download_slots = threading.BoundedSemaphore(3)
_memory_lock = threading.Lock()
_memory_cache = OrderedDict()


def tile_bbox(z, x, y):
    """Rectángulo EPSG:3857 (min_x, min_y, max_x, max_y) de la tesela z/x/y (origen arriba a la izquierda)."""
    size = 2 * WEB_MERCATOR_EXTENT / (2 ** z)
    min_x = -WEB_MERCATOR_EXTENT + x * size
    max_y = WEB_MERCATOR_EXTENT - y * size
    return (min_x, max_y - size, min_x + size, max_y)


def tile_range(z, west, south, east, north):
    """Teselas (x0, y0, x1, y1) de nivel z que cubren un rectángulo en grados."""
    def to_tile(longitude, latitude):
        latitude = max(min(latitude, 85.05112878), -85.05112878)
        n = 2 ** z
        x = (longitude + 180.0) / 360.0 * n
        y = (1.0 - math.asinh(math.tan(math.radians(latitude))) / math.pi) / 2.0 * n
        return min(max(int(x), 0), n - 1), min(max(int(y), 0), n - 1)

    x0, y0 = to_tile(west, north)
    x1, y1 = to_tile(east, south)
    return x0, y0, x1, y1


def valid_tile(z, x, y):
    return MIN_ZOOM <= z <= MAX_ZOOM and 0 <= x < 2 ** z and 0 <= y < 2 ** z


def wms_url(z, x, y):
    min_x, min_y, max_x, max_y = tile_bbox(z, x, y)
    return CATASTRO_WMS_URL + "?" + urllib.parse.urlencode({
        "SERVICE": "WMS", "VERSION": "1.1.1", "REQUEST": "GetMap", "FORMAT": "image/png",
        "TRANSPARENT": "FALSE", "SRS": "EPSG:3857", "LAYERS": "Catastro", "STYLES": "",
        "BBOX": f"{min_x:.3f},{min_y:.3f},{max_x:.3f},{max_y:.3f}",
        "WIDTH": str(TILE_SIZE), "HEIGHT": str(TILE_SIZE),
    })


def cache_root(dbname):
    """Carpeta de la caché de teselas de una base de datos, junto a su filestore."""
    return os.path.join(config.filestore(dbname), "fiber_gis_catastro")


def tile_path(dbname, z, x, y):
    return os.path.join(cache_root(dbname), str(z), str(x), f"{y}.png")


def _memory_get(key):
    with _memory_lock:
        payload = _memory_cache.get(key)
        if payload is not None:
            _memory_cache.move_to_end(key)
        return payload


def _memory_put(key, payload):
    with _memory_lock:
        _memory_cache[key] = payload
        _memory_cache.move_to_end(key)
        while len(_memory_cache) > MEMORY_TILES:
            _memory_cache.popitem(last=False)


def clear_memory_cache():
    with _memory_lock:
        _memory_cache.clear()


def download_tile(z, x, y, timeout=20, attempts=2):
    """Descarga la tesela del Catastro; devuelve los bytes PNG o None si no hay respuesta válida.

    El servicio corta a veces conexiones sueltas; se reintenta una vez tras una breve pausa.
    """
    request = urllib.request.Request(wms_url(z, x, y), headers={"User-Agent": USER_AGENT})
    for attempt in range(attempts):
        with _download_slots:
            try:
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    payload = response.read()
                if payload.startswith(PNG_SIGNATURE):
                    return payload
                error = "respuesta sin imagen PNG"
            except (urllib.error.URLError, TimeoutError, OSError) as exception:
                error = exception
        if attempt + 1 < attempts:
            time.sleep(0.5)
    _logger.info("Catastro no ha servido la tesela %s/%s/%s: %s", z, x, y, error)
    return None


def get_tile(dbname, z, x, y, max_age_days=DEFAULT_MAX_AGE_DAYS, download=None):
    """Devuelve los bytes PNG de la tesela desde memoria, disco o Catastro (en ese orden).

    Si la copia en disco ha caducado y el Catastro no responde, se sirve la copia antigua.
    """
    key = (dbname, z, x, y)
    payload = _memory_get(key)
    if payload is not None:
        return payload
    path = tile_path(dbname, z, x, y)
    stale = None
    try:
        age = time.time() - os.path.getmtime(path)
        with open(path, "rb") as handle:
            stale = handle.read()
        if age <= max_age_days * 86400 and stale.startswith(PNG_SIGNATURE):
            _memory_put(key, stale)
            return stale
    except OSError:
        pass
    payload = (download or download_tile)(z, x, y)
    if payload is None:
        return stale if stale and stale.startswith(PNG_SIGNATURE) else None
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
    with open(temporary, "wb") as handle:
        handle.write(payload)
    os.replace(temporary, path)
    _memory_put(key, payload)
    return payload


def cache_stats(dbname):
    """Número de teselas y tamaño en bytes de la caché en disco."""
    count = size = 0
    for folder, _dirs, files in os.walk(cache_root(dbname)):
        for name in files:
            if name.endswith(".png"):
                count += 1
                try:
                    size += os.path.getsize(os.path.join(folder, name))
                except OSError:
                    pass
    return count, size


class FiberGisCatastroTiles(models.AbstractModel):
    _name = "fiber.gis.catastro.tiles"
    _description = "Caché de cartografía del Catastro"

    PRECACHE_PARAM = "fiber_gis.catastro_precache"
    PRECACHE_ZOOMS = (13, 14, 15, 16, 17, 18)
    PRECACHE_MARGIN_DEG = 0.003

    @api.model
    def _max_age_days(self):
        raw = self.env["ir.config_parameter"].sudo().get_param("fiber_gis.catastro_cache_days", DEFAULT_MAX_AGE_DAYS)
        try:
            return min(max(int(raw), 1), 365)
        except (TypeError, ValueError):
            return DEFAULT_MAX_AGE_DAYS

    @api.model
    def get_tile_png(self, z, x, y):
        if not valid_tile(z, x, y):
            return None
        return get_tile(self.env.cr.dbname, z, x, y, self._max_age_days())

    @api.model
    def clear_cache(self):
        clear_memory_cache()
        shutil.rmtree(cache_root(self.env.cr.dbname), ignore_errors=True)

    @api.model
    def cache_summary(self):
        count, size = cache_stats(self.env.cr.dbname)
        state = self._precache_state()
        summary = f"{count} teselas guardadas ({size / 1048576:.1f} MB)."
        if state:
            summary += f" Precarga en curso: {state['done']} de {state['total']} teselas."
        return summary

    @api.model
    def _precache_state(self):
        raw = self.env["ir.config_parameter"].sudo().get_param(self.PRECACHE_PARAM)
        try:
            return json.loads(raw) if raw else None
        except ValueError:
            return None

    @api.model
    def _network_bbox(self):
        """Rectángulo (oeste, sur, este, norte) que cubre los elementos y sitios con coordenadas."""
        points = []
        for model in ("fiber.gis.node", "fiber.gis.site"):
            for record in self.env[model].search_read(
                [("latitude", "!=", False), ("longitude", "!=", False)], ["latitude", "longitude"],
            ):
                points.append((record["latitude"], record["longitude"]))
        if not points:
            return None
        margin = self.PRECACHE_MARGIN_DEG
        return (
            min(p[1] for p in points) - margin, min(p[0] for p in points) - margin,
            max(p[1] for p in points) + margin, max(p[0] for p in points) + margin,
        )

    @api.model
    def start_precache(self):
        """Programa la descarga en segundo plano de las teselas que cubren la red registrada."""
        bbox = self._network_bbox()
        if not bbox:
            return 0
        total = 0
        for z in self.PRECACHE_ZOOMS:
            x0, y0, x1, y1 = tile_range(z, *bbox)
            total += (x1 - x0 + 1) * (y1 - y0 + 1)
        state = {"bbox": bbox, "zooms": list(self.PRECACHE_ZOOMS), "zoom_index": 0, "x": None, "y": None,
                 "done": 0, "total": total}
        self.env["ir.config_parameter"].sudo().set_param(self.PRECACHE_PARAM, json.dumps(state))
        cron = self.env.ref("fiber_gis.ir_cron_fiber_gis_catastro_precache", raise_if_not_found=False)
        if cron:
            cron.sudo()._trigger()
        return total

    @api.model
    def _cron_precache(self):
        """Descarga las teselas pendientes de la precarga programada.

        Usa el progreso por lotes de los crons de Odoo 19 (``_commit_progress``): guarda el avance cada
        pocas teselas y, si se agota el tiempo del cron, Odoo lo vuelve a lanzar para continuar.
        """
        state = self._precache_state()
        if not state:
            return
        dbname, max_age = self.env.cr.dbname, self._max_age_days()
        parameters = self.env["ir.config_parameter"].sudo()
        cron = self.env["ir.cron"]
        zooms = state["zooms"]
        processed = 0
        while state["zoom_index"] < len(zooms):
            z = zooms[state["zoom_index"]]
            x0, y0, x1, y1 = tile_range(z, *state["bbox"])
            x = x0 if state["x"] is None else state["x"]
            y = y0 if state["y"] is None else state["y"]
            get_tile(dbname, z, x, y, max_age)
            processed += 1
            state["done"] += 1
            y += 1
            if y > y1:
                y, x = y0, x + 1
            if x > x1:
                state.update(zoom_index=state["zoom_index"] + 1, x=None, y=None)
            else:
                state.update(x=x, y=y)
            if processed % 20 == 0:
                parameters.set_param(self.PRECACHE_PARAM, json.dumps(state))
                remaining_time = cron._commit_progress(20, remaining=max(state["total"] - state["done"], 0))
                if remaining_time <= 0:
                    return
        parameters.set_param(self.PRECACHE_PARAM, False)
        cron._commit_progress(processed % 20, remaining=0)
        _logger.info("Precarga de cartografía del Catastro terminada: %s teselas.", state["done"])
