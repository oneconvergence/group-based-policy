import unittest
from gbpservice.neutron.nsf.configurator.api.v1.controllers import firewall
import json
import mock



class FirewallTestCase(unittest.TestCase):

    def test_create_firewall(self):
        fw_controller = firewall.FwaasController()
        with mock.patch.object(fw_controller.fwaas_handler, 'create_firewall') as rpc_mock:
            rpc_mock.return_value = True
            value = fw_controller._create_firewall(
                body=({"kwargs": {"fw": "fw", "host": "host", "context": "context"}}))
        rpc_mock.assert_called_once_with("context", "fw", "host")
        self.assertEqual(value, 'true')

    def test_delete_firewall(self):
        fw_controller = firewall.FwaasController()
        with mock.patch.object(fw_controller.fwaas_handler, 'delete_firewall') as rpc_mock:
            rpc_mock.return_value = True
            value = fw_controller._delete_firewall(
                body=({"kwargs": {"fw": "fw", "host": "host", "context": "context"}}))
        rpc_mock.assert_called_once_with("context", "fw", "host")
        self.assertEqual(value, 'true')

    def test_update_firewall(self):
        fw_controller = firewall.FwaasController()
        with mock.patch.object(fw_controller.fwaas_handler, 'update_firewall') as rpc_mock:
            rpc_mock.return_value = True
            value = fw_controller._update_firewall(
                body=({"kwargs": {"fw": "fw", "host": "host", "context": "context"}}))
        rpc_mock.assert_called_once_with("context", "fw", "host")
        self.assertEqual(value, 'true')


if __name__ == '__main__':
    unittest.main()
