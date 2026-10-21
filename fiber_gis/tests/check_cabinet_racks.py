"""Static release checks for the rack grouping and interconnection editor."""

import ast
from pathlib import Path

from lxml import etree


ROOT = Path(__file__).resolve().parents[1]
manifest = ast.literal_eval((ROOT / "__manifest__.py").read_text(encoding="utf-8"))
assert manifest["version"] == "19.0.4.25"

cabinet_source = (ROOT / "models/cabinet.py").read_text(encoding="utf-8")
for method in ("add_cabinet_rack", "move_equipment_to_rack", "create_interconnection", "delete_interconnection", "save_catalog_item"):
    assert f"def {method}(" in cabinet_source, f"Missing cabinet method: {method}"
assert '"fiber.gis.cabinet.interconnection"' in cabinet_source

template = etree.parse(str(ROOT / "static/src/xml/fiber_cabinet.xml"))
scss = (ROOT / "static/src/scss/fiber_cabinet.scss").read_text(encoding="utf-8")
assert "width: min(" not in scss and "height: min(" not in scss, "Avoid Sass min() with mixed CSS units in Odoo asset SCSS"
assert "aspect-ratio:" not in scss, "Keep catalog preview sizing on an explicit height for legacy Sass compatibility"
assert ".o_fiber_cabinet_catalog_modal {" in scss and "position: fixed" in scss
assert template.xpath("//*[@aria-label='Ampliar o reducir la vista del rack']")
assert template.xpath("//*[@t-on-click='addRack']")
assert template.xpath("//*[@t-on-click='createInterconnection']")
assert template.xpath("//*[@t-on-click and contains(@t-on-click, 'onVisualPortClick')]")
assert template.xpath("//*[@*[name()='t-on-click.stop' and contains(., 'openCatalogEditor')]]")
assert template.xpath("//*[@t-on-click and contains(@t-on-click, 'saveCatalogEditor')]")
assert template.xpath("//*[@t-on-pointerdown and contains(@t-on-pointerdown, 'startCatalogPortDrag')]")
assert template.xpath("//canvas[@class='o_fiber_cabinet_connection_layer']")
assert template.xpath("//*[@class='o_fiber_cabinet_catalog_modal' and @role='dialog']")
assert template.xpath("//*[@t-att-class and contains(@t-att-class, 'o_fiber_cabinet_port_hotspot')]")
assert "equipmentPorts(item)" in (ROOT / "static/src/js/fiber_cabinet.js").read_text(encoding="utf-8")
assert "isInterconnectionPortOccupied" in (ROOT / "static/src/js/fiber_cabinet.js").read_text(encoding="utf-8")
views = etree.parse(str(ROOT / "views/fiber_gis_cabinet_views.xml"))
assert views.xpath("//record[@id='action_fiber_gis_cabinets']/field[@name='domain' and contains(text(), 'rack_group_id')]")

photo = ROOT / "static/src/img/fs_fhu_panel_48f_sc_upc.webp"
assert photo.is_file() and photo.stat().st_size > 10_000
attribution = (ROOT / "static/src/img/ATTRIBUTION.txt").read_text(encoding="utf-8")
assert "SKU 35529" in attribution and "fs.com/es/products/35529.html" in attribution
print("Cabinet zoom, rack grouping, modal catalogue editor, cable canvas and product image OK")
