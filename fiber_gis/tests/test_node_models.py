from lxml import etree

from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, new_test_user


class TestNodeModels(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.nodes = cls.env["fiber.gis.node"]
        cls.models = cls.env["fiber.gis.node.category"]
        cls.model_a = cls.models.create({
            "name": "Modelo CTO de prueba", "code": "TEST_MODEL_CTO", "node_kind": "cto",
            "map_icon": "cto", "color": "#112233",
        })
        cls.model_b = cls.models.create({
            "name": "Modelo caja de prueba", "code": "TEST_MODEL_BOX", "node_kind": "box",
            "map_icon": "terminal", "color": "#334455",
        })
        cls.function = cls.env["fiber.gis.asset.type"].create({
            "name": "Distribucion", "code": "TEST_DISTRIBUTION", "category": "node",
            "node_category_ids": [fields.Command.link(cls.model_a.id)],
        })

    def _node(self, **values):
        return self.nodes.create({"name": "Equipo de prueba", "node_category_id": self.model_a.id, **values})

    def test_model_defaults_are_copied(self):
        node = self._node(type_id=self.function.id)
        self.assertEqual(node.node_kind, "cto")
        self.assertEqual(node.map_icon, "cto")
        self.assertEqual(node.color, "#112233")
        self.assertEqual(node.cable_entry_count, 4)

    def test_explicit_style_wins_and_survives_catalog_changes(self):
        node = self._node(map_icon="star", color="#abcdef")
        self.model_a.write({"map_icon": "square", "color": "#778899"})
        node.write({"address": "Calle San Anton, 1, Granada"})
        node.write({"illuminated": True})
        node.write({"node_category_id": self.model_a.id})
        self.assertEqual((node.map_icon, node.color), ("star", "#abcdef"))

    def test_model_change_clears_incompatible_function(self):
        node = self._node(type_id=self.function.id)
        node.write({"node_category_id": self.model_b.id})
        self.assertFalse(node.type_id)
        self.assertEqual((node.node_kind, node.map_icon, node.color), ("box", "terminal", "#334455"))

    def test_model_change_can_keep_explicit_style(self):
        node = self._node()
        node.write({"node_category_id": self.model_b.id, "map_icon": "star", "color": "#abcdef"})
        self.assertEqual((node.map_icon, node.color), ("star", "#abcdef"))

    def test_dowisp_flag_keeps_custom_model(self):
        node = self._node(type_id=self.function.id, color="#abcdef")
        node.write({"dowisp_cto": True})
        self.assertEqual(node.node_category_id, self.model_a)
        self.assertEqual(node.type_id, self.function)
        self.assertEqual(node.color, "#abcdef")

    def test_incompatible_function_rejected_on_create_and_write(self):
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self._node(node_category_id=self.model_b.id, type_id=self.function.id)
        node = self._node()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            node.write({"node_category_id": self.model_b.id, "type_id": self.function.id})

    def test_shared_function_keeps_selected_model(self):
        self.function.write({"node_category_ids": [fields.Command.link(self.model_b.id)]})
        node = self._node(node_category_id=self.model_b.id, type_id=self.function.id)
        self.assertEqual(node.node_kind, "box")

    def test_type_only_import_uses_compatible_model(self):
        node = self.nodes.create({"name": "Importado", "type_id": self.function.id})
        self.assertEqual(node.node_category_id, self.model_a)

    def test_form_defaults_and_model_onchange(self):
        self.model_a.cable_entry_count = 2
        defaults = self.nodes.with_context(default_node_category_id=self.model_a.id).default_get([
            "node_category_id", "node_kind", "cable_entry_count", "map_icon", "color",
        ])
        self.assertEqual((defaults["map_icon"], defaults["color"]), ("cto", "#112233"))
        self.assertEqual(defaults["cable_entry_count"], 2)
        node = self.nodes.new({"node_category_id": self.model_b.id, "type_id": self.function.id})
        node._onchange_node_category_id()
        self.assertFalse(node.type_id)
        self.assertEqual((node.map_icon, node.color), ("terminal", "#334455"))
        self.assertEqual(node.cable_entry_count, 4)

    def test_initialization_preserves_legacy_pairs_and_node_style(self):
        node = self._node(type_id=self.function.id, color="#abcdef", map_icon="star")
        self.function.write({"node_category_ids": [fields.Command.clear()]})
        write_date = node.write_date
        self.models._initialize_model_functions()
        self.models._initialize_model_functions()
        self.assertIn(self.model_a, self.function.node_category_ids)
        self.assertEqual((node.color, node.map_icon, node.write_date), ("#abcdef", "star", write_date))

    def test_model_form_exposes_style_and_functions(self):
        view = self.models.get_view(view_type="form")
        arch = etree.fromstring(view["arch"].encode())
        for name in ("map_icon", "color", "function_type_ids"):
            self.assertTrue(arch.xpath(".//field[@name='%s']" % name))

    def test_catalog_permissions_unchanged(self):
        technician = new_test_user(self.env, login="model_technician", groups="fiber_gis.group_fiber_gis_user")
        manager = new_test_user(self.env, login="model_manager", groups="fiber_gis.group_fiber_gis_manager")
        self.model_a.with_user(technician).read(["name", "map_icon", "color", "function_type_ids"])
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.model_a.with_user(technician).write({"color": "#abcdef"})
        self.model_a.with_user(manager).write({"color": "#abcdef"})
