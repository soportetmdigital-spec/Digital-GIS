"""Iconos de mapa subidos por los responsables, además de las formas incluidas en el módulo."""

import re
import unicodedata

from odoo import api, fields, models
from odoo.exceptions import ValidationError

# Las opciones de icono personalizadas se guardan como "custom_<código>" en el campo de selección.
CUSTOM_ICON_PREFIX = "custom_"


def icon_code_from_name(name):
    """Código estable (letras, números y guion bajo) a partir del nombre del icono."""
    text = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:40] or "icono"


class FiberGisMapIcon(models.Model):
    _name = "fiber.gis.map.icon"
    _description = "Icono del mapa"
    _order = "sequence, name, id"

    name = fields.Char(string="Nombre", required=True)
    code = fields.Char(
        string="Código", required=True, copy=False, index=True,
        help="Identificador estable del icono; se genera a partir del nombre.",
    )
    image = fields.Image(
        string="Imagen", required=True, max_width=256, max_height=256,
        help="PNG con fondo transparente o SVG. Se muestra en el mapa con su transparencia, sin color de fondo.",
    )
    sequence = fields.Integer(string="Secuencia", default=10)
    active = fields.Boolean(string="Activo", default=True)

    _code_unique = models.Constraint("UNIQUE(code)", "Ya existe un icono con este código.")

    @api.model
    def _unique_code(self, name, exclude_id=None):
        base = icon_code_from_name(name)
        code, index = base, 2
        domain = [("code", "=", code)] + ([("id", "!=", exclude_id)] if exclude_id else [])
        while self.with_context(active_test=False).search_count(domain):
            code = f"{base}_{index}"
            index += 1
            domain = [("code", "=", code)] + ([("id", "!=", exclude_id)] if exclude_id else [])
        return code

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            values["code"] = self._unique_code(values.get("code") or values.get("name"))
        return super().create(vals_list)

    def write(self, values):
        if "code" in values:
            for icon in self:
                if values["code"] != icon.code and self._icon_in_use(icon):
                    raise ValidationError("No se puede cambiar el código de un icono que ya usan elementos o sitios.")
            values = dict(values, code=icon_code_from_name(values["code"]))
        return super().write(values)

    @api.model
    def _icon_in_use(self, icon):
        value = f"{CUSTOM_ICON_PREFIX}{icon.code}"
        return any(
            self.env[model].with_context(active_test=False).search_count([("map_icon", "=", value)])
            for model in ("fiber.gis.node", "fiber.gis.site", "fiber.gis.node.category")
        )

    @api.ondelete(at_uninstall=False)
    def _unlink_if_unused(self):
        for icon in self:
            if self._icon_in_use(icon):
                raise ValidationError(
                    f"El icono «{icon.name}» está en uso. Archívalo en lugar de borrarlo o cambia antes el icono de esos registros."
                )

    @api.model
    def _selection_options(self):
        """Opciones de selección de los iconos personalizados (también los archivados, para no perder valores)."""
        icons = self.sudo().with_context(active_test=False).search([])
        return [(f"{CUSTOM_ICON_PREFIX}{icon.code}", icon.name) for icon in icons]

    @api.model
    def get_map_icons(self):
        """Iconos personalizados activos con la versión de su imagen, para el mapa y el selector de iconos."""
        return [{
            "value": f"{CUSTOM_ICON_PREFIX}{icon.code}",
            "code": icon.code,
            "name": icon.name,
            "url": f"/fiber_gis/map_icon/{icon.code}?v={int(icon.write_date.timestamp()) if icon.write_date else 0}",
        } for icon in self.search([])]
