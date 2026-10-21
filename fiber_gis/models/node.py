"""Elementos de red: CTO, cajas, OLT, arquetas, postes y equipos."""

import base64
import html
import json
import re
import unicodedata
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from .map_icon import map_icon_preview_html
from .map_actions import google_maps_action
from .node_category import NODE_KIND_SELECTION


class FiberGisNode(models.Model):
    _name = "fiber.gis.node"
    _description = "Elemento o equipo de red de fibra"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(string="Nombre", tracking=True)
    code = fields.Char(string="Matricula", tracking=True, index=True)
    node_kind = fields.Selection(
        NODE_KIND_SELECTION,
        string="Categoria tecnica",
        required=True,
        default="box",
        tracking=True,
        index=True,
    )
    node_category_id = fields.Many2one(
        "fiber.gis.node.category",
        string="Modelo",
        default=lambda self: self._node_category_from_kind("box").id,
        tracking=True,
    )
    type_id = fields.Many2one(
        "fiber.gis.asset.type",
        domain="[('category', '=', 'node'), ('node_category_ids', 'in', [node_category_id])]",
        string="Tipo funci\u00f3n",
    )
    deployment_plan_id = fields.Many2one(
        "fiber.gis.deployment.plan",
        string="Plan de despliegue",
        ondelete="set null",
        index=True,
        tracking=True,
    )
    map_icon = fields.Selection(
        [
            ("circle", "Circulo"),
            ("square", "Cuadrado"),
            ("diamond", "Rombo"),
            ("triangle", "Triangulo"),
            ("star", "Estrella"),
            ("network", "Red"),
            ("olt", "OLT / cabecera"),
            ("odf", "ODF"),
            ("fdh", "Armario distribucion"),
            ("cto", "CTO"),
            ("terminal", "Caja terminal"),
            ("cabinet", "Armario"),
            ("closure", "Caja de registro"),
            ("dome_closure", "Cierre de empalme"),
            ("splice", "Fusion / empalme"),
            ("manhole", "Arqueta"),
            ("chamber", "Camara"),
            ("handhole", "Arqueta pequena"),
            ("pole", "Poste"),
            ("aerial_strand", "Tendido aereo"),
            ("duct", "Canalizacion"),
            ("splitter", "Splitter"),
            ("rack", "Rack"),
            ("ont", "ONT/CPE"),
            ("router", "Router cliente"),
            ("drop", "Acometida"),
            ("building", "Edificio"),
            ("customer", "Cliente"),
            ("customer_terminal", "Cliente final"),
            ("tray", "Bandeja"),
        ],
        string="Icono en mapa",
        default="circle",
        required=True,
    )
    color = fields.Char(string="Color en mapa", tracking=True)
    map_icon_preview_html = fields.Html(
        string="Vista previa del icono",
        compute="_compute_map_icon_preview_html",
        sanitize=False,
    )
    site_id = fields.Many2one("fiber.gis.site", string="Sitio")
    parent_id = fields.Many2one("fiber.gis.node", string="Contenedor")
    child_ids = fields.One2many("fiber.gis.node", "parent_id", string="Contenido")
    child_count = fields.Integer(string="Elementos interiores", compute="_compute_child_count")
    latitude = fields.Float(string="Latitud", digits=(10, 7), tracking=True)
    longitude = fields.Float(string="Longitud", digits=(10, 7), tracking=True)
    altitude = fields.Float(string="Altitud (m)")
    address = fields.Char(string="Direcci\u00f3n")
    partner_id = fields.Many2one(
        "res.partner",
        string="Cliente",
        index=True,
        ondelete="set null",
        tracking=True,
    )
    dowisp_id = fields.Integer(string="ID Dowisp", index=True)
    dowisp_created_at = fields.Datetime(string="Fecha creaci\u00f3n Dowisp")
    dowisp_created_by = fields.Char(string="Usuario creaci\u00f3n Dowisp")
    dowisp_updated_by = fields.Char(string="Usuario \u00faltima modificaci\u00f3n Dowisp")
    dowisp_internal_id = fields.Char(string="ID interno Dowisp")
    dowisp_deployment = fields.Char(string="Despliegue Dowisp")
    dowisp_zone = fields.Char(string="Zona Dowisp")
    dowisp_import_file = fields.Char(string="Fichero importaci\u00f3n Dowisp")
    previous_label = fields.Char(string="Etiqueta anterior")
    typology = fields.Char(string="Tipolog\u00eda")
    infrastructure = fields.Char(string="Infraestructura")
    dowisp_model = fields.Char(string="Modelo Dowisp")
    dowisp_geom = fields.Char(
        string="Geometr\u00eda Dowisp",
        help="Ejemplo: SRID=4326;POINT (-3.591644660828528 37.17013590554851). Al importar se rellena latitud/longitud.",
    )
    dowisp_cto = fields.Boolean(string="CTO")
    uuii = fields.Char(string="UUII")
    illuminated = fields.Boolean(string="Iluminada")
    olt_port = fields.Char(string="Puerto OLT")
    fiber_assignment = fields.Text(string="Asignaci\u00f3n de fibras")
    diagram_positions = fields.Text(string="Posiciones diagrama")
    manhole_type = fields.Selection(
        [
            ("sidewalk", "Acera"),
            ("roadway", "Calzada"),
            ("garden", "Jard\u00edn"),
            ("building", "Interior de edificio"),
            ("other", "Otra"),
        ],
        string="Ubicaci\u00f3n",
        help="Lugar donde est\u00e1 instalada la arqueta.",
    )
    manhole_model_id = fields.Many2one(
        "fiber.gis.manhole.type",
        string="Tipo de arqueta",
        ondelete="restrict",
        tracking=True,
    )
    manhole_length_cm = fields.Float(string="Largo (cm)")
    manhole_width_cm = fields.Float(string="Ancho (cm)")
    manhole_depth_cm = fields.Float(string="Profundidad (cm)")
    state = fields.Selection(
        [
            ("planned", "Planificado"),
            ("installed", "Instalado"),
            ("active", "Activo"),
            ("maintenance", "Mantenimiento"),
            ("retired", "Retirado"),
        ],
        default="planned",
        required=True,
        tracking=True,
        index=True,
    )
    manufacturer = fields.Char(string="Fabricante")
    model = fields.Char(string="Modelo del fabricante")
    serial = fields.Char(string="N.\u00ba de serie")
    ont_gpon_serial = fields.Char(
        string="N.\u00ba de serie GPON",
        tracking=True,
        help="Identificador GPON informado por el fabricante u operador.",
    )
    ont_loid = fields.Char(
        string="LOID",
        tracking=True,
        help="Identificador logico usado para registrar la ONT en la red GPON.",
    )
    ont_ploam_password = fields.Char(
        string="Clave PLOAM",
        copy=False,
        help="Clave de autenticacion PLOAM cuando la red la utilice.",
    )
    ont_olt_pon_port = fields.Char(
        string="Puerto OLT / PON",
        tracking=True,
        help="Puerto de la OLT al que queda asociada la ONT.",
    )
    ont_optical_rx_dbm = fields.Float(string="Potencia optica RX (dBm)", digits=(8, 2))
    ont_optical_tx_dbm = fields.Float(string="Potencia optica TX (dBm)", digits=(8, 2))
    ont_mac_address = fields.Char(string="Direccion MAC", tracking=True)
    ont_management_ip = fields.Char(string="IP de gestion", tracking=True)
    ont_firmware_version = fields.Char(string="Version de firmware")
    ont_operation_mode = fields.Selection(
        [
            ("router", "Router"),
            ("bridge", "Bridge"),
            ("mixed", "Mixto"),
        ],
        string="Modo de funcionamiento",
    )
    ont_internet_vlan = fields.Integer(string="VLAN de Internet")
    ont_wifi_ssid = fields.Char(string="Nombre de red Wi-Fi (SSID)")
    ont_wifi_standard = fields.Selection(
        [
            ("wifi4", "Wi-Fi 4"),
            ("wifi5", "Wi-Fi 5"),
            ("wifi6", "Wi-Fi 6"),
            ("wifi6e", "Wi-Fi 6E"),
            ("wifi7", "Wi-Fi 7"),
        ],
        string="Estandar Wi-Fi",
    )
    capacity_ports = fields.Integer(string="Capacidad puertos")
    cable_entry_count = fields.Integer(
        string="Bocas de cable",
        default=4,
        help="Numero de entradas para cables en este elemento. Se puede ajustar al equipo instalado.",
    )
    has_trays = fields.Boolean(string="Tiene bandejas")
    tray_count = fields.Integer(string="Numero de bandejas")
    splitter_in_housing = fields.Boolean(string="Splitter en carcasa")
    image_1920 = fields.Image(string="Foto principal")
    image_preview_html = fields.Html(
        string="Foto",
        compute="_compute_image_preview_html",
        sanitize=False,
    )
    image_source_url = fields.Char(string="Origen foto")
    node_photo_ids = fields.One2many("fiber.gis.node.photo", "node_id", string="Fotos de instalacion")
    splice_photo_ids = fields.One2many(
        "fiber.gis.splice.document", "node_id", string="Fotos de empalme",
        domain=[("kind", "=", "photo")],
    )
    splice_card_ids = fields.One2many(
        "fiber.gis.splice.document", "node_id", string="Cartas de empalme",
        domain=[("kind", "=", "excel")],
    )
    port_ids = fields.One2many("fiber.gis.port", "node_id", string="Puertos")
    incoming_cable_ids = fields.One2many("fiber.gis.cable", "to_node_id", string="Cables de entrada")
    outgoing_cable_ids = fields.One2many("fiber.gis.cable", "from_node_id", string="Cables de salida")
    tray_ids = fields.One2many("fiber.gis.tray", "node_id", string="Bandejas")
    tray_record_count = fields.Integer(string="Bandejas registradas", compute="_compute_tray_record_count")
    splitter_ids = fields.One2many("fiber.gis.splitter", "node_id", string="Splitters")
    tray_visual_html = fields.Html(
        string="Gestor visual de bandejas",
        compute="_compute_tray_visual_html",
        sanitize=False,
    )
    work_log_ids = fields.One2many("fiber.gis.node.work.log", "node_id", string="Registro técnico")
    notes = fields.Text(string="Observaciones")
    active = fields.Boolean(string="Activo", default=True)
    CTO_ILLUMINATED_COLOR = "#16a34a"
    CTO_NOT_ILLUMINATED_COLOR = "#e11d48"

    @api.model
    def default_get(self, fields_list):
        """Completa los valores iniciales del formulario con los valores por defecto del modelo."""
        values = super().default_get(fields_list)
        category = self.env["fiber.gis.node.category"].browse(values.get("node_category_id")).exists()
        if self.env.context.get("default_node_kind") and not self.env.context.get("default_node_category_id"):
            category = self._node_category_from_kind(self.env.context["default_node_kind"])
        if category:
            defaults = {
                "node_category_id": category.id,
                "node_kind": category.node_kind,
                "has_trays": category.has_trays,
                "cable_entry_count": category.cable_entry_count,
                "map_icon": "square" if category.node_kind == "manhole" and not self.env.context.get("default_map_icon") else (
                    category.map_icon or self._default_icon_from_kind(category.node_kind)
                ),
                "color": category.color or self._default_color_from_kind(category.node_kind),
            }
            for name, value in defaults.items():
                if name in fields_list and f"default_{name}" not in self.env.context:
                    values[name] = value
        return values

    @api.model_create_multi
    def create(self, vals_list):
        """Crea los registros y prepara sus relaciones o datos derivados antes de devolverlos."""
        seen_codes = set()
        for values in vals_list:
            self._prepare_name_code_values(values)
            code = values.get("code")
            if code and not self.env.context.get("skip_fiber_gis_code_check"):
                if code in seen_codes:
                    raise ValidationError(f"Ya hay mas de un elemento con la matricula '{code}' en los datos que intentas guardar.")
                seen_codes.add(code)
            self._check_code_available(code)
            self._prepare_dowisp_values(values)
            self._prepare_type_values(values)
            self._prepare_category_values(values)
            self._prepare_manhole_model_values(values)
        nodes = super().create(vals_list)
        nodes._ensure_trays_from_count()
        for node in nodes:
            node._log_work("element", "Elemento creado.")
        if not self.env.context.get("skip_fiber_gis_auto_photo_fetch"):
            for node in nodes:
                node._auto_fetch_equipment_photo()
        return nodes

    def write(self, vals):
        """Actualiza los registros y mantiene coherentes sus campos y relaciones dependientes."""
        result = True
        for node in self:
            values = dict(vals)
            node._prepare_name_code_values(values, node)
            node._check_code_available(values.get("code"), node)
            node._prepare_dowisp_values(values, node)
            node._prepare_type_values(values, node)
            node._prepare_category_values(values, node)
            node._prepare_manhole_model_values(values)
            photo_fields_changed = "manufacturer" in values or "model" in values
            result = super(FiberGisNode, node).write(values) and result
            if values.get("has_trays") or "tray_count" in values:
                node._ensure_trays_from_count()
            if not self.env.context.get("skip_fiber_gis_work_log"):
                node._log_work("element", "Elemento modificado.")
            if photo_fields_changed:
                node._auto_fetch_equipment_photo()
        return result

    @api.onchange("has_trays")
    def _onchange_has_trays(self):
        """Recalcula los campos del formulario al cambiar «tiene bandejas», antes de guardar el registro."""
        for node in self:
            if node.has_trays and not node.tray_count:
                node.tray_count = 1

    @api.onchange("manhole_model_id")
    def _onchange_manhole_model_id(self):
        """Recalcula los campos del formulario al cambiar «arqueta modelo identificador», antes de guardar el registro."""
        for node in self:
            if not node.manhole_model_id:
                continue
            node.manhole_length_cm = node.manhole_model_id.length_cm
            node.manhole_width_cm = node.manhole_model_id.width_cm
            node.manhole_depth_cm = node.manhole_model_id.depth_cm

    @api.model
    def _prepare_manhole_model_values(self, values):
        """Prepara «arqueta modelo valores» y aplica los valores derivados necesarios antes de persistirlos."""
        model_id = values.get("manhole_model_id")
        if not model_id:
            return
        manhole_model = self.env["fiber.gis.manhole.type"].browse(model_id).exists()
        if not manhole_model:
            return
        values.setdefault("manhole_length_cm", manhole_model.length_cm)
        values.setdefault("manhole_width_cm", manhole_model.width_cm)
        values.setdefault("manhole_depth_cm", manhole_model.depth_cm)

    def _ensure_trays_from_count(self):
        """Crea las bandejas que falten para alcanzar el número indicado, sin duplicar las existentes."""
        tray_model = self.env["fiber.gis.tray"]
        for node in self:
            if not node.has_trays or not node.tray_count:
                continue
            existing = node.tray_ids.sorted("sequence")
            missing = node.tray_count - len(existing)
            for index in range(missing):
                number = len(existing) + index + 1
                tray_model.create({
                    "name": f"Bandeja {number}",
                    "node_id": node.id,
                    "sequence": number,
                    "tray_type": "mixed",
                    "capacity": 12,
                })

    def unlink(self):
        """Elimina los registros aplicando las comprobaciones y limpiezas necesarias en sus relaciones."""
        nodes = self._with_descendant_nodes()
        if nodes != self and not self.env.context.get("fiber_gis_unlink_expanded"):
            return nodes.with_context(fiber_gis_unlink_expanded=True).unlink()
        if nodes != self:
            nodes._log_work("delete", "Elemento borrado. Se limpian bandejas, cables y registros relacionados.")
        nodes._unlink_related_network_records()
        return super(FiberGisNode, nodes).unlink()

    def _with_descendant_nodes(self):
        """Devuelve el elemento y sus descendientes, deteniendo el recorrido si detecta una relación circular."""
        nodes = self
        pending = self
        while pending:
            children = self.search([("parent_id", "in", pending.ids)]) - nodes
            nodes |= children
            pending = children
        return nodes

    def _unlink_related_network_records(self):
        """Elimina las conexiones de red dependientes antes de borrar el elemento."""
        self.ensure_one() if len(self) == 1 else None
        cable_model = self.env["fiber.gis.cable"].with_context(active_test=False)
        link_model = self.env["fiber.gis.logical.link"].with_context(active_test=False)
        port_model = self.env["fiber.gis.port"].with_context(active_test=False)
        tray_model = self.env["fiber.gis.tray"].with_context(active_test=False)

        cables = cable_model.search([
            "|",
            ("from_node_id", "in", self.ids),
            ("to_node_id", "in", self.ids),
        ])
        fibers = cables.mapped("fiber_ids")
        trays = tray_model.search([("node_id", "in", self.ids)])
        tray_lines = self.env["fiber.gis.tray.line"].with_context(active_test=False).search([
            "|",
            ("input_fiber_id", "in", fibers.ids),
            ("output_fiber_id", "in", fibers.ids),
        ])
        links = link_model.search([
            "|",
            "|",
            ("from_node_id", "in", self.ids),
            ("to_node_id", "in", self.ids),
            ("fiber_ids", "in", fibers.ids),
        ])
        ports = port_model.search([("node_id", "in", self.ids)])

        if links:
            links.unlink()
        if tray_lines:
            tray_lines.unlink()
        if trays:
            trays.unlink()
        if ports:
            ports.unlink()
        if cables:
            cables.unlink()

    @api.model
    def _clean_name_code_value(self, value):
        """Normaliza un nombre o código y elimina espacios sobrantes antes de compararlo."""
        if not isinstance(value, str):
            return value
        return value.strip() or False

    @api.model
    def _prepare_name_code_values(self, values, record=False):
        """Prepara nombre y matrícula y comprueba posibles duplicados antes de guardar el elemento."""
        if "name" in values:
            values["name"] = self._clean_name_code_value(values.get("name"))
        if "code" in values:
            values["code"] = self._clean_name_code_value(values.get("code"))

        current_name = record.name if record else False
        current_code = record.code if record else False
        name = values.get("name", current_name)
        code = values.get("code", current_code)

        if name and not code:
            values["code"] = name
        elif code and not name:
            values["name"] = code
        elif not name and not code:
            values.setdefault("name", False)
            values.setdefault("code", False)

    @api.onchange("code")
    def _onchange_code_duplicate_warning(self):
        """Recalcula los campos del formulario al cambiar «código duplicado aviso», antes de guardar el registro."""
        for node in self:
            code = (node.code or "").strip()
            if not code:
                continue
            domain = [("code", "=", code)]
            if node.id:
                domain.append(("id", "!=", node.id))
            if self.search_count(domain):
                return {
                    "warning": {
                        "title": "Matricula duplicada",
                        "message": "Ya existe un elemento con esa matricula. Usa otra matricula antes de guardar.",
                    }
                }

    @api.model
    def _check_code_available(self, code, record=False):
        """Valida «código disponible» antes de guardar y rechaza los datos que incumplen las reglas del modelo."""
        if not code:
            return
        if self.env.context.get("skip_fiber_gis_code_check"):
            return
        domain = [("code", "=", code)]
        if record:
            domain.append(("id", "!=", record.id))
        if self.search_count(domain):
            raise ValidationError(f"Ya existe un elemento con la matricula '{code}'. Usa otra matricula antes de guardar.")

    def _log_work(self, work_type, description, employee_id=None):
        """Registra en el historial del elemento el trabajo realizado y el técnico seleccionado."""
        if self.env.context.get("skip_fiber_gis_work_log"):
            return
        from .work_log import work_employee_id
        if employee_id is None:
            employee_id = work_employee_id(self.env)
        employee = self.env["hr.employee.public"].browse(employee_id).exists()
        if employee:
            employee.check_access("read")
        for node in self:
            if node.id:
                self.env["fiber.gis.node.work.log"].sudo().create({
                    "node_id": node.id,
                    "node_name": node.display_name,
                    "work_type": work_type,
                    "description": description,
                    "user_id": self.env.uid,
                    "employee_id": employee.id or False,
                    "employee_name": employee.name if employee else False,
                })

    def _equipment_photo_query(self):
        """Prepara la consulta de búsqueda de imagen a partir del fabricante y modelo del equipo."""
        self.ensure_one()
        return " ".join(part for part in [self.manufacturer, self.model] if part).strip()

    def _auto_fetch_equipment_photo(self):
        """Busca una fotografía del modelo de equipo y guarda la imagen encontrada si es válida."""
        if self.env.context.get("skip_fiber_gis_auto_photo_fetch"):
            return
        for node in self:
            if node.image_1920 or not node._equipment_photo_query():
                continue
            try:
                node.action_fetch_equipment_photo()
            except Exception:
                node.message_post(body="No se ha podido obtener automaticamente la foto del equipo.")

    def action_fetch_equipment_photo(self):
        """Ejecuta la acción de usuario «consulta equipo fotografía» y devuelve el resultado correspondiente a Odoo."""
        for node in self:
            query = node._equipment_photo_query()
            if not query:
                raise UserError("Indica fabricante y/o modelo antes de buscar una foto.")
            image_url = node._find_equipment_image_url(query)
            if not image_url:
                raise UserError(f"No se ha encontrado una foto para '{query}'.")
            image_data, mimetype = node._download_image(image_url)
            encoded = base64.b64encode(image_data)
            attachment = self.env["ir.attachment"].create({
                "name": f"{query[:80]}.jpg",
                "datas": encoded,
                "res_model": node._name,
                "res_id": node.id,
                "mimetype": mimetype,
            })
            node.with_context(skip_fiber_gis_work_log=True).write({
                "image_1920": encoded,
                "image_source_url": image_url,
            })
            node._log_work("element", f"Foto del equipo actualizada desde {image_url}.")
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Foto actualizada",
                "message": "Se ha a\u00f1adido la foto del equipo.",
                "type": "success",
                "sticky": False,
            },
        }

    def action_clear_equipment_photo(self):
        """Ejecuta la acción de usuario «limpieza equipo fotografía» y devuelve el resultado correspondiente a Odoo."""
        for node in self:
            node.with_context(skip_fiber_gis_work_log=True).write({
                "image_1920": False,
                "image_source_url": False,
            })
            node._log_work("element", "Foto principal del equipo borrada.")
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Foto borrada",
                "message": "Se ha borrado la foto principal del elemento.",
                "type": "success",
                "sticky": False,
            },
        }

    @api.model
    def _find_equipment_image_url(self, query):
        """Busca una dirección de imagen adecuada para el modelo del equipo."""
        return self._find_commons_image_url(query) or self._find_duckduckgo_image_url(query)

    @api.model
    def _find_commons_image_url(self, query):
        """Busca una imagen reutilizable en Wikimedia Commons para el equipo."""
        params = urlencode({
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrnamespace": 6,
            "gsrsearch": query,
            "gsrlimit": 5,
            "prop": "imageinfo",
            "iiprop": "url|mime",
        })
        request = Request(
            f"https://commons.wikimedia.org/w/api.php?{params}",
            headers={"User-Agent": "FiberGIS-Odoo/1.0"},
        )
        with urlopen(request, timeout=7) as response:
            payload = json.loads(response.read().decode("utf-8"))
        pages = payload.get("query", {}).get("pages", {})
        for page in pages.values():
            info = (page.get("imageinfo") or [{}])[0]
            mime = info.get("mime") or ""
            url = info.get("url")
            if url and mime.startswith("image/"):
                return url
        return False

    @api.model
    def _find_duckduckgo_image_url(self, query):
        """Localiza resultados de imagen mediante el buscador DuckDuckGo."""
        search_url = f"https://duckduckgo.com/?{urlencode({'q': query, 'iax': 'images', 'ia': 'images'})}"
        headers = {
            "User-Agent": "Mozilla/5.0 FiberGIS-Odoo/1.0",
            "Accept": "text/html,application/xhtml+xml",
        }
        with urlopen(Request(search_url, headers=headers), timeout=8) as response:
            html_page = response.read().decode("utf-8", errors="ignore")
        token_match = re.search(r"vqd=['\"]?([^&'\"\\]+)", html_page)
        if not token_match:
            return False
        params = urlencode({
            "l": "es-es",
            "o": "json",
            "q": query,
            "vqd": token_match.group(1),
            "f": ",,,,,",
            "p": "1",
        })
        image_request = Request(
            f"https://duckduckgo.com/i.js?{params}",
            headers={
                "User-Agent": "Mozilla/5.0 FiberGIS-Odoo/1.0",
                "Accept": "application/json",
                "Referer": search_url,
            },
        )
        with urlopen(image_request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8", errors="ignore"))
        for result in payload.get("results", []):
            image_url = result.get("image") or result.get("thumbnail")
            if image_url and image_url.startswith(("http://", "https://")):
                return image_url
        return False

    @api.model
    def _download_image(self, image_url):
        """Descarga una imagen remota y comprueba su respuesta antes de devolverla."""
        request = Request(image_url, headers={"User-Agent": "FiberGIS-Odoo/1.0"})
        with urlopen(request, timeout=10) as response:
            data = response.read(5 * 1024 * 1024)
            mimetype = response.headers.get_content_type() or "image/jpeg"
        if not data:
            raise UserError("La imagen encontrada esta vacia.")
        if not mimetype.startswith("image/"):
            raise UserError("El resultado encontrado no es una imagen valida.")
        return data, mimetype

    @api.model
    def _prepare_dowisp_values(self, values, node=None):
        """Prepara «dowisp valores» y aplica los valores derivados necesarios antes de persistirlos."""
        if values.get("dowisp_cto") and not values.get("node_kind"):
            values["node_kind"] = "cto"
        is_cto = values.get("node_kind") == "cto" or values.get("dowisp_cto") or (node and node.node_kind == "cto")
        if is_cto and "illuminated" in values and "node_category_id" not in values:
            # El color elegido a mano no debe perderse al editar Cobertura CTO.
            if not node or node.color == self._get_cto_color(node.illuminated):
                values.setdefault("color", self._get_cto_color(values["illuminated"]))
        geom = values.get("dowisp_geom")
        if geom and not values.get("latitude") and not values.get("longitude"):
            coordinates = self._parse_dowisp_point(geom)
            if coordinates:
                values["longitude"], values["latitude"] = coordinates

    @api.onchange("type_id")
    def _onchange_type_id(self):
        """Recalcula los campos del formulario al cambiar «tipo identificador», antes de guardar el registro."""
        for node in self:
            if node.type_id and not node.node_category_id:
                node.node_category_id = node.type_id.node_category_ids[:1]
                node._onchange_node_category_id()

    @api.onchange("node_category_id")
    def _onchange_node_category_id(self):
        """Recalcula los campos del formulario al cambiar «elemento de red categoría identificador», antes de guardar el registro."""
        for node in self:
            if node.node_category_id:
                node.node_kind = node.node_category_id.node_kind
                node.has_trays = node.node_category_id.has_trays
                if node.has_trays and not node.tray_count:
                    node.tray_count = 1
                node.map_icon = node.node_category_id.map_icon or node._default_icon_from_kind(node.node_kind)
                node.color = node.node_category_id.color
                node.cable_entry_count = node.node_category_id.cable_entry_count
            if node.type_id and node.node_category_id not in node.type_id.node_category_ids:
                node.type_id = False

    @api.model
    def _prepare_type_values(self, values, node=None):
        """Prepara «tipo valores» y aplica los valores derivados necesarios antes de persistirlos."""
        type_id = values.get("type_id")
        if not type_id or values.get("node_category_id") or values.get("node_kind"):
            return
        if (node and node.node_category_id) or self.env.context.get("default_node_category_id"):
            return
        function = self.env["fiber.gis.asset.type"].browse(type_id).exists()
        if function.node_category_ids:
            values["node_category_id"] = function.node_category_ids[0].id

    @api.model
    def _prepare_category_values(self, values, node=None):
        """Prepara «categoría valores» y aplica los valores derivados necesarios antes de persistirlos."""
        if node and not {"node_category_id", "node_kind"}.intersection(values):
            return
        category_id = values.get("node_category_id")
        if category_id:
            category = self.env["fiber.gis.node.category"].browse(category_id).exists()
        elif "node_category_id" in values:
            # Permite vaciar el modelo sin reutilizar una funcion incompatible.
            if "type_id" not in values:
                values["type_id"] = False
            return
        elif node and node.node_category_id and node.node_category_id.node_kind == values.get("node_kind"):
            category = node.node_category_id
        else:
            kind = values.get("node_kind") or self.env.context.get("default_node_kind") or "box"
            context_model = self.env.context.get("default_node_category_id")
            category = (
                self.env["fiber.gis.node.category"].browse(context_model).exists()
                if context_model and "node_kind" not in values else self._node_category_from_kind(kind)
            )
        if category:
            values["node_category_id"] = category.id
            values["node_kind"] = category.node_kind
            if not node or node.node_category_id != category:
                values.setdefault("has_trays", category.has_trays)
                if category.has_trays:
                    values.setdefault("tray_count", 1)
            if not node or node.node_category_id != category:
                values.setdefault("cable_entry_count", category.cable_entry_count)
            if not node or node.node_category_id != category:
                values.setdefault(
                    "map_icon",
                    "square" if category.node_kind == "manhole" else (
                        category.map_icon or self._default_icon_from_kind(category.node_kind)
                    ),
                )
                values.setdefault("color", category.color or self._default_color_from_kind(category.node_kind))
            if node and node.type_id and "type_id" not in values:
                if category not in node.type_id.node_category_ids:
                    values["type_id"] = False

    @api.constrains("node_category_id", "type_id")
    def _check_model_function(self):
        """Valida que la función elegida pertenezca al modelo de elemento seleccionado."""
        for node in self:
            function = node.type_id
            if function and (
                function.category != "node" or node.node_category_id not in function.node_category_ids
            ):
                raise ValidationError(
                    "El tipo de funci\u00f3n no es compatible con el modelo. "
                    "Selecciona una funci\u00f3n del modelo o configura la relaci\u00f3n en Modelos."
                )

    @api.model
    def _node_category_from_kind(self, kind):
        """Relaciona el tipo técnico interno con la categoría de elemento que muestra la interfaz."""
        if not kind:
            return self.env["fiber.gis.node.category"]
        return self.env["fiber.gis.node.category"].search([("node_kind", "=", kind)], limit=1)

    @api.model
    def _default_icon_from_kind(self, kind):
        """Devuelve el icono predeterminado asociado al tipo de elemento."""
        return {
            "site": "network",
            "olt": "olt",
            "odf": "odf",
            "cabinet": "fdh",
            "cto": "cto",
            "box": "terminal",
            "closure": "closure",
            "manhole": "square",
            "pole": "pole",
            "splitter": "splitter",
            "rack": "rack",
            "ont": "ont",
        }.get(kind, "circle")

    @api.model
    def _default_color_from_kind(self, kind):
        """Devuelve el color inicial predeterminado según el tipo de elemento."""
        return "#000000" if kind == "manhole" else False

    @api.model
    def _node_kind_from_type(self, type_record):
        """Obtiene el tipo de elemento de red asociado a su tipo GIS."""
        if not type_record:
            return False
        code = (type_record.code or "").upper()
        return {
            "OLT": "olt",
            "ODF": "odf",
            "CTO": "cto",
            "BOX": "box",
            "CLOSURE": "closure",
            "MANHOLE": "manhole",
            "POLE": "pole",
            "SPLITTER": "splitter",
            "RACK": "rack",
            "CABINET": "cabinet",
            "ONT": "ont",
            "CPE": "ont",
            "SITE": "site",
        }.get(code, "other" if type_record.category == "node" else False)

    @api.model
    def _get_cto_color(self, illuminated):
        """Obtiene el color de fibra que corresponde a la boca de la CTO."""
        return self.CTO_ILLUMINATED_COLOR if illuminated else self.CTO_NOT_ILLUMINATED_COLOR

    @api.model
    def action_update_cto_colors(self):
        """Ejecuta la acción de usuario «actualización CTO colores» y devuelve el resultado correspondiente a Odoo."""
        ctos = self.search(["|", ("node_kind", "=", "cto"), ("dowisp_cto", "=", True)])
        for cto in ctos:
            cto.with_context(skip_cto_color_prepare=True).write({
                "color": self._get_cto_color(cto.illuminated),
            })
        return len(ctos)

    @api.model
    def _parse_dowisp_point(self, geom):
        """Interpreta una coordenada recibida de Dowisp y devuelve un punto geográfico utilizable."""
        match = re.search(
            r"POINT\s*\(\s*(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s*\)",
            geom or "",
            re.IGNORECASE,
        )
        if not match:
            return False
        return (float(match.group(1)), float(match.group(2)))

    @api.depends("child_ids")
    def _compute_child_count(self):
        """Calcula y actualiza «elemento dependiente cantidad» a partir de los datos actuales y sus relaciones."""
        for node in self:
            node.child_count = len(node.child_ids)

    @api.depends("tray_ids")
    def _compute_tray_record_count(self):
        """Calcula y actualiza «bandeja registro cantidad» a partir de los datos actuales y sus relaciones."""
        for node in self:
            node.tray_record_count = len(node.tray_ids)

    @api.depends(
        "tray_ids.name",
        "tray_ids.sequence",
        "tray_ids.tray_type",
        "tray_ids.capacity",
        "tray_ids.line_ids.position",
        "tray_ids.line_ids.line_type",
        "tray_ids.line_ids.input_fiber_id",
        "tray_ids.line_ids.output_fiber_id",
        "tray_ids.line_ids.input_fiber_id.cable_id.name",
        "tray_ids.line_ids.output_fiber_id.cable_id.name",
        "tray_ids.line_ids.input_fiber_color",
        "tray_ids.line_ids.output_fiber_color",
        "tray_ids.line_ids.input_tube",
        "tray_ids.line_ids.output_tube",
        "tray_ids.line_ids.input_tube_color",
        "tray_ids.line_ids.output_tube_color",
        "tray_ids.line_ids.splitter_ratio",
        "tray_ids.line_ids.splitter_id",
        "tray_ids.line_ids.splitter_id.output_ids.output_fiber_id",
        "tray_ids.line_ids.splitter_id.input_output_id",
        "tray_ids.line_ids.splitter_id.output_ids.downstream_splitter_ids",
        "tray_ids.line_ids.state",
        "tray_ids.line_ids.notes",
    )
    def _compute_tray_visual_html(self):
        """Calcula y actualiza «bandeja visual HTML» a partir de los datos actuales y sus relaciones."""
        for node in self:
            node.tray_visual_html = node._build_tray_visual_html()

    def _build_tray_visual_html(self):
        """Construye «bandeja visual HTML» con los datos del modelo para mostrarlo o imprimirlo."""
        self.ensure_one()
        if not self.tray_ids:
            return (
                "<div class='o_fiber_tray_empty'>"
                "Este elemento no tiene bandejas registradas."
                "</div>"
            )
        cards = []
        for tray in self.tray_ids.sorted(lambda item: (item.sequence, item.name or "")):
            rows = []
            # En la ficha se agrupan los trabajos por función: splitter, fusión,
            # fibras en punta y, al final, sangrías. La posición se conserva en
            # los registros y se usa como orden estable dentro de cada grupo.
            tray_line_priority = {
                "splitter": 0,
                "fusion": 1,
                "free": 2,
                "pending_cancel": 2,
                "pass": 3,
            }
            for line in tray.line_ids.sorted(
                lambda item: (tray_line_priority.get(item.line_type, 4), item.position, item.id)
            ):
                rows.append(self._tray_line_visual_html(line))
            no_lines = "<div class='o_fiber_tray_no_lines'>Sin fibras registradas.</div>"
            tray_lines = "".join(rows) or no_lines
            cards.append(
                f"<section class='o_fiber_tray_card' data-tray-id='{tray.id}'>"
                "<header class='o_fiber_tray_card_header'>"
                f"<strong>{html.escape(tray.name or 'Bandeja')}</strong>"
                f"<span>{tray.used_positions} trabajos</span>"
                "</header>"
                f"<div class='o_fiber_tray_lines'>{tray_lines}</div>"
                "</section>"
            )
        return (
            "<div class='o_fiber_tray_visual'>"
            f"{''.join(cards)}"
            "</div>"
        )

    def _tray_line_visual_html(self, line):
        """Construye la representación HTML de una operación y sus fibras en la bandeja."""
        type_labels = dict(line._fields["line_type"].selection)
        type_label = type_labels.get(line.line_type, line.line_type or "")
        input_html = self._fiber_endpoint_html(line.input_fiber_id, line.input_tube, line.input_tube_color, line.input_fiber_color)
        input_html = input_html or "<span class='o_fiber_endpoint is-empty'>Sin fibra asignada</span>"
        if line.splitter_id.input_output_id:
            source = line.splitter_id.input_output_id
            input_html = (
                f"<span class='o_fiber_endpoint'><b>{html.escape(source.splitter_id.display_name)}</b>"
                f"<em>Salida {source.sequence} - {html.escape(source.splitter_id.tray_id.display_name)}</em></span>"
            )
        output = self._fiber_endpoint_html(line.output_fiber_id, line.output_tube, line.output_tube_color, line.output_fiber_color)
        if line.line_type in ("free", "pending_cancel"):
            arrow_html = ""
            output_html = ""
        elif line.line_type == "pass":
            if line.output_fiber_id:
                arrow_html = "<span class='o_fiber_tray_arrow'>&rarr;</span>"
                output_html = output or "<span class='o_fiber_endpoint is-empty'>Sin cable de salida</span>"
            else:
                # Mantiene legibles los registros antiguos que solo guardaban la fibra de entrada.
                arrow_html = ""
                output_html = "<span class='o_fiber_endpoint is-empty'>Sangría sin continuidad registrada</span>"
        elif line.line_type == "splitter":
            arrow_html = "<span class='o_fiber_tray_arrow'>&rarr;</span>"
            if line.splitter_id:
                output_html = (
                    "<span class='o_fiber_endpoint is-empty'>"
                    f"{line.splitter_id.connected_output_count}/"
                    f"{line.splitter_id.output_count} salidas ocupadas"
                    "</span>"
                )
            else:
                output_html = "<span class='o_fiber_endpoint is-empty'>Salida splitter</span>"
        else:
            arrow_html = "<span class='o_fiber_tray_arrow'>&rarr;</span>"
            output_html = output or "<span class='o_fiber_endpoint is-empty'>Sin salida</span>"
        splitter = f"<span class='o_fiber_tray_ratio'>{html.escape(line.splitter_ratio)}</span>" if line.splitter_ratio else ""
        notes = f"<small>{html.escape(line.notes or '')}</small>" if line.notes else ""
        pending_class = " is-pending-cancel" if line.line_type == "pending_cancel" else ""
        return (
            f"<article class='o_fiber_tray_line{pending_class}' draggable='true' data-line-id='{line.id}' data-node-id='{self.id}' tabindex='0' role='button' title='Doble clic para abrir la fibra; arrastrar para mover a otra bandeja'>"
            f"<span class='o_fiber_tray_type'>{html.escape(type_label)}</span>"
            f"{input_html}"
            f"{arrow_html}"
            f"{output_html}"
            f"{splitter}"
            f"{notes}"
            "<button class='o_fiber_tray_delete' type='button' title='Borrar registro' aria-label='Borrar registro'>"
            "<span class='fa fa-trash' aria-hidden='true'></span>"
            "</button>"
            "</article>"
        )

    def _fiber_endpoint_html(self, fiber, tube, tube_color, fiber_color):
        """Muestra para un extremo la fibra, el elemento, la bandeja y la operación registrados."""
        if not fiber:
            return ""
        cable = fiber.cable_id.display_name or ""
        fiber_text = f"F{fiber.number}"
        parts = []
        if tube:
            tube_text = f"T{tube}"
            tube_swatch = f"<i style='background:{html.escape(tube_color or '#e5e7eb')}'></i>"
            parts.append(f"{tube_swatch}{html.escape(tube_text)}")
        fiber_swatch = f"<i style='background:{html.escape(fiber_color or '#e5e7eb')}'></i>"
        parts.append(f"{fiber_swatch}{html.escape(fiber_text)}")
        fiber_label = " ".join(parts)
        endpoint_label = self._fiber_endpoint_label(fiber)
        endpoint_html = (
            f"<em title='{html.escape(endpoint_label)}'>{html.escape(endpoint_label)}</em>"
            if endpoint_label
            else ""
        )
        return (
            f"<span class='o_fiber_endpoint' data-fiber-id='{fiber.id}'>"
            f"<span class='o_fiber_endpoint_id'>{fiber_label}</span>"
            f"<b title='{html.escape(cable)}'>{html.escape(cable)}</b>"
            f"{endpoint_html}"
            "</span>"
        )

    def _fiber_endpoint_label(self, fiber):
        """Devuelve la dirección o el elemento identificativo de un extremo de fibra."""
        self.ensure_one()
        cable = fiber.cable_id
        if cable.from_node_id == self:
            return self._format_fiber_endpoint(cable.to_node_id)
        if cable.to_node_id == self:
            return self._format_fiber_endpoint(cable.from_node_id)
        endpoint = cable.to_node_id or cable.from_node_id
        return self._format_fiber_endpoint(endpoint)

    def _format_fiber_endpoint(self, endpoint):
        """Formatea la fibra, su bandeja y el elemento conectado para mostrar el extremo."""
        if not endpoint:
            return ""
        label = endpoint.display_name or endpoint.name or endpoint.code or "Elemento"
        if endpoint.address:
            return f"{label} - {endpoint.address}"
        return label

    @api.depends("map_icon", "color")
    def _compute_map_icon_preview_html(self):
        """Calcula y actualiza «mapa icono vista previa HTML» a partir de los datos actuales y sus relaciones."""
        for node in self:
            labels = dict(node._fields["map_icon"].selection)
            node.map_icon_preview_html = map_icon_preview_html(
                node.map_icon,
                node.color,
                labels.get(node.map_icon, node.map_icon),
            )

    @api.depends("image_1920")
    def _compute_image_preview_html(self):
        """Calcula y actualiza «imagen vista previa HTML» a partir de los datos actuales y sus relaciones."""
        for node in self:
            if not node.image_1920 or not node.id:
                node.image_preview_html = ""
                continue
            image_url = f"/web/image/fiber.gis.node/{node.id}/image_1920"
            node.image_preview_html = (
                "<div class='o_fiber_gis_node_photo_preview'>"
                f"<img src='{image_url}'/>"
                "</div>"
            )

    @api.constrains("latitude", "longitude")
    def _check_coordinates(self):
        """Valida «coordenadas» antes de guardar y rechaza los datos que incumplen las reglas del modelo."""
        for node in self:
            if node.latitude and not -90 <= node.latitude <= 90:
                raise ValidationError("La latitud debe estar entre -90 y 90.")
            if node.longitude and not -180 <= node.longitude <= 180:
                raise ValidationError("La longitud debe estar entre -180 y 180.")

    def action_open_map(self):
        """Abre el registro seleccionado en el mapa de Fiber GIS."""
        self.ensure_one()
        params = {
            "target_node_id": self.id,
        }
        if self.deployment_plan_id:
            params["deployment_plan_id"] = self.deployment_plan_id.id
        return {
            "type": "ir.actions.client",
            "tag": "fiber_gis.map_action",
            "name": "Mapa de Fibra",
            "params": params,
        }

    def action_delete_element(self):
        """Ejecuta la acción de usuario «borrado elemento» y devuelve el resultado correspondiente a Odoo."""
        self.ensure_one()
        self.unlink()
        return {
            "type": "ir.actions.act_window_close",
        }

    def action_open_trace_wizard(self):
        """Abre el asistente para diagnosticar el recorrido de una fibra."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Trazar fibra",
            "res_model": "fiber.gis.trace.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_node_id": self.id,
            },
        }

    def action_open_tray_wizard(self):
        """Abre el asistente de operaciones de bandeja para el elemento seleccionado."""
        self.ensure_one()
        if self.has_trays and self.tray_count and not self.tray_ids:
            self._ensure_trays_from_count()
        cable = self.incoming_cable_ids[:1] or self.outgoing_cable_ids[:1]
        return {
            "type": "ir.actions.act_window",
            "name": "Gestionar bandejas",
            "res_model": "fiber.gis.cable.tray.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_node_id": self.id,
                "default_cable_id": cable.id if cable else False,
                "default_from_fiber": 1,
                "default_to_fiber": cable.total_fiber_count if cable else 1,
            },
        }

    def action_open_splice_upload(self):
        """Abre el formulario para adjuntar una carta Excel a este elemento."""
        self.ensure_one()
        if not self.has_trays or self.node_kind == "ont":
            raise UserError("Las cartas de empalme solo están disponibles en elementos con bandejas.")
        return {
            "type": "ir.actions.act_window",
            "name": "Subir carta Excel",
            "res_model": "fiber.gis.splice.document",
            "view_mode": "form",
            "view_id": self.env.ref("fiber_gis.view_fiber_gis_splice_document_upload_form").id,
            "target": "new",
            "context": {
                "default_node_id": self.id,
                "default_kind": "excel",
                "default_name": False,
            },
        }

    def action_open_google_maps(self):
        """Abre en Google Maps la ubicación del registro seleccionado."""
        self.ensure_one()
        return google_maps_action(self.latitude, self.longitude, self._get_geocoding_query)

    def action_geocode_openstreetmap(self):
        """Ejecuta la acción de usuario «geocodificación OpenStreetMap» y devuelve el resultado correspondiente a Odoo."""
        site_model = self.env["fiber.gis.site"]
        for node in self:
            query = node._get_geocoding_query()
            if not query:
                raise UserError("Introduce una direccion, nombre o matricula antes de obtener coordenadas.")
            result = site_model._nominatim_geocode(query)
            node.write(
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
        if self.address and self.address.strip():
            query = self.address.strip()
        else:
            parts = [self.name, self.code, self.site_id.city]
            query = ", ".join(part.strip() for part in parts if part and part.strip())
        if not query:
            return ""
        if "granada" not in query.lower():
            query = f"{query}, Granada"
        if "espa" not in query.lower() and "spain" not in query.lower():
            query = f"{query}, Espa\u00f1a"
        return query

    @api.model
    def _customer_address(self, customer):
        """Forma la dirección del cliente usando solo los campos de contacto disponibles."""
        customer = customer.exists()
        if not customer:
            return ""
        city_line = " ".join(
            part.strip() for part in [customer.zip, customer.city] if part and part.strip()
        )
        parts = [
            customer.street,
            customer.street2,
            city_line,
            customer.state_id.name,
            customer.country_id.name,
        ]
        return ", ".join(part.strip() for part in parts if part and part.strip())

    @api.model
    def _customer_partner_coordinates(self, customer):
        """Obtiene las coordenadas del contacto cuando la instalación dispone de esos campos geográficos."""
        if (
            not customer
            or "partner_latitude" not in customer._fields
            or "partner_longitude" not in customer._fields
        ):
            return 0.0, 0.0
        return (
            float(customer.partner_latitude or 0.0),
            float(customer.partner_longitude or 0.0),
        )

    @api.model
    def _customer_business_identifier(self, customer):
        """Devuelve el identificador de cliente que se guarda en el registro de acometida."""
        customer.ensure_one()
        allowed_types = {"char", "text", "integer"}
        label_candidates = {
            "id cliente",
            "id de cliente",
            "identificador cliente",
            "identificador de cliente",
        }
        field_names = ["x_legacy_cliente_id"]

        # Custom Studio fields vary between installations, so their visible label
        # is more reliable than their technical name.
        for field_name, field in customer._fields.items():
            label = unicodedata.normalize("NFKD", field.string or "")
            label = "".join(char for char in label if not unicodedata.combining(char))
            if label.casefold().strip() in label_candidates:
                field_names.append(field_name)

        field_names.extend([
            "x_studio_id_de_cliente",
            "x_studio_id_cliente",
            "id_cliente",
            "customer_code",
            "client_code",
            "ref",
        ])
        for field_name in dict.fromkeys(field_names):
            field = customer._fields.get(field_name)
            if not field or field.type not in allowed_types:
                continue
            value = customer[field_name]
            if value not in (False, None, ""):
                token = re.sub(r"[^0-9A-Za-z._-]+", "-", str(value).strip()).strip("-")
                if token:
                    return token

        raise UserError(
            "El cliente no tiene informado su ID de cliente. "
            "Completa ese dato en la ficha del contacto antes de crear la acometida."
        )

    def _ensure_customer_drop(self, customer, address=None, latitude=0.0, longitude=0.0):
        """Busca o crea el extremo de cliente, el cable de acometida y su primera fibra sin duplicar registros."""
        self.ensure_one()
        customer = customer.exists()
        if not customer:
            raise UserError("Selecciona el cliente al que llega la acometida.")
        if not self.latitude or not self.longitude:
            raise UserError("El elemento de origen necesita coordenadas para dibujar la acometida.")

        endpoint = self.with_context(active_test=False).search([
            ("partner_id", "=", customer.id),
            ("node_kind", "=", "ont"),
        ], limit=1)
        address = (address or "").strip() or endpoint.address or self._customer_address(customer)
        latitude = float(latitude or 0.0)
        longitude = float(longitude or 0.0)
        if not latitude and not longitude and endpoint:
            latitude, longitude = endpoint.latitude, endpoint.longitude
        if not latitude and not longitude:
            latitude, longitude = self._customer_partner_coordinates(customer)
        if bool(latitude) != bool(longitude):
            raise UserError("Indica tanto la latitud como la longitud del cliente.")
        if not latitude or not longitude:
            if not address:
                raise UserError("El cliente necesita una direcci\u00f3n o coordenadas para situarlo en el mapa.")
            site_model = self.env["fiber.gis.site"]
            result = site_model._nominatim_geocode(address)
            latitude, longitude = result["lat"], result["lng"]

        node_type = self.env.ref("fiber_gis.type_node_ont", raise_if_not_found=False)
        if not node_type:
            node_type = self.env["fiber.gis.asset.type"].search([
                ("category", "=", "node"),
                ("code", "=", "ONT"),
            ], limit=1)
        endpoint_values = {
            "partner_id": customer.id,
            "node_kind": "ont",
            "node_category_id": self._node_category_from_kind("ont").id or False,
            "type_id": node_type.id or False,
            "map_icon": "customer_terminal",
            "address": address,
            "latitude": latitude,
            "longitude": longitude,
            "active": True,
        }
        customer_identifier = False
        if endpoint:
            if self.deployment_plan_id and not endpoint.deployment_plan_id:
                endpoint_values["deployment_plan_id"] = self.deployment_plan_id.id
            endpoint.write(endpoint_values)
        else:
            customer_identifier = self._customer_business_identifier(customer)
            endpoint_values.update({
                "name": customer.display_name,
                "code": f"ID-{customer_identifier}",
                "color": "#16a34a",
                "state": "planned" if self.state == "planned" else "active",
                "deployment_plan_id": self.deployment_plan_id.id or False,
            })
            endpoint = self.create(endpoint_values)

        drop_type = self.env.ref("fiber_gis.type_cable_drop", raise_if_not_found=False)
        if not drop_type:
            drop_type = self.env["fiber.gis.asset.type"].search([
                ("category", "=", "cable"),
                ("code", "=", "CABLE_DROP"),
            ], limit=1)
        if not drop_type:
            raise UserError("No est\u00e1 configurado el tipo GIS Acometida.")
        connected = self.env["fiber.gis.cable"].search([
            "|",
            ("from_node_id", "=", self.id),
            ("to_node_id", "=", self.id),
        ])
        drop_cable = connected.filtered(
            lambda cable: cable.type_id == drop_type
            and endpoint in (cable.from_node_id | cable.to_node_id)
        )[:1]
        if not drop_cable:
            customer_identifier = customer_identifier or self._customer_business_identifier(customer)
            drop_cable = self.env["fiber.gis.cable"].create({
                "name": f"Acometida - {customer.display_name}",
                "code": f"ID-{customer_identifier}",
                "type_id": drop_type.id,
                "from_node_id": self.id,
                "to_node_id": endpoint.id,
                "fiber_count": 1,
                "tube_count": 0,
                "route_kind": "facade",
                "state": "planned" if self.state == "planned" else "active",
                "color": drop_type.color or "#10b981",
                "deployment_plan_id": self.deployment_plan_id.id or False,
            })
        drop_cable.action_generate_fibers()
        drop_fiber = drop_cable.fiber_ids.filtered(lambda fiber: fiber.number == 1)[:1]
        if not drop_fiber:
            raise UserError("No se ha podido generar la fibra de la acometida.")
        return endpoint, drop_cable, drop_fiber

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
