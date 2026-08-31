from odoo.tests import TransactionCase


class TestOntTechnicalData(TransactionCase):
    def test_ont_technical_data_is_stored(self):
        ont = self.env["fiber.gis.node"].create({
            "name": "ONT de prueba",
            "code": "ONT-TECH-TEST",
            "node_kind": "ont",
            "manufacturer": "Fabricante",
            "model": "Modelo X",
            "serial": "HW-0001",
            "ont_gpon_serial": "GPON-0001",
            "ont_loid": "LOID-0001",
            "ont_olt_pon_port": "OLT-1/PON-4",
            "ont_optical_rx_dbm": -19.5,
            "ont_optical_tx_dbm": 2.1,
            "ont_mac_address": "00:11:22:33:44:55",
            "ont_management_ip": "192.168.1.1",
            "ont_firmware_version": "1.2.3",
            "ont_operation_mode": "router",
            "ont_internet_vlan": 100,
            "ont_wifi_ssid": "Fibra-Test",
            "ont_wifi_standard": "wifi6",
        })

        self.assertEqual(ont.ont_gpon_serial, "GPON-0001")
        self.assertEqual(ont.ont_olt_pon_port, "OLT-1/PON-4")
        self.assertEqual(ont.ont_operation_mode, "router")
        self.assertEqual(ont.ont_internet_vlan, 100)
        self.assertEqual(ont.ont_wifi_standard, "wifi6")
