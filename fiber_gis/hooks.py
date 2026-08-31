"""Hooks de instalacion de Fiber GIS."""

ASSET_TYPES = [
    ("type_node_olt", {"name": "OLT", "code": "OLT", "category": "node", "sequence": 10, "color": "#2563eb"}),
    ("type_node_odf", {"name": "ODF", "code": "ODF", "category": "node", "sequence": 20, "color": "#7c3aed"}),
    ("type_node_box", {"name": "Caja terminal", "code": "BOX", "category": "node", "sequence": 30, "color": "#059669"}),
    ("type_node_cto", {"name": "CTO", "code": "CTO", "category": "node", "sequence": 35, "color": "#e11d48"}),
    ("type_node_closure", {"name": "Caja de registro", "code": "CLOSURE", "category": "node", "sequence": 40, "color": "#d97706"}),
    ("type_node_cabinet", {"name": "Armario", "code": "CABINET", "category": "node", "sequence": 45, "color": "#64748b"}),
    ("type_node_manhole", {"name": "Arqueta", "code": "MANHOLE", "category": "node", "sequence": 50, "color": "#475569"}),
    ("type_node_pole", {"name": "Poste", "code": "POLE", "category": "node", "sequence": 60, "color": "#92400e"}),
    ("type_node_splitter", {"name": "Splitter", "code": "SPLITTER", "category": "node", "sequence": 70, "color": "#0891b2"}),
    ("type_node_rack", {"name": "Rack", "code": "RACK", "category": "node", "sequence": 80, "color": "#4338ca"}),
    ("type_node_ont", {"name": "ONT/CPE", "code": "ONT", "category": "node", "sequence": 90, "color": "#0f766e"}),
    ("type_node_site", {"name": "Sitio tecnico", "code": "SITE", "category": "node", "sequence": 100, "color": "#334155"}),
    ("type_cable_backbone", {"name": "Cable troncal", "code": "CABLE_BACKBONE", "category": "cable", "sequence": 10, "color": "#ef4444"}),
    ("type_cable_distribution", {"name": "Cable de distribucion", "code": "CABLE_DISTRIBUTION", "category": "cable", "sequence": 20, "color": "#f59e0b"}),
    ("type_cable_drop", {"name": "Acometida", "code": "CABLE_DROP", "category": "cable", "sequence": 30, "color": "#10b981"}),
]

NODE_CATEGORIES = [
    ("node_category_site", {"name": "Sitio tecnico", "code": "SITE", "node_kind": "site", "sequence": 10}),
    ("node_category_olt", {"name": "OLT", "code": "OLT", "node_kind": "olt", "sequence": 20}),
    ("node_category_odf", {"name": "ODF", "code": "ODF", "node_kind": "odf", "sequence": 30}),
    ("node_category_cabinet", {"name": "Armario", "code": "CABINET", "node_kind": "cabinet", "sequence": 40}),
    ("node_category_cto", {"name": "CTO", "code": "CTO", "node_kind": "cto", "sequence": 50}),
    ("node_category_box", {"name": "Caja terminal", "code": "BOX", "node_kind": "box", "sequence": 60}),
    ("node_category_closure", {"name": "Caja de registro", "code": "CLOSURE", "node_kind": "closure", "sequence": 70}),
    ("node_category_manhole", {"name": "Arqueta", "code": "MANHOLE", "node_kind": "manhole", "sequence": 80}),
    ("node_category_pole", {"name": "Poste", "code": "POLE", "node_kind": "pole", "sequence": 90}),
    ("node_category_splitter", {"name": "Splitter", "code": "SPLITTER", "node_kind": "splitter", "sequence": 100}),
    ("node_category_rack", {"name": "Rack", "code": "RACK", "node_kind": "rack", "sequence": 110}),
    ("node_category_ont", {"name": "ONT/CPE", "code": "ONT", "node_kind": "ont", "sequence": 120}),
    ("node_category_other", {"name": "Otro", "code": "OTHER", "node_kind": "other", "sequence": 999}),
]


def post_init_hook(env):
    _upsert_by_code(env, "fiber.gis.asset.type", ASSET_TYPES)
    _upsert_by_code(env, "fiber.gis.node.category", NODE_CATEGORIES)
    env["fiber.gis.node.category"]._initialize_model_functions()


def _upsert_by_code(env, model_name, rows):
    record_model = env[model_name].sudo().with_context(active_test=False)
    xmlid_model = env["ir.model.data"].sudo()
    module = "fiber_gis"

    for xml_name, values in rows:
        record = record_model.search([("code", "=", values["code"])], limit=1)
        if record:
            record.write(values)
        else:
            record = record_model.create(values)

        xmlid = xmlid_model.search([
            ("module", "=", module),
            ("name", "=", xml_name),
        ], limit=1)
        xml_values = {
            "module": module,
            "name": xml_name,
            "model": model_name,
            "res_id": record.id,
            "noupdate": True,
        }
        if xmlid:
            xmlid.write(xml_values)
        else:
            xmlid_model.create(xml_values)
