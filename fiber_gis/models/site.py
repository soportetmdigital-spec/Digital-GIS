"""Sitios de red y geocodificaci\u00f3n de direcciones."""

import hashlib
import json
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import quote_plus, urlencode, urlparse

from odoo import api, fields, models
from odoo.exceptions import UserError

from .map_icon import map_icon_preview_html
from .local_geocoding import municipality_key, normalize_place, short_address


_NOMINATIM_LOCK = threading.Lock()
_NOMINATIM_LAST_REQUEST = 0.0
_MAP_STREET_AREAS = {
    "granada": {
        "name": "Granada capital",
        "query_name": "Granada",
        "south": 37.145,
        "west": -3.640,
        "north": 37.215,
        "east": -3.545,
    },
    "santa_fe": {
        "name": "Santa Fe",
        "query_name": "Santa Fe",
        "south": 37.175,
        "west": -3.745,
        "north": 37.205,
        "east": -3.680,
    },
}


class FiberGisSite(models.Model):
    _name = "fiber.gis.site"
    _description = "Sitio de red de fibra"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(string="Nombre", tracking=True)
    code = fields.Char(string="Matricula", tracking=True)
    partner_id = fields.Many2one("res.partner", string="Contacto")
    map_icon = fields.Selection(
        [
            ("square", "Cuadrado"),
            ("circle", "Circulo"),
            ("diamond", "Rombo"),
            ("triangle", "Triangulo"),
            ("star", "Estrella"),
            ("network", "Red"),
            ("olt", "OLT / cabecera"),
            ("fdh", "Armario distribucion"),
            ("rack", "Rack"),
            ("cabinet", "Armario"),
            ("building", "Edificio"),
        ],
        string="Icono en mapa",
        default="network",
        required=True,
    )
    color = fields.Char(string="Color en mapa", default="#2563eb", tracking=True)
    map_icon_preview_html = fields.Html(
        string="Vista previa del icono",
        compute="_compute_map_icon_preview_html",
        sanitize=False,
    )
    street = fields.Char(string="Direcci\u00f3n")
    street2 = fields.Char(string="Direcci\u00f3n 2")
    zip = fields.Char(string="C\u00f3digo postal")
    city = fields.Char(string="Ciudad")
    state_id = fields.Many2one("res.country.state", string="Provincia")
    country_id = fields.Many2one("res.country", string="Pa\u00eds")
    latitude = fields.Float(string="Latitud", digits=(10, 7), tracking=True)
    longitude = fields.Float(string="Longitud", digits=(10, 7), tracking=True)
    state = fields.Selection(
        [
            ("planned", "Planificado"),
            ("installed", "Instalado"),
            ("active", "Activo"),
            ("maintenance", "Mantenimiento"),
            ("retired", "Retirado"),
        ],
        string="Estado",
        default="planned",
        tracking=True,
    )
    notes = fields.Text(string="Notas")
    node_ids = fields.One2many("fiber.gis.node", "site_id", string="Elementos")
    node_count = fields.Integer(string="N.\u00ba de elementos", compute="_compute_node_count")
    active = fields.Boolean(string="Activo", default=True)

    _site_code_unique = models.Constraint(
        "UNIQUE(code)",
        "La matricula del sitio debe ser unica.",
    )

    @api.depends("node_ids")
    def _compute_node_count(self):
        for site in self:
            site.node_count = len(site.node_ids)

    @api.depends("map_icon", "color")
    def _compute_map_icon_preview_html(self):
        for site in self:
            labels = dict(site._fields["map_icon"].selection)
            site.map_icon_preview_html = map_icon_preview_html(
                site.map_icon,
                site.color,
                labels.get(site.map_icon, site.map_icon),
            )

    def action_open_google_maps(self):
        self.ensure_one()
        if self.latitude and self.longitude:
            query = f"{self.latitude},{self.longitude}"
        else:
            query = self._get_geocoding_query()
        return {
            "type": "ir.actions.act_url",
            "name": "Abrir en Google Maps",
            "target": "new",
            "url": f"https://www.google.com/maps/search/?api=1&query={quote_plus(query)}",
        }

    def action_geocode_openstreetmap(self):
        for site in self:
            query = site._get_geocoding_query()
            if not query:
                raise UserError("Introduce una direcci\u00f3n o un nombre de sitio antes de obtener coordenadas.")
            result = site._nominatim_geocode(query)
            site.write(
                {
                    "latitude": result["lat"],
                    "longitude": result["lng"],
                }
            )
        return True

    def action_geocode_google_maps(self):
        """Compatibilidad con vistas antiguas: la geocodificacion ya usa OpenStreetMap."""
        return self.action_geocode_openstreetmap()

    def _get_geocoding_query(self):
        self.ensure_one()
        address_parts = [
            self.street,
            self.street2,
            self.zip,
            self.city,
            self.state_id.name,
            self.country_id.name,
        ]
        query = ", ".join(part.strip() for part in address_parts if part and part.strip())
        if not query:
            return ""
        if not self.city and self.state_id and self.state_id.name.lower() == "granada":
            query = f"{query}, Granada"
        if not self.country_id:
            query = f"{query}, Espa\u00f1a"
        return query

    def _nominatim_geocode(self, query):
        cache_key = f"search_local_v2|{query.strip().casefold()}"
        cached = self._nominatim_cache_get(cache_key)
        if cached and cached.get("not_found"):
            raise UserError(f"No se han encontrado coordenadas para '{query}'.")
        if cached:
            return cached
        payload = self._nominatim_request(
            "search",
            {
                "format": "jsonv2",
                "limit": 10,
                "countrycodes": "es",
                "addressdetails": 1,
                "bounded": 1,
                "viewbox": "-3.745,37.215,-3.545,37.145",
                "q": query,
            },
        )
        expected_area = "santa_fe" if "santa fe" in normalize_place(query) else None
        candidates = [
            item for item in payload if isinstance(item, dict)
            and municipality_key(item)
            and (not expected_area or municipality_key(item) == expected_area)
        ] if isinstance(payload, list) else []
        result = None
        for item in candidates:
            try:
                latitude, longitude = float(item["lat"]), float(item["lon"])
            except (KeyError, TypeError, ValueError):
                continue
            if -90 <= latitude <= 90 and -180 <= longitude <= 180:
                result = {"lat": latitude, "lng": longitude}
                break
        if not result:
            self._nominatim_cache_set(cache_key, {"not_found": True})
            raise UserError(f"No se ha encontrado '{query}' en Granada capital o Santa Fe.")
        self._nominatim_cache_set(cache_key, result)
        return result

    @api.model
    def search_map_streets(self, query, area_key="granada"):
        """Busca calles solo cuando el mapa no encuentra inventario local."""
        query = " ".join(str(query or "").strip().split())[:160]
        area_key = area_key if area_key in _MAP_STREET_AREAS else "granada"
        area = _MAP_STREET_AREAS[area_key]
        if len(query) < 2:
            return []
        cache_key = f"map_street_local_v2|{area_key}|{query.casefold()}"
        cached = self._nominatim_cache_get(cache_key)
        if cached is not None:
            return cached.get("results", [])
        payload = self._nominatim_request(
            "search",
            {
                "format": "jsonv2",
                "limit": 20,
                "countrycodes": "es",
                "addressdetails": 1,
                "layer": "address",
                "bounded": 1,
                "viewbox": (
                    f"{area['west']},{area['north']},"
                    f"{area['east']},{area['south']}"
                ),
                "q": f"{query}, {area['query_name']}, Granada, Espa\u00f1a",
            },
        )
        results = []
        results_by_name = {}
        for item in payload if isinstance(payload, list) else []:
            if not isinstance(item, dict) or municipality_key(item) != area_key:
                continue
            address = item.get("address") or {}
            name = (address.get("road") or item.get("name") or "").strip()
            is_road = (
                item.get("addresstype") == "road"
                or item.get("class") == "highway"
                or item.get("category") == "highway"
            )
            if not name or not is_road:
                continue
            deduplication_key = name.casefold()
            try:
                bounding_box = [float(value) for value in item.get("boundingbox", [])]
                latitude = float(item["lat"])
                longitude = float(item["lon"])
            except (KeyError, TypeError, ValueError):
                continue
            if len(bounding_box) != 4:
                bounding_box = [latitude, latitude, longitude, longitude]
            if deduplication_key in results_by_name:
                existing_bounds = results_by_name[deduplication_key]["bounds"]
                existing_bounds["south"] = min(existing_bounds["south"], bounding_box[0])
                existing_bounds["north"] = max(existing_bounds["north"], bounding_box[1])
                existing_bounds["west"] = min(existing_bounds["west"], bounding_box[2])
                existing_bounds["east"] = max(existing_bounds["east"], bounding_box[3])
                continue
            result = {
                "osm_id": item.get("osm_id"),
                "name": name,
                "display_name": short_address(item),
                "municipality": area["name"],
                "latitude": latitude,
                "longitude": longitude,
                "bounds": {
                    "south": bounding_box[0],
                    "north": bounding_box[1],
                    "west": bounding_box[2],
                    "east": bounding_box[3],
                },
            }
            results_by_name[deduplication_key] = result
            results.append(result)
            if len(results) >= 8:
                break
        self._nominatim_cache_set(cache_key, {"results": results})
        return results

    @api.model
    def reverse_geocode_coordinates(self, latitude, longitude):
        try:
            latitude = float(latitude)
            longitude = float(longitude)
        except (TypeError, ValueError):
            return {
                "address": "",
                "warning": "Las coordenadas no son v\u00e1lidas para obtener la direcci\u00f3n.",
            }
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            return {
                "address": "",
                "warning": "Las coordenadas est\u00e1n fuera del rango permitido.",
            }

        try:
            return {
                "address": self._nominatim_reverse_geocode(latitude, longitude),
                "provider": "OpenStreetMap",
                "warning": "",
            }
        except UserError:
            return {
                "address": "",
                "provider": "",
                "warning": "No se ha encontrado una direcci\u00f3n postal para ese punto.",
            }

    def _nominatim_reverse_geocode(self, latitude, longitude):
        cache_key = f"reverse_short_local_v2|{latitude:.7f}|{longitude:.7f}"
        cached = self._nominatim_cache_get(cache_key)
        if cached:
            return cached["address"]
        payload = self._nominatim_request(
            "reverse",
            {
                "format": "jsonv2",
                "lat": f"{latitude:.7f}",
                "lon": f"{longitude:.7f}",
                "zoom": 18,
                "addressdetails": 1,
                "layer": "address",
            },
        )
        address = short_address(payload) if isinstance(payload, dict) else ""
        if not address:
            raise UserError("OpenStreetMap no ha encontrado una direcci\u00f3n para esas coordenadas.")
        self._nominatim_cache_set(cache_key, {"address": address})
        return address

    @api.model
    def _nominatim_request(self, endpoint, params):
        global _NOMINATIM_LAST_REQUEST

        base_url = self._nominatim_base_url()
        email = (self.env["ir.config_parameter"].sudo().get_param(
            "fiber_gis.nominatim_email", ""
        ) or "").strip()
        request_params = dict(params)
        if email:
            request_params["email"] = email
        request = urllib.request.Request(
            f"{base_url}/{endpoint}?{urlencode(request_params)}",
            headers={
                "User-Agent": self._nominatim_user_agent(email),
                "Accept": "application/json",
                "Accept-Language": "es-ES,es;q=0.9",
            },
        )
        with _NOMINATIM_LOCK:
            self._nominatim_wait_for_request_slot()
            try:
                with urllib.request.urlopen(request, timeout=10) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
                raise UserError(f"No se ha podido contactar con OpenStreetMap: {error}") from error
            finally:
                _NOMINATIM_LAST_REQUEST = time.monotonic()
                self.env["ir.config_parameter"].sudo().set_param(
                    "fiber_gis.nominatim_last_request", f"{time.time():.6f}"
                )
        if isinstance(payload, dict) and payload.get("error"):
            raise UserError(f"OpenStreetMap ha rechazado la consulta: {payload['error']}")
        return payload

    @api.model
    def _nominatim_wait_for_request_slot(self):
        """Serializa consultas entre workers y respeta el maximo publico de una por segundo."""
        self.env.cr.execute(
            "SELECT pg_advisory_xact_lock(hashtext(%s))",
            ("fiber_gis.nominatim",),
        )
        raw_timestamp = self.env["ir.config_parameter"].sudo().get_param(
            "fiber_gis.nominatim_last_request", "0"
        )
        try:
            database_delay = 1.05 - (time.time() - float(raw_timestamp))
        except (TypeError, ValueError):
            database_delay = 0.0
        process_delay = 1.05 - (time.monotonic() - _NOMINATIM_LAST_REQUEST)
        wait_seconds = max(0.0, database_delay, process_delay)
        if wait_seconds:
            time.sleep(wait_seconds)

    @api.model
    def _nominatim_base_url(self):
        value = (self.env["ir.config_parameter"].sudo().get_param(
            "fiber_gis.nominatim_url", "https://nominatim.openstreetmap.org"
        ) or "https://nominatim.openstreetmap.org").strip().rstrip("/")
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise UserError("La URL de Nominatim configurada no es valida.")
        return value

    @api.model
    def _nominatim_user_agent(self, email=""):
        contact = f"; {email}" if email else ""
        return f"FiberGIS/19.0.3.37.0 (Odoo 19{contact})"

    @api.model
    def _nominatim_cache_key(self, value):
        source = f"{self._nominatim_base_url()}|{value}"
        digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
        return f"fiber_gis.nominatim_cache.{digest}"

    @api.model
    def _nominatim_cache_get(self, value):
        raw_value = self.env["ir.config_parameter"].sudo().get_param(
            self._nominatim_cache_key(value), ""
        )
        if not raw_value:
            return None
        try:
            return json.loads(raw_value)
        except (TypeError, json.JSONDecodeError):
            return None

    @api.model
    def _nominatim_cache_set(self, value, result):
        self.env["ir.config_parameter"].sudo().set_param(
            self._nominatim_cache_key(value),
            json.dumps(result, ensure_ascii=True, separators=(",", ":")),
        )

    def action_set_planned(self):
        self.write({"state": "planned"})

    def action_set_installed(self):
        self.write({"state": "installed"})

    def action_set_active(self):
        self.write({"state": "active"})

    def action_set_maintenance(self):
        self.write({"state": "maintenance"})

    def action_set_retired(self):
        self.write({"state": "retired"})
