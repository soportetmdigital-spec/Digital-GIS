"""Sitios de red y geocodificaci\u00f3n de direcciones."""

import hashlib
import json
import threading
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus, urlencode, urlparse

from odoo import api, fields, models
from odoo.exceptions import UserError

from .local_geocoding import municipality_key, normalize_place, short_address
from .map_actions import google_maps_action


_NOMINATIM_LOCK = threading.Lock()  # Keep for backward compatibility if needed
_NOMINATIM_LAST_REQUEST = 0.0
_MAP_STREET_AREAS = {
    "granada": {
        "name": "Granada capital",
        "catastro_municipality": "GRANADA",
        "south": 37.145,
        "west": -3.640,
        "north": 37.215,
        "east": -3.545,
    },
    "santa_fe": {
        "name": "Santa Fe",
        "catastro_municipality": "SANTA FE",
        "south": 37.175,
        "west": -3.745,
        "north": 37.205,
        "east": -3.680,
    },
}
_CATASTRO_STREET_TYPES = {
    "calle", "cl", "avenida", "av", "plaza", "pza", "paseo", "ps",
    "cuesta", "ct", "camino", "cm", "carretera", "cr", "travesia",
    "tr", "ronda", "glorieta", "via", "vía", "bajada", "subida",
    "doctor", "dr", "don", "d", "doña", "dna",
}


class FiberGisSite(models.Model):
    _name = "fiber.gis.site"
    _description = "Sitio de red de fibra"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    @api.model
    def get_map_detail_zoom(self):
        """Devuelve el umbral de zoom configurado para mostrar en el mapa nombres e iconos detallados."""
        raw_zoom = self.env["ir.config_parameter"].sudo().get_param("fiber_gis.map_detail_zoom", "0.67")
        try:
            return min(max(float(raw_zoom), 0.1), 10.0)
        except (TypeError, ValueError):
            return 0.67

    name = fields.Char(string="Nombre", tracking=True)
    code = fields.Char(string="Matricula", tracking=True, index=True)
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
        index=True,
    )
    notes = fields.Text(string="Notas")
    node_ids = fields.One2many("fiber.gis.node", "site_id", string="Elementos")
    work_log_ids = fields.One2many(
        "fiber.gis.node.work.log", "site_id", string="Registro técnico",
    )
    node_count = fields.Integer(string="N.\u00ba de elementos", compute="_compute_node_count")
    active = fields.Boolean(string="Activo", default=True)

    _site_code_unique = models.Constraint(
        "UNIQUE(code)",
        "La matricula del sitio debe ser unica.",
    )

    @api.depends("node_ids")
    def _compute_node_count(self):
        """Calcula y actualiza «elemento de red cantidad» a partir de los datos actuales y sus relaciones."""
        for site in self:
            site.node_count = len(site.node_ids)

    @api.depends("map_icon", "color")
    def _compute_map_icon_preview_html(self):
        """Calcula y actualiza «mapa icono vista previa HTML» a partir de los datos actuales y sus relaciones."""
        for site in self:
            labels = dict(site._fields["map_icon"].selection)
            site.map_icon_preview_html = map_icon_preview_html(
                site.map_icon,
                site.color,
                labels.get(site.map_icon, site.map_icon),
            )

    def action_open_google_maps(self):
        """Abre en Google Maps la ubicación del registro seleccionado."""
        self.ensure_one()
        return google_maps_action(self.latitude, self.longitude, self._get_geocoding_query)

    def action_geocode_openstreetmap(self):
        """Ejecuta la acción de usuario «geocodificación OpenStreetMap» y devuelve el resultado correspondiente a Odoo."""
        for site in self:
            query = site._get_geocoding_query()
            if not query:
                raise UserError("Introduce una direcci\u00f3n o un nombre de sitio antes de obtener coordenadas.")
            site._nominatim_wait_for_request_slot()
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
        """Obtiene «geocodificación consulta» aplicando las reglas y relaciones propias del modelo."""
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
        """Consulta Nominatim para localizar la dirección y valida que el resultado pertenezca al ámbito permitido."""
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
        """Busca vias de Catastro cuando no hay coincidencias en el inventario."""
        query = " ".join(str(query or "").strip().split())[:160]
        area_key = area_key if area_key in _MAP_STREET_AREAS else "granada"
        area = _MAP_STREET_AREAS[area_key]
        if len(query) < 2:
            return []
        cache_key = f"map_street_catastro_v2|{area_key}|{query.casefold()}"
        cached = self._catastro_cache_get(cache_key)
        if cached is not None:
            return cached.get("results", [])
        municipality_codes = self._catastro_municipality_codes(area)
        catastro_query = self._catastro_street_name_query(query)
        root = self._catastro_request("ConsultaVia", {
            "Provincia": "GRANADA", "Municipio": area["catastro_municipality"],
            "TipoVia": "", "NombreVia": catastro_query,
        })
        results = []
        seen_codes = set()
        for street in self._catastro_elements(root, "calle"):
            direction = self._catastro_child(street, "dir")
            code = self._catastro_child_text(direction, "cv")
            street_type = self._catastro_child_text(direction, "tv")
            street_name = self._catastro_child_text(direction, "nv")
            if not code or not street_name or code in seen_codes:
                continue
            seen_codes.add(code)
            name = " ".join(value for value in (street_type, street_name) if value)
            results.append({
                "catastro_id": f"{municipality_codes['del']}:{municipality_codes['mun']}:{code}",
                "name": name, "display_name": name, "municipality": area["name"],
                "area_key": area_key,
            })
        normalized_query = normalize_place(query)
        results.sort(key=lambda item: (not normalize_place(item["name"]).startswith(normalized_query), item["name"]))
        results = results[:8]
        self._catastro_cache_set(cache_key, {"results": results})
        return results

    @api.model
    def _catastro_street_name_query(self, query):
        """Catastro recibe el nombre separado del tipo de via."""
        words = str(query or "").strip().split()
        while words and normalize_place(words[0]) in _CATASTRO_STREET_TYPES:
            words.pop(0)
        return " ".join(words) or str(query or "").strip()

    @api.model
    def locate_map_street(self, catastro_id, area_key="granada"):
        """Obtiene la geometria de una via solo cuando el usuario la selecciona."""
        area_key = area_key if area_key in _MAP_STREET_AREAS else "granada"
        try:
            delegation, municipality, street_code = str(catastro_id or "").split(":", 2)
        except ValueError as error:
            raise UserError("La referencia de Catastro no es valida.") from error
        if not all(value.isdigit() for value in (delegation, municipality, street_code)):
            raise UserError("La referencia de Catastro no es valida.")
        cache_key = f"map_street_geometry_catastro_v1|{area_key}|{catastro_id}"
        cached = self._catastro_cache_get(cache_key)
        if cached is not None:
            return cached
        root = self._catastro_wfs_request(delegation, municipality, street_code)
        area = _MAP_STREET_AREAS[area_key]
        coordinates, seen_coordinates = [], set()
        for position in self._catastro_elements(root, "pos"):
            try:
                latitude, longitude = (float(value) for value in (position.text or "").split()[:2])
            except (TypeError, ValueError):
                continue
            if not (area["south"] <= latitude <= area["north"] and area["west"] <= longitude <= area["east"]):
                continue
            coordinate = (round(latitude, 7), round(longitude, 7))
            if coordinate not in seen_coordinates:
                seen_coordinates.add(coordinate)
                coordinates.append(coordinate)
        if not coordinates:
            raise UserError("Catastro no ha devuelto geometria para esta calle.")
        latitudes, longitudes = zip(*coordinates)
        result = {
            "latitude": sorted(latitudes)[len(latitudes) // 2],
            "longitude": sorted(longitudes)[len(longitudes) // 2],
            "bounds": {"south": min(latitudes), "north": max(latitudes), "west": min(longitudes), "east": max(longitudes)},
        }
        self._catastro_cache_set(cache_key, result)
        return result

    @api.model
    def _catastro_municipality_codes(self, area):
        """Consulta o procesa «municipio códigos» mediante los servicios cartográficos del Catastro."""
        cache_key = f"municipality_codes_v1|{area['catastro_municipality']}"
        cached = self._catastro_cache_get(cache_key)
        if cached:
            return cached
        root = self._catastro_request("ConsultaMunicipio", {
            "Provincia": "GRANADA", "Municipio": area["catastro_municipality"],
        })
        wanted_name = normalize_place(area["catastro_municipality"])
        for municipality in self._catastro_elements(root, "muni"):
            if normalize_place(self._catastro_child_text(municipality, "nm")) != wanted_name:
                continue
            location = self._catastro_child(municipality, "locat")
            delegation = self._catastro_child_text(location, "cd")
            code = self._catastro_child_text(location, "cmc")
            if delegation.isdigit() and code.isdigit():
                result = {"del": delegation, "mun": code}
                self._catastro_cache_set(cache_key, result)
                return result
        raise UserError("Catastro no ha encontrado el municipio seleccionado.")

    @api.model
    def _catastro_request(self, endpoint, params):
        """Envía una petición al servicio del Catastro y devuelve la respuesta recibida."""
        request = urllib.request.Request(
            "https://ovc.catastro.meh.es/ovcservweb/OVCSWLocalizacionRC/OVCCallejero.asmx/"
            f"{endpoint}?{urlencode(params)}",
            headers={"User-Agent": "FiberGIS/19.0 (Odoo 19)", "Accept": "application/xml,text/xml;q=0.9,*/*;q=0.8"},
        )
        return self._catastro_xml_response(request)

    @api.model
    def _catastro_wfs_request(self, delegation, municipality, street_code):
        """Consulta el servicio WFS del Catastro para obtener datos vectoriales de la zona."""
        request = urllib.request.Request(
            "https://ovc.catastro.meh.es/INSPIRE/wfsAD.aspx?" + urlencode({
                "service": "WFS", "version": "2.0.0", "request": "GetFeature",
                "STOREDQUERY_ID": "GetADByCodVIA", "DEL": delegation,
                "MUN": municipality, "CODVIA": street_code, "SRSNAME": "EPSG:4326",
            }),
            headers={"User-Agent": "FiberGIS/19.0 (Odoo 19)", "Accept": "application/gml+xml,application/xml,text/xml;q=0.9"},
        )
        return self._catastro_xml_response(request)

    @api.model
    def _catastro_xml_response(self, request):
        """Analiza la respuesta XML del Catastro y devuelve sus elementos interpretados."""
        try:
            with urllib.request.urlopen(request, timeout=12) as response:
                payload = response.read(4_000_001)
        except (urllib.error.URLError, TimeoutError) as error:
            raise UserError(f"No se ha podido contactar con Catastro: {error}") from error
        if len(payload) > 4_000_000:
            raise UserError("La respuesta de Catastro para esta calle es demasiado grande.")
        try:
            return ET.fromstring(payload)
        except ET.ParseError as error:
            raise UserError("Catastro ha devuelto una respuesta no valida.") from error

    @api.model
    def _catastro_elements(self, root, name):
        """Consulta o procesa «elementos» mediante los servicios cartográficos del Catastro."""
        return [element for element in root.iter() if element.tag.rsplit("}", 1)[-1] == name]

    @api.model
    def _catastro_child(self, parent, name):
        """Consulta o procesa «elemento dependiente» mediante los servicios cartográficos del Catastro."""
        if parent is None:
            return None
        return next((element for element in parent if element.tag.rsplit("}", 1)[-1] == name), None)

    @api.model
    def _catastro_child_text(self, parent, name):
        """Consulta o procesa «elemento dependiente texto» mediante los servicios cartográficos del Catastro."""
        child = self._catastro_child(parent, name)
        return (child.text or "").strip() if child is not None else ""

    @api.model
    def _catastro_cache_key(self, value):
        """Consulta o procesa «caché clave» mediante los servicios cartográficos del Catastro."""
        digest = hashlib.sha256(f"catastro|{value}".encode("utf-8")).hexdigest()
        return f"fiber_gis.catastro_cache.{digest}"

    @api.model
    def _catastro_cache_get(self, value):
        """Consulta o procesa «caché consulta» mediante los servicios cartográficos del Catastro."""
        raw_value = self.env["ir.config_parameter"].sudo().get_param(self._catastro_cache_key(value), "")
        if not raw_value:
            return None
        try:
            return json.loads(raw_value)
        except (TypeError, json.JSONDecodeError):
            return None

    @api.model
    def _catastro_cache_set(self, value, result):
        """Consulta o procesa «caché estado» mediante los servicios cartográficos del Catastro."""
        self.env["ir.config_parameter"].sudo().set_param(
            self._catastro_cache_key(value), json.dumps(result, ensure_ascii=True, separators=(",", ":")),
        )

    @api.model
    def reverse_geocode_coordinates(self, latitude, longitude):
        """Obtiene una dirección breve para las coordenadas y restringe el resultado a las poblaciones configuradas."""
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
        """Obtiene una dirección breve a partir de las coordenadas mediante Nominatim."""
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
        """Consulta «petición» mediante el servicio de geocodificación Nominatim."""
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
        self._nominatim_wait_for_request_slot()
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            raise UserError(f"No se ha podido contactar con OpenStreetMap: {error}") from error
        self.env["ir.config_parameter"].sudo().set_param(
            "fiber_gis.nominatim_last_request", f"{time.time():.6f}"
        )
        if isinstance(payload, dict) and payload.get("error"):
            raise UserError(f"OpenStreetMap ha rechazado la consulta: {payload['error']}")
        return payload

    @api.model
    def _nominatim_wait_for_request_slot(self):
        """Serializa consultas respetando el limite publico de una por segundo."""
        raw_timestamp = self.env["ir.config_parameter"].sudo().get_param(
            "fiber_gis.nominatim_last_request", "0"
        )
        try:
            last_request = float(raw_timestamp)
        except (TypeError, ValueError):
            last_request = 0.0
        elapsed = time.time() - last_request
        wait_seconds = max(0.0, 1.0 - elapsed)
        if wait_seconds:
            time.sleep(wait_seconds)

    @api.model
    def _nominatim_base_url(self):
        """Consulta «base URL» mediante el servicio de geocodificación Nominatim."""
        value = (self.env["ir.config_parameter"].sudo().get_param(
            "fiber_gis.nominatim_url", "https://nominatim.openstreetmap.org"
        ) or "https://nominatim.openstreetmap.org").strip().rstrip("/")
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise UserError("La URL de Nominatim configurada no es valida.")
        return value

    @api.model
    def _nominatim_user_agent(self, email=""):
        """Consulta «usuario agente» mediante el servicio de geocodificación Nominatim."""
        contact = f"; {email}" if email else ""
        return f"FiberGIS/19.0.4.25 (Odoo 19{contact})"

    @api.model
    def _nominatim_cache_key(self, value):
        """Consulta «caché clave» mediante el servicio de geocodificación Nominatim."""
        source = f"{self._nominatim_base_url()}|{value}"
        digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
        return f"fiber_gis.nominatim_cache.{digest}"

    @api.model
    def _nominatim_cache_get(self, value):
        """Consulta «caché consulta» mediante el servicio de geocodificación Nominatim."""
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
        """Consulta «caché estado» mediante el servicio de geocodificación Nominatim."""
        self.env["ir.config_parameter"].sudo().set_param(
            self._nominatim_cache_key(value),
            json.dumps(result, ensure_ascii=True, separators=(",", ":")),
        )

    def action_set_planned(self):
        """Cambia el estado del registro a planificado."""
        self.write({"state": "planned"})

    def action_set_installed(self):
        """Cambia el estado del registro a instalado."""
        self.write({"state": "installed"})

    def action_set_active(self):
        """Activa el registro y actualiza su estado."""
        self.write({"state": "active"})

    def action_set_maintenance(self):
        """Marca el registro en mantenimiento."""
        self.write({"state": "maintenance"})

    def action_set_retired(self):
        """Retira el registro de la red activa."""
        self.write({"state": "retired"})
