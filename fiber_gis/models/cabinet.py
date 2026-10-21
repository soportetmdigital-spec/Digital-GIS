"""Armarios de comunicaciones y distribucion visual de equipos/fibras."""

import json

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

FIBER_PANEL_KINDS = {"patch_panel", "odf", "odf_96", "fhu_panel_48f"}


def _find_equipment_overlap(items):
    """Devuelve el primer par de equipos solapados en una lista ya cargada."""
    furthest_item = None
    furthest_end = 0
    for item in sorted(items, key=lambda equipment: (equipment.position_u, equipment.id)):
        if furthest_item and item.position_u <= furthest_end:
            return furthest_item, item
        item_end = item.position_u + item.height_u - 1
        if item_end > furthest_end:
            furthest_item, furthest_end = item, item_end
    return None


class FiberGisCabinet(models.Model):
    _name = "fiber.gis.cabinet"
    _description = "Armario de comunicaciones"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(string="Nombre", required=True, tracking=True)
    code = fields.Char(string="Código", tracking=True, index=True)
    node_id = fields.Many2one("fiber.gis.node", string="Elemento GIS", ondelete="set null", tracking=True)
    rack_group_id = fields.Many2one("fiber.gis.cabinet", string="Cabecera de racks", ondelete="cascade", index=True, copy=False)
    site_id = fields.Many2one(related="node_id.site_id", string="Sitio", store=True)
    height_u = fields.Integer(string="Altura (U)", required=True, default=42, tracking=True)
    width_mm = fields.Integer(string="Ancho (mm)", default=600)
    depth_mm = fields.Integer(string="Fondo (mm)", default=800)
    description = fields.Text(string="Notas")
    equipment_ids = fields.One2many("fiber.gis.cabinet.equipment", "cabinet_id", string="Equipos")
    interconnection_ids = fields.One2many("fiber.gis.cabinet.interconnection", "group_cabinet_id", string="Interconexiones")
    equipment_count = fields.Integer(compute="_compute_metrics", string="Equipos")
    occupied_u = fields.Integer(compute="_compute_metrics", string="Unidades ocupadas")
    patch_port_count = fields.Integer(compute="_compute_metrics", string="Puertos de fibra")
    connected_fiber_count = fields.Integer(compute="_compute_metrics", string="Fibras conectadas")
    active = fields.Boolean(default=True)

    _height_u_range = models.Constraint("CHECK(height_u >= 1 AND height_u <= 60)", "La altura debe estar entre 1 y 60 U.")

    @api.constrains("rack_group_id")
    def _check_rack_group(self):
        for rack in self:
            if rack.rack_group_id and (rack.rack_group_id == rack or rack.rack_group_id.rack_group_id):
                raise ValidationError("Los racks secundarios deben depender directamente de una cabecera principal.")

    @api.depends("equipment_ids", "equipment_ids.height_u", "equipment_ids.position_u", "equipment_ids.kind", "equipment_ids.port_ids.fiber_id")
    def _compute_metrics(self):
        for cabinet in self:
            cabinet.equipment_count = len(cabinet.equipment_ids)
            cabinet.occupied_u = sum(cabinet.equipment_ids.mapped("height_u"))
            panels = cabinet.equipment_ids.filtered(lambda item: item.kind in FIBER_PANEL_KINDS)
            cabinet.patch_port_count = sum(panels.mapped("port_count"))
            cabinet.connected_fiber_count = len(panels.mapped("port_ids.fiber_id"))

    @api.constrains("height_u", "equipment_ids", "equipment_ids.position_u", "equipment_ids.height_u")
    def _check_equipment_layout(self):
        for cabinet in self:
            items = cabinet.equipment_ids
            for item in items:
                if item.position_u < 1 or item.position_u + item.height_u - 1 > cabinet.height_u:
                    raise ValidationError(f"{item.display_name}: la posición excede las {cabinet.height_u} U del armario.")
            overlap = _find_equipment_overlap(items)
            if overlap:
                raise ValidationError(f"{overlap[0].display_name} se solapa con {overlap[1].display_name} en el armario.")

    def write(self, values):
        result = super().write(values)
        if "height_u" in values:
            self._check_equipment_layout()
        return result

    @api.model
    def get_cabinet_editor_data(self, cabinet_id):
        self._check_manager()
        cabinet = self.browse(cabinet_id).exists()
        if not cabinet:
            raise UserError("El armario ya no existe.")
        cabinet.ensure_one()
        root = cabinet.rack_group_id or cabinet
        racks = root | self.search([("rack_group_id", "=", root.id)])
        rack_data = []
        for rack in racks.sorted("id"):
            equipment = []
            for item in rack.equipment_ids.sorted("position_u", reverse=True):
                equipment.append({
                    "id": item.id, "rack_id": rack.id, "name": item.name, "kind": item.kind, "kind_label": dict(item._fields["kind"].selection).get(item.kind),
                    "position_u": item.position_u, "height_u": item.height_u, "port_count": item.port_count,
                    "ports": [{"id": port.id, "number": port.number, "fiber_id": port.fiber_id.id or False,
                               "fiber_label": port.fiber_id.display_name if port.fiber_id else "",
                               "fiber_color": port.fiber_id.color or "#7c8da5", "fiber_color_name": port.fiber_id.color_name or ""}
                              for port in item.port_ids.sorted("number")],
                })
            rack_data.append({"id": rack.id, "name": rack.name, "height_u": rack.height_u,
                              "width_mm": rack.width_mm, "depth_mm": rack.depth_mm, "equipment": equipment})
        links = self.env["fiber.gis.cabinet.interconnection"].search([("group_cabinet_id", "=", root.id)])
        connection_data = [{
            "id": link.id, "name": link.name or "", "cable_type": link.cable_type, "color": link.color or "#138da0",
            "from_equipment_id": link.from_equipment_id.id, "from_equipment_name": link.from_equipment_id.name,
            "from_rack_id": link.from_equipment_id.cabinet_id.id, "from_port": link.from_port,
            "to_equipment_id": link.to_equipment_id.id, "to_equipment_name": link.to_equipment_id.name,
            "to_rack_id": link.to_equipment_id.cabinet_id.id, "to_port": link.to_port,
        } for link in links]
        return {"id": root.id, "name": root.name, "height_u": root.height_u,
                "width_mm": root.width_mm, "depth_mm": root.depth_mm, "racks": rack_data,
                "interconnections": connection_data,
                "catalog": self.env["fiber.gis.cabinet.equipment"]._catalog_data()}

    @api.model
    def save_catalog_item(self, cabinet_id, kind, name, height_u, port_count, image_data=False, image_filename="", port_layout=None, reset_image=False):
        self._check_manager()
        cabinet = self.browse(int(cabinet_id)).exists()
        if not cabinet:
            raise UserError("La cabecera ya no existe.")
        kind = str(kind or "")
        defaults = self.env["fiber.gis.cabinet.equipment"]._catalog_defaults().get(kind)
        if not defaults:
            raise ValidationError("El elemento ya no existe en la biblioteca.")
        name = (name or "").strip()
        height_u, port_count = int(height_u), int(port_count)
        if not name or not (1 <= height_u <= 60) or not (0 <= port_count <= 512):
            raise ValidationError("Indica un nombre, una altura entre 1 y 60 U y hasta 512 bocas.")
        if kind in FIBER_PANEL_KINDS and port_count < 1:
            raise ValidationError("Un panel de fibra debe conservar al menos una boca.")
        equipment = self.env["fiber.gis.cabinet.equipment"].search([("kind", "=", kind)])
        links = self.env["fiber.gis.cabinet.interconnection"].search([
            "|", "&", ("from_equipment_id", "in", equipment.ids), ("from_port", ">", port_count),
            "&", ("to_equipment_id", "in", equipment.ids), ("to_port", ">", port_count),
        ])
        if links:
            raise ValidationError("Hay interconexiones en bocas por encima de la cantidad indicada. Muévelas o elimínalas antes de reducir el número.")
        if any(port.number > port_count and port.fiber_id for item in equipment for port in item.port_ids):
            raise ValidationError("Hay fibras asignadas a bocas por encima de la cantidad indicada. Libéralas antes de reducir el número.")
        layout = {}
        for number, point in (port_layout or {}).items():
            number = int(number)
            if number < 1 or number > port_count or not isinstance(point, dict):
                continue
            layout[str(number)] = {
                "x": max(0, min(100, float(point.get("x", 50)))),
                "y": max(0, min(100, float(point.get("y", 50)))),
            }
        Catalog = self.env["fiber.gis.cabinet.catalog"].sudo()
        record = Catalog.search([("kind", "=", kind)], limit=1)
        values = {"name": name, "height_u": height_u, "port_count": port_count,
                  "port_layout_json": json.dumps(layout)}
        if image_data:
            values.update({"image": image_data, "image_filename": image_filename or name})
        elif reset_image:
            values.update({"image": False, "image_filename": False})
        if record:
            record.write(values)
        else:
            record = Catalog.create({"kind": kind, **values})
        if equipment and any(item.port_count != port_count for item in equipment):
            equipment.write({"port_count": port_count})
        return self.get_cabinet_editor_data(cabinet.id)

    def _check_manager(self):
        if not self.env.user.has_group("fiber_gis.group_fiber_gis_manager"):
            raise UserError("Solo los responsables de Fiber GIS pueden editar cabeceras.")

    def action_open_editor(self):
        self.ensure_one()
        self._check_manager()
        return {"type": "ir.actions.client", "tag": "fiber_gis.cabinet_action", "name": f"Cabecera · {self.name}", "params": {"cabinet_id": self.id}}

    def action_create_equipment(self, kind, position_u=None):
        self.ensure_one()
        self._check_manager()
        catalog = self.env["fiber.gis.cabinet.equipment"]._catalog().get(kind)
        if not catalog:
            raise ValidationError("Tipo de equipo no disponible en la biblioteca.")
        height = catalog["height_u"]
        position = int(position_u) if position_u is not None else self._first_free_position(height)
        if position < 1 or position + height - 1 > self.height_u:
            raise ValidationError("El equipo no cabe en esa posición del armario.")
        equipment = self.env["fiber.gis.cabinet.equipment"].create({
            "cabinet_id": self.id, "name": catalog["name"], "kind": kind,
            "position_u": position, "height_u": height, "port_count": catalog["port_count"],
        })
        return self.get_cabinet_editor_data(self.id)

    @api.model
    def add_cabinet_rack(self, cabinet_id):
        self._check_manager()
        cabinet = self.browse(int(cabinet_id)).exists()
        if not cabinet:
            raise UserError("La cabecera ya no existe.")
        root = cabinet.rack_group_id or cabinet
        racks = root | self.search([("rack_group_id", "=", root.id)])
        self.create({"name": f"Rack {len(racks) + 1}", "node_id": root.node_id.id or False,
                     "rack_group_id": root.id, "height_u": root.height_u,
                     "width_mm": root.width_mm, "depth_mm": root.depth_mm})
        return self.get_cabinet_editor_data(root.id)

    @api.model
    def create_interconnection(self, equipment_id, from_port, target_equipment_id, to_port, name="", cable_type="ethernet", color="#138da0"):
        self._check_manager()
        source = self.env["fiber.gis.cabinet.equipment"].browse(int(equipment_id)).exists()
        target = self.env["fiber.gis.cabinet.equipment"].browse(int(target_equipment_id)).exists()
        if not source or not target:
            raise UserError("Selecciona los dos equipos de la interconexión.")
        root = source.cabinet_id.rack_group_id or source.cabinet_id
        target_root = target.cabinet_id.rack_group_id or target.cabinet_id
        if root != target_root:
            raise ValidationError("Los dos equipos deben pertenecer a la misma cabecera de racks.")
        self.env["fiber.gis.cabinet.interconnection"].create({
            "group_cabinet_id": root.id, "from_equipment_id": source.id, "from_port": int(from_port),
            "to_equipment_id": target.id, "to_port": int(to_port), "name": (name or "").strip(),
            "cable_type": cable_type, "color": color or "#138da0",
        })
        return self.get_cabinet_editor_data(root.id)

    @api.model
    def delete_interconnection(self, interconnection_id):
        self._check_manager()
        link = self.env["fiber.gis.cabinet.interconnection"].browse(int(interconnection_id)).exists()
        if not link:
            return True
        root = link.group_cabinet_id
        link.unlink()
        return self.get_cabinet_editor_data(root.id)

    def _first_free_position(self, height):
        occupied = set()
        for item in self.equipment_ids:
            occupied.update(range(item.position_u, item.position_u + item.height_u))
        for position in range(1, self.height_u - height + 2):
            if all(unit not in occupied for unit in range(position, position + height)):
                return position
        raise ValidationError("No hay espacio libre para este equipo. Retira o mueve otro componente.")

    @api.model
    def move_equipment(self, equipment_id, position_u):
        equipment = self.env["fiber.gis.cabinet.equipment"].browse(int(equipment_id)).exists()
        if not equipment:
            raise UserError("El equipo ya no existe.")
        equipment.cabinet_id._check_manager()
        equipment.position_u = int(position_u)
        return self.get_cabinet_editor_data(equipment.cabinet_id.id)

    @api.model
    def move_equipment_to_rack(self, equipment_id, rack_id, position_u):
        equipment = self.env["fiber.gis.cabinet.equipment"].browse(int(equipment_id)).exists()
        rack = self.browse(int(rack_id)).exists()
        if not equipment or not rack:
            raise UserError("No se encontró el equipo o el rack de destino.")
        source_root = equipment.cabinet_id.rack_group_id or equipment.cabinet_id
        target_root = rack.rack_group_id or rack
        source_root._check_manager()
        if source_root != target_root:
            raise ValidationError("Solo se pueden mover equipos entre racks de la misma cabecera.")
        position = int(position_u)
        if position < 1 or position + equipment.height_u - 1 > rack.height_u:
            raise ValidationError("El equipo no cabe en esa posición del rack de destino.")
        equipment.write({"cabinet_id": rack.id, "position_u": position})
        equipment.port_ids.write({"cabinet_id": rack.id})
        return self.get_cabinet_editor_data(source_root.id)

    @api.model
    def delete_equipment(self, equipment_id):
        equipment = self.env["fiber.gis.cabinet.equipment"].browse(int(equipment_id)).exists()
        if not equipment:
            return True
        equipment.cabinet_id._check_manager()
        cabinet_id = equipment.cabinet_id.id
        equipment.unlink()
        return self.get_cabinet_editor_data(cabinet_id)

    @api.model
    def rename_equipment(self, equipment_id, name):
        equipment = self.env["fiber.gis.cabinet.equipment"].browse(int(equipment_id)).exists()
        if not equipment:
            raise UserError("El equipo ya no existe.")
        equipment.cabinet_id._check_manager()
        name = (name or "").strip()
        if not name:
            raise ValidationError("El nombre del equipo no puede quedar vacío.")
        equipment.name = name
        return self.get_cabinet_editor_data(equipment.cabinet_id.id)

    @api.model
    def assign_patch_fiber(self, port_id, fiber_id=False):
        port = self.env["fiber.gis.cabinet.port"].browse(int(port_id)).exists()
        if not port:
            raise UserError("El puerto ya no existe.")
        port.cabinet_id._check_manager()
        port.write({"fiber_id": int(fiber_id) if fiber_id else False})
        return self.get_cabinet_editor_data(port.cabinet_id.id)


class FiberGisCabinetCatalog(models.Model):
    _name = "fiber.gis.cabinet.catalog"
    _description = "Biblioteca de equipos de armario"
    _order = "kind"

    kind = fields.Char(required=True, index=True)
    name = fields.Char(required=True)
    height_u = fields.Integer(required=True, default=1)
    port_count = fields.Integer(default=0)
    image = fields.Image(max_width=2400, max_height=1600)
    image_filename = fields.Char()
    port_layout_json = fields.Text(default="{}")

    _kind_unique = models.Constraint("UNIQUE(kind)", "Cada tipo de equipo solo puede aparecer una vez en la biblioteca.")

    @api.constrains("name", "height_u", "port_count")
    def _check_catalog_dimensions(self):
        for item in self:
            if not item.name.strip() or not (1 <= item.height_u <= 60) or not (0 <= item.port_count <= 512):
                raise ValidationError("La biblioteca requiere nombre, altura entre 1 y 60 U y hasta 512 bocas.")

    @api.model
    def _sync_defaults(self):
        defaults = self.env["fiber.gis.cabinet.equipment"]._catalog_defaults()
        existing = set(self.sudo().search([]).mapped("kind"))
        self.sudo().create([
            {"kind": kind, "name": values["name"], "height_u": values["height_u"],
             "port_count": values["port_count"]}
            for kind, values in defaults.items() if kind not in existing
        ])


class FiberGisCabinetEquipment(models.Model):
    _name = "fiber.gis.cabinet.equipment"
    _description = "Equipo de armario de comunicaciones"
    _order = "cabinet_id, position_u desc, id"

    cabinet_id = fields.Many2one("fiber.gis.cabinet", required=True, ondelete="cascade", index=True)
    name = fields.Char(required=True)
    kind = fields.Selection([
        ("patch_panel", "Patch panel de fibra"), ("odf", "ODF / cabecera de fibra"),
        ("fhu_panel_48f", "Panel FHU 1U 48F SC/UPC"),
        ("odf_96", "ODF alta densidad"), ("switch_48", "Switch distribución 48 puertos"),
        ("mikrotik_crs326", "MikroTik CRS326-24G-2S+RM"),
        ("zyxel_gs1920", "Zyxel GS1920-24HPv2"),
        ("firewall", "Firewall"), ("server", "Servidor"), ("nas", "Almacenamiento NAS"),
        ("server_1u", "Servidor rack 1U"), ("server_3u", "Servidor rack 3U"),
        ("raid_2u", "Cabina RAID 2U"), ("raid_3u", "Cabina RAID 3U"),
        ("kvm_switch", "Conmutador KVM 1U"), ("monitor_7u", "Monitor rack 7U"),
        ("monitor_8u", "Monitor rack 8U"), ("ups_managed", "SAI gestionable 2U"),
        ("power_strip", "Regleta de alimentación 1U"),
        ("switch", "Switch acceso 24 puertos"), ("router", "Router"), ("olt", "OLT"),
        ("shelf", "Bandeja fija"), ("shelf_sliding", "Bandeja extraíble"),
        ("cable_manager", "Organizador de cables"), ("pdu", "Regleta PDU"),
        ("fan_panel", "Panel de ventilación"), ("ups", "SAI / UPS"), ("blank", "Panel ciego"),
    ], required=True)
    position_u = fields.Integer(string="Unidad U (desde abajo)", required=True, default=1)
    height_u = fields.Integer(string="Alto (U)", required=True, default=1)
    port_count = fields.Integer(string="Puertos", default=0)
    notes = fields.Char(string="Notas")
    port_ids = fields.One2many("fiber.gis.cabinet.port", "equipment_id", string="Puertos")

    @api.model
    def _catalog_defaults(self):
        return {
            "patch_panel": {"name": "Patch panel fibra 24F", "height_u": 1, "port_count": 24},
            "fhu_panel_48f": {"name": "Panel FHU 1U 48F SC/UPC", "height_u": 1, "port_count": 24},
            "odf": {"name": "ODF modular 48F", "height_u": 2, "port_count": 48},
            "odf_96": {"name": "ODF alta densidad 96F", "height_u": 4, "port_count": 96},
            "switch": {"name": "Switch acceso 24 puertos", "height_u": 1, "port_count": 24},
            "switch_48": {"name": "Switch distribución 48 puertos", "height_u": 1, "port_count": 48},
            "mikrotik_crs326": {"name": "MikroTik CRS326-24G-2S+RM", "height_u": 1, "port_count": 24},
            "zyxel_gs1920": {"name": "Zyxel GS1920-24HPv2", "height_u": 1, "port_count": 24},
            "router": {"name": "Router de borde", "height_u": 1, "port_count": 8},
            "firewall": {"name": "Firewall / seguridad", "height_u": 1, "port_count": 8},
            "olt": {"name": "OLT GPON 16 puertos", "height_u": 2, "port_count": 16},
            "server": {"name": "Servidor rack 2U", "height_u": 2, "port_count": 2},
            "nas": {"name": "Almacenamiento NAS 2U", "height_u": 2, "port_count": 4},
            "server_1u": {"name": "Servidor rack 1U", "height_u": 1, "port_count": 2},
            "server_3u": {"name": "Servidor rack 3U", "height_u": 3, "port_count": 2},
            "raid_2u": {"name": "Cabina RAID 2U", "height_u": 2, "port_count": 0},
            "raid_3u": {"name": "Cabina RAID 3U", "height_u": 3, "port_count": 0},
            "kvm_switch": {"name": "Conmutador KVM 1U", "height_u": 1, "port_count": 0},
            "monitor_7u": {"name": "Monitor rack 7U", "height_u": 7, "port_count": 0},
            "monitor_8u": {"name": "Monitor rack 8U", "height_u": 8, "port_count": 0},
            "ups_managed": {"name": "SAI gestionable 2U", "height_u": 2, "port_count": 0},
            "power_strip": {"name": "Regleta de alimentación 1U", "height_u": 1, "port_count": 0},
            "shelf": {"name": "Bandeja fija", "height_u": 1, "port_count": 0},
            "shelf_sliding": {"name": "Bandeja extraíble", "height_u": 2, "port_count": 0},
            "cable_manager": {"name": "Organizador horizontal", "height_u": 1, "port_count": 0},
            "pdu": {"name": "Regleta PDU", "height_u": 1, "port_count": 0},
            "fan_panel": {"name": "Panel de ventilación", "height_u": 1, "port_count": 0},
            "ups": {"name": "SAI / UPS rack", "height_u": 2, "port_count": 0},
            "blank": {"name": "Panel ciego", "height_u": 1, "port_count": 0},
        }

    @api.model
    def _catalog(self):
        result = self._catalog_defaults()
        for item in self.env["fiber.gis.cabinet.catalog"].sudo().search([]):
            result[item.kind] = {"name": item.name, "height_u": item.height_u,
                                 "port_count": item.port_count}
        return result

    @api.model
    def _catalog_data(self):
        records = {item.kind: item for item in self.env["fiber.gis.cabinet.catalog"].sudo().search([])}
        result = []
        for kind, values in self._catalog().items():
            record = records.get(kind)
            try:
                layout = json.loads(record.port_layout_json or "{}") if record else {}
            except (TypeError, ValueError):
                layout = {}
            result.append({"kind": kind, **values,
                           "image_url": f"/web/image/fiber.gis.cabinet.catalog/{record.id}/image?unique={record.write_date.strftime('%Y%m%d%H%M%S%f')}" if record and record.image else "",
                           "port_layout": layout})
        return result

    @api.model_create_multi
    def create(self, vals_list):
        catalog = self._catalog()
        normalized = []
        for raw_values in vals_list:
            values = dict(raw_values)
            defaults = catalog.get(values.get("kind"), {})
            for field_name in ("height_u", "port_count"):
                if values.get(field_name) in (None, False, 0) and field_name in defaults:
                    values[field_name] = defaults[field_name]
            normalized.append(values)
        records = super().create(normalized)
        for equipment in records:
            if equipment.kind in FIBER_PANEL_KINDS:
                equipment._sync_ports()
        return records

    def write(self, values):
        values = dict(values)
        if "kind" in values:
            defaults = self._catalog().get(values["kind"], {})
            if values.get("height_u") in (None, False, 0):
                values["height_u"] = defaults.get("height_u", 1)
            if values.get("port_count") in (None, False, 0):
                values["port_count"] = defaults.get("port_count", 0)
        result = super().write(values)
        if {"kind", "port_count"}.intersection(values):
            for equipment in self:
                equipment._sync_ports()
        return result

    def _sync_ports(self):
        self.ensure_one()
        ports = self.port_ids
        if self.kind not in FIBER_PANEL_KINDS:
            if ports.filtered("fiber_id"):
                raise ValidationError("No se puede cambiar el tipo mientras haya fibras conectadas al panel.")
            ports.unlink()
            return
        excess = ports.filtered(lambda port: port.number > self.port_count)
        if excess.filtered("fiber_id"):
            raise ValidationError("Desconecta primero las fibras de los puertos que quedarían fuera del panel.")
        excess.unlink()
        existing_numbers = set(ports.filtered(lambda port: port.number <= self.port_count).mapped("number"))
        self.env["fiber.gis.cabinet.port"].create([
            {"cabinet_id": self.cabinet_id.id, "equipment_id": self.id, "number": number}
            for number in range(1, self.port_count + 1) if number not in existing_numbers
        ])

    @api.constrains("position_u", "height_u", "port_count", "kind")
    def _check_dimensions(self):
        for item in self:
            if item.position_u < 1 or item.height_u < 1 or item.height_u > 60 or item.port_count < 0 or item.port_count > 512:
                raise ValidationError("La posición, altura o cantidad de puertos del equipo no es válida.")
            if item.kind in FIBER_PANEL_KINDS and item.port_count < 1:
                raise ValidationError("Un panel de fibra debe tener al menos un puerto.")

    @api.constrains("cabinet_id", "position_u", "height_u")
    def _check_position_and_overlap(self):
        cabinet_ids = set(self.mapped("cabinet_id").ids)
        for cabinet in self.env["fiber.gis.cabinet"].browse(cabinet_ids):
            items = self.search([("cabinet_id", "=", cabinet.id)], order="position_u, id")
            for item in items:
                if item.position_u + item.height_u - 1 > cabinet.height_u:
                    raise ValidationError(f"{item.display_name}: la posición excede las {cabinet.height_u} U del armario.")
            overlap = _find_equipment_overlap(items)
            if overlap:
                raise ValidationError(f"{overlap[0].display_name} se solapa con {overlap[1].display_name} en el armario.")


class FiberGisCabinetPort(models.Model):
    _name = "fiber.gis.cabinet.port"
    _description = "Puerto de patch panel de cabecera"
    _order = "equipment_id, number"

    cabinet_id = fields.Many2one("fiber.gis.cabinet", required=True, ondelete="cascade", index=True)
    equipment_id = fields.Many2one("fiber.gis.cabinet.equipment", required=True, ondelete="cascade", index=True)
    number = fields.Integer(required=True)
    fiber_id = fields.Many2one("fiber.gis.cable.fiber", string="Fibra", ondelete="set null", index=True)
    _number_unique = models.Constraint("UNIQUE(equipment_id, number)", "El número de puerto debe ser único en el panel.")
    _fiber_unique = models.Constraint("UNIQUE(fiber_id)", "Esta fibra ya está asignada a otro puerto de cabecera.")

    @api.constrains("equipment_id", "cabinet_id", "number", "fiber_id")
    def _check_assignment(self):
        for port in self:
            if port.equipment_id.cabinet_id != port.cabinet_id:
                raise ValidationError("El puerto debe pertenecer al mismo armario que el equipo.")
            if port.equipment_id.kind not in FIBER_PANEL_KINDS or not (1 <= port.number <= port.equipment_id.port_count):
                raise ValidationError("El puerto no corresponde a un panel de fibra válido.")
            if port.fiber_id:
                duplicate = self.search_count([("fiber_id", "=", port.fiber_id.id), ("id", "!=", port.id)])
                if duplicate:
                    raise ValidationError("Esta fibra ya está asignada a otro puerto de cabecera.")


class FiberGisCabinetInterconnection(models.Model):
    _name = "fiber.gis.cabinet.interconnection"
    _description = "Cableado de interconexión de una cabecera"
    _order = "group_cabinet_id, id"

    group_cabinet_id = fields.Many2one("fiber.gis.cabinet", required=True, ondelete="cascade", index=True)
    from_equipment_id = fields.Many2one("fiber.gis.cabinet.equipment", required=True, ondelete="cascade", index=True)
    from_port = fields.Integer(string="Puerto de origen", required=True)
    to_equipment_id = fields.Many2one("fiber.gis.cabinet.equipment", required=True, ondelete="cascade", index=True)
    to_port = fields.Integer(string="Puerto de destino", required=True)
    name = fields.Char(string="Identificación del cable")
    cable_type = fields.Selection([
        ("ethernet", "Ethernet / cobre"), ("fiber", "Fibra óptica"),
        ("dac", "DAC / twinaxial"), ("other", "Otro"),
    ], required=True, default="ethernet")
    color = fields.Char(string="Color de visualización", default="#138da0")

    @api.constrains("group_cabinet_id", "from_equipment_id", "from_port", "to_equipment_id", "to_port")
    def _check_endpoints(self):
        for link in self:
            source, target = link.from_equipment_id, link.to_equipment_id
            source_root = source.cabinet_id.rack_group_id or source.cabinet_id
            target_root = target.cabinet_id.rack_group_id or target.cabinet_id
            if source == target or source_root != target_root or source_root != link.group_cabinet_id:
                raise ValidationError("La interconexión debe unir dos equipos distintos de la misma cabecera de racks.")
            if not (1 <= link.from_port <= source.port_count and 1 <= link.to_port <= target.port_count):
                raise ValidationError("Los números de puerto deben estar dentro de los puertos de ambos equipos.")
            existing_links = self.search([("id", "!=", link.id), ("group_cabinet_id", "=", link.group_cabinet_id.id)])
            for existing in existing_links:
                occupied_ports = ((existing.from_equipment_id, existing.from_port), (existing.to_equipment_id, existing.to_port))
                if (source, link.from_port) in occupied_ports or (target, link.to_port) in occupied_ports:
                    raise ValidationError("Uno de estos puertos ya tiene una interconexión registrada.")


class FiberGisCableFiberCabinet(models.Model):
    _inherit = "fiber.gis.cable.fiber"

    @api.model
    def search_cabinet_fibers(self, cabinet_id, query):
        self.env["fiber.gis.cabinet"]._check_manager()
        cabinet = self.env["fiber.gis.cabinet"].browse(int(cabinet_id)).exists()
        if not cabinet:
            raise UserError("El armario ya no existe.")
        text = (query or "").strip()
        if len(text) < 2 or not cabinet.node_id:
            return {"fibers": [], "truncated": False}
        occupied_ids = self.env["fiber.gis.cabinet.port"].search([("fiber_id", "!=", False)]).mapped("fiber_id").ids
        endpoint_domain = ["|", ("cable_id.from_node_id", "=", cabinet.node_id.id), ("cable_id.to_node_id", "=", cabinet.node_id.id)]
        search_terms = [
            ("name", "ilike", text), ("cable_id.name", "ilike", text), ("cable_id.code", "ilike", text),
            ("cable_id.from_node_id.name", "ilike", text), ("cable_id.to_node_id.name", "ilike", text),
            ("color_name", "ilike", text),
        ]
        if text.isdigit():
            search_terms.append(("number", "=", int(text)))
        query_domain = ["|"] * (len(search_terms) - 1) + search_terms
        domain = endpoint_domain + [("id", "not in", occupied_ids)] + query_domain
        fibers = self.search(domain, limit=51)
        truncated = len(fibers) > 50
        return {
            "fibers": [{"id": fiber.id, "label": fiber.display_name, "cable": fiber.cable_id.display_name,
                        "number": fiber.number, "tube": fiber.tube, "color": fiber.color or "#7c8da5",
                        "color_name": fiber.color_name or "", "from_node": fiber.from_node_id.display_name or "",
                        "to_node": fiber.to_node_id.display_name or ""} for fiber in fibers[:50]],
            "truncated": truncated,
        }

