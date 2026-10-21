from odoo.tests import TransactionCase


class TestCableTrayWizard(TransactionCase):
    def test_work_log_text_resolves_method_based_operation_selection(self):
        wizard = self.env["fiber.gis.cable.tray.wizard"].new({
            "operation": "rest",
            "from_fiber": 2,
            "to_fiber": 5,
        })
        labels = dict(wizard._fields["operation"]._description_selection(wizard.env))

        self.assertTrue(labels["rest"])
        self.assertTrue(wizard._work_log_text().startswith(f"{labels['rest']} en "))
