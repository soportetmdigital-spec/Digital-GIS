"""Acceso a las pestanas CTO sin privilegios de administrador."""

from lxml import etree

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user
from odoo.tools.safe_eval import safe_eval


class TestNodeTabs(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.technician = new_test_user(
            cls.env,
            login="gis_tab_technician",
            groups="base.group_user,fiber_gis.group_fiber_gis_user",
        )
        cls.manager = new_test_user(
            cls.env,
            login="gis_tab_manager",
            groups="base.group_user,fiber_gis.group_fiber_gis_manager",
        )
        cls.portal_user = new_test_user(
            cls.env, login="gis_tab_portal", groups="base.group_portal",
        )
        cls.cto = cls.env["fiber.gis.node"].create({
            "name": "CTO para permisos", "code": "TAB-CTO-ACCESS", "node_kind": "cto",
            "dowisp_id": 1234, "uuii": "24", "illuminated": True,
        })
        cls.view_id = cls.env.ref("fiber_gis.view_fiber_gis_node_form").id

    def test_cto_tabs_are_available_to_technicians_and_managers(self):
        for user in (self.technician, self.manager):
            with self.subTest(user=user.login):
                self.assertFalse(user.has_group("base.group_system"))
                model = self.env["fiber.gis.node"].with_user(user)
                arch = etree.fromstring(model.get_view(self.view_id, "form")["arch"])
                available_fields = model.fields_get()
                for page_name in ("datos_dowisp", "datos_cto"):
                    pages = arch.xpath("//page[@name='%s']" % page_name)
                    self.assertEqual(len(pages), 1)
                    page = pages[0]
                    field_names = page.xpath(".//field/@name")
                    for name in field_names:
                        self.assertIn(name, available_fields)
                    self.cto.with_user(user).read(field_names)
                    expression = page.get("invisible", "False")
                    if page_name == "datos_cto":
                        self.assertEqual(page.get("string"), "Cobertura CTO")
                        for kind, _label in model._fields["node_kind"].selection:
                            for imported_cto in (False, True):
                                self.assertFalse(safe_eval(expression, {
                                    "node_kind": kind, "dowisp_cto": imported_cto,
                                }))
                    else:
                        self.assertFalse(safe_eval(expression, {"node_kind": "cto", "dowisp_cto": False}))
                        self.assertFalse(safe_eval(expression, {"node_kind": "box", "dowisp_cto": True}))
                        self.assertTrue(safe_eval(expression, {"node_kind": "box", "dowisp_cto": False}))
                        self.assertTrue(safe_eval(expression, {"node_kind": "ont", "dowisp_cto": False}))

    def test_portal_has_no_read_access_to_cto_records(self):
        with self.assertRaises(AccessError):
            self.cto.with_user(self.portal_user).read(["dowisp_id", "uuii"])

    def test_menu_label_changes_without_changing_external_id(self):
        menu = self.env.ref("fiber_gis.menu_fiber_gis_root").with_context(lang="en_US")
        self.assertEqual(menu.name, "Digital GIS")
