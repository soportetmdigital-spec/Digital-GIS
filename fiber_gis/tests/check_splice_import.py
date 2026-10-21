"""Comprueba el cotejo de matrículas del importador sin depender de una instancia Odoo."""

import ast
from pathlib import Path
import xml.etree.ElementTree as ET
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "models" / "splice_document.py"
TREE = ast.parse(SOURCE.read_text(encoding="utf-8"))
FUNCTION = next(
    node for node in TREE.body
    if isinstance(node, ast.FunctionDef) and node.name == "match_splice_node"
)
NAMESPACE = {}
exec(compile(ast.Module(body=[FUNCTION], type_ignores=[]), str(SOURCE), "exec"), NAMESPACE)
match_splice_node = NAMESPACE["match_splice_node"]


class TestSpliceImportMatching(unittest.TestCase):
    def test_matches_exact_code_at_start_or_between_separators(self):
        nodes = [(1, "CTO-12"), (2, "CTO-123")]
        self.assertEqual(match_splice_node("CTO-12", nodes), (1, "matched"))
        self.assertEqual(match_splice_node("Carta CTO-12 2026", nodes), (1, "matched"))
        self.assertEqual(match_splice_node("Carta_CTO-123.xlsx", nodes), (2, "matched"))

    def test_does_not_accept_partial_code_collisions(self):
        self.assertEqual(match_splice_node("CTO-1234", [(1, "CTO-12")]), (False, "unmatched"))
        self.assertEqual(match_splice_node("Carta X-CTO-12A", [(1, "CTO-12")]), (False, "unmatched"))

    def test_reports_duplicate_codes_and_multiple_distinct_codes_as_ambiguous(self):
        self.assertEqual(match_splice_node("CTO-12", [(1, "CTO-12"), (2, "CTO-12")]), (False, "ambiguous"))
        self.assertEqual(
            match_splice_node("Empalme CTO-12 y CTO-123", [(1, "CTO-12"), (2, "CTO-123")]),
            (False, "ambiguous"),
        )

    def test_duplicate_code_and_name_alias_for_same_node_is_not_ambiguous(self):
        self.assertEqual(match_splice_node("A5-002", [(7, "A5-002"), (7, "Caja A5-002")]), (7, "matched"))

    def test_splice_tab_is_limited_to_elements_with_trays(self):
        view = ET.parse(ROOT / "views" / "fiber_gis_node_views.xml").getroot()
        page = view.find(".//page[@name='splice_cards']")
        self.assertIsNotNone(page)
        self.assertEqual(page.get("string"), "Cartas de Empalme")
        self.assertIn("not has_trays", page.get("invisible", ""))
        self.assertIn("node_kind == 'ont'", page.get("invisible", ""))
        field_names = {field.get("name") for field in page.findall(".//field")}
        self.assertTrue({"splice_photo_ids", "splice_card_ids", "image_1920", "file_data", "comment"} <= field_names)
        upload_button = page.find(".//button[@name='action_open_splice_upload']")
        self.assertIsNotNone(upload_button)
        self.assertEqual(upload_button.get("string"), "Subir carta Excel")
        self.assertIsNone(page.find(".//button[@name='action_open_splice_import_wizard']"))
        layout = page.find("./group")
        self.assertIsNotNone(layout)
        self.assertEqual(layout.get("col"), "1")
        section_titles = [group.get("string") for group in layout.findall("./group")]
        self.assertEqual(section_titles, ["Cartas Excel", "Fotos"])
        excel_field = page.find(".//field[@name='splice_card_ids']")
        self.assertEqual(excel_field.get("nolabel"), "1")
        excel_fields = {field.get("name") for field in excel_field.findall(".//field")}
        self.assertIn("technician_comment", excel_fields)

    def test_bulk_import_is_a_configuration_menu(self):
        views = ET.parse(ROOT / "views" / "fiber_gis_splice_document_views.xml").getroot()
        menu = views.find(".//menuitem[@id='menu_fiber_gis_splice_import']")
        self.assertIsNotNone(menu)
        self.assertEqual(menu.get("parent"), "fiber_gis.menu_fiber_gis_config")
        self.assertEqual(menu.get("action"), "action_fiber_gis_splice_import")
        report_fields = (ROOT / "views" / "fiber_gis_splice_document_views.xml").read_text(encoding="utf-8")
        importer = SOURCE.read_text(encoding="utf-8")
        self.assertIn('name="skipped_report" filename="skipped_report_name"', report_fields)
        self.assertIn('"archivos_no_importados.txt"', importer)
        self.assertIn('duplicate_items.append((entry.filename, "Duplicado; omitido"))', importer)

    def test_duplicate_import_menu_cleanup_is_one_time(self):
        migration = ROOT / "migrations" / "19.0.3.55" / "post-migrate.py"
        self.assertTrue(migration.exists())
        source = migration.read_text(encoding="utf-8")
        self.assertIn("menu_fiber_gis_splice_import", source)
        self.assertIn("duplicates.unlink()", source)

    def test_splice_menu_external_id_is_not_deleted_on_each_module_update(self):
        cleanup = ET.parse(ROOT / "data" / "fiber_gis_cleanup.xml").getroot()
        removed_external_ids = [
            item for item in cleanup.findall("delete")
            if item.get("model") == "ir.model.data"
        ]
        self.assertFalse(removed_external_ids, "La limpieza no debe borrar IDs XML del menú canónico")
        migration = ROOT / "migrations" / "19.0.4.20" / "post-migrate.py"
        source = migration.read_text(encoding="utf-8")
        self.assertIn('env.ref("fiber_gis.menu_fiber_gis_splice_import"', source)
        self.assertIn('("id", "!=", canonical.id)', source)
        self.assertIn("duplicates.unlink()", source)

    def test_pending_cancel_is_colored_and_unlimited(self):
        wizard = (ROOT / "models" / "cable_tray_wizard.py").read_text(encoding="utf-8")
        tray = (ROOT / "models" / "tray.py").read_text(encoding="utf-8")
        styles = (ROOT / "static" / "src" / "scss" / "fiber_map.scss").read_text(encoding="utf-8")
        self.assertIn('("pending_cancel", "Fibra pendiente de anular")', wizard)
        self.assertIn('("free", "pending_cancel")', tray)
        self.assertIn(".o_fiber_tray_line.is-pending-cancel", styles)
        self.assertIn(".o_fiber_color_checkbox.is-pending-cancel", styles)

    def test_importer_accepts_libreoffice_and_large_archives(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn('".xlsb", ".ods"', source)
        self.assertIn("len(entries) > 5000", source)
        self.assertIn('("name", "!=", False)', source)
        self.assertIn("no tiene bandejas activadas", source)

    def test_tray_default_is_owned_by_equipment_model_and_migrated(self):
        category_model = (ROOT / "models" / "node_category.py").read_text(encoding="utf-8")
        node_model = (ROOT / "models" / "node.py").read_text(encoding="utf-8")
        defaults = (ROOT / "data" / "fiber_gis_node_category_data.xml").read_text(encoding="utf-8")
        migration = (ROOT / "migrations" / "19.0.3.52" / "post-migrate.py").read_text(encoding="utf-8")
        self.assertIn('string="Tiene bandejas por defecto"', category_model)
        self.assertIn('"has_trays": category.has_trays', node_model)
        for category_code in ("CTO", "CTO_INTERNAL", "BOX", "CLOSURE"):
            block = defaults.split(f'code">{category_code}</field>', 1)[-1].split("</record>", 1)[0]
            self.assertIn('<field name="has_trays">True</field>', block)
        self.assertIn('"UPDATE fiber_gis_node "', migration)
        self.assertIn('"SET has_trays = TRUE, tray_count = GREATEST', migration)
        self.assertIn("GREATEST(COALESCE(tray_count, 0), 1)", migration)
        self.assertIn("nodes._ensure_trays_from_count()", migration)
        self.assertNotIn("node.write(", migration)


if __name__ == "__main__":
    unittest.main()
