"""Static check that Cabinet actions load before menus that reference them."""

import ast
from pathlib import Path

from lxml import etree


ROOT = Path(__file__).resolve().parents[1]
manifest = ast.literal_eval((ROOT / "__manifest__.py").read_text(encoding="utf-8"))
data_files = manifest["data"]
action_file = "views/fiber_gis_cabinet_views.xml"
menu_file = "views/fiber_gis_menus.xml"
assert data_files.index(action_file) < data_files.index(menu_file), (
    "The cabinet action must load before the menu that references it."
)

action_tree = etree.parse(str(ROOT / action_file))
action_ids = set(action_tree.xpath("//record[@model='ir.actions.act_window']/@id"))
menu_tree = etree.parse(str(ROOT / menu_file))
referenced_actions = set(menu_tree.xpath("//menuitem[@id='menu_fiber_gis_cabinets']/@action"))
assert referenced_actions == {"action_fiber_gis_cabinets"}
assert referenced_actions.issubset(action_ids), "Cabinet menu references an undeclared action."
print("Cabinet action/menu load order OK")
