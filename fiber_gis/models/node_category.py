"""Modelos de red: funciones admitidas y aspecto inicial de cada equipo."""

from odoo import api, fields, models


NODE_KIND_SELECTION = [
    ("site", "Sitio tecnico"),
    ("olt", "OLT"),
    ("odf", "ODF"),
    ("cabinet", "Armario"),
    ("cto", "CTO"),
    ("box", "Caja terminal"),
    ("closure", "Caja de registro"),
    ("manhole", "Arqueta"),
    ("pole", "Poste"),
    ("splitter", "Splitter"),
    ("rack", "Rack"),
    ("ont", "ONT/CPE"),
    ("other", "Otro"),
]


class FiberGisNodeCategory(models.Model):
    _name = "fiber.gis.node.category"
    _description = "Modelo de elemento de red"
    _order = "sequence, name"

    name = fields.Char(string="Nombre", required=True, translate=True)
    code = fields.Char(string="Codigo", required=True)
    node_kind = fields.Selection(
        NODE_KIND_SELECTION,
        string="Categoria tecnica",
        required=True,
        default="other",
        help="Mantiene la compatibilidad tecnica del mapa, CTO, arquetas y filtros.",
    )
    sequence = fields.Integer(string="Secuencia", default=10)
    active = fields.Boolean(string="Activo", default=True)
    map_icon = fields.Selection(
        selection="_selection_map_icon", string="Icono predeterminado",
    )
    color = fields.Char(string="Color predeterminado")
    function_type_ids = fields.Many2many(
        "fiber.gis.asset.type", "fiber_gis_model_function_rel",
        "node_category_id", "type_id", string="Tipos de funci\u00f3n",
        domain=[("category", "=", "node")],
    )

    @api.model
    def _selection_map_icon(self):
        return self.env["fiber.gis.node"]._fields["map_icon"].selection

    @api.model
    def _initial_style(self, kind):
        node_model = self.env["fiber.gis.node"]
        type_record = self.env["fiber.gis.asset.type"].search([
            ("category", "=", "node"), ("code", "=", kind.upper()),
        ], limit=1)
        return {
            "map_icon": node_model._default_icon_from_kind(kind),
            "color": (
                node_model.CTO_NOT_ILLUMINATED_COLOR if kind == "cto"
                else type_record.color or "#2f80ed"
            ),
        }

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            kind = values.get("node_kind") or self.env.context.get("default_node_kind") or "other"
            for name, value in self._initial_style(kind).items():
                if not values.get(name):
                    values[name] = value
        return super().create(vals_list)

    @api.model
    def _initialize_model_functions(self):
        """Enlaza los datos anteriores sin cambiar el aspecto de ningun equipo."""
        categories = self.with_context(active_test=False).search([])
        node_model = self.env["fiber.gis.node"].with_context(active_test=False)
        for category in categories:
            defaults = self._initial_style(category.node_kind)
            missing = {key: value for key, value in defaults.items() if not category[key]}
            if missing:
                category.write(missing)
        types = self.env["fiber.gis.asset.type"].with_context(active_test=False).search([
            ("category", "=", "node"),
        ])
        for function in types:
            kind = node_model._node_kind_from_type(function)
            compatible = categories.filtered(lambda category: category.node_kind == kind)
            # Conserva tambien las combinaciones personalizadas ya utilizadas.
            compatible |= node_model.search([("type_id", "=", function.id)]).node_category_id
            missing = compatible - function.node_category_ids
            if missing:
                function.write({"node_category_ids": [fields.Command.link(item.id) for item in missing]})

    _code_unique = models.Constraint(
        "UNIQUE(code)",
        "El codigo del modelo debe ser unico.",
    )
