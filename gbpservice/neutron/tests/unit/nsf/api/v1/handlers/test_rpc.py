import unittest
from gbpservice.neutron.nsf.configurator.api.v1.handlers import rpc
import json
import mock


class FirewallTestCase(unittest.TestCase):

    def test_create_firewall(self):
        fw_handler = rpc.FwaasRpc(topic="FWAAS_RPC_TOPIC")
        with mock.patch.object(fw_handler.client, 'cast') as rpc_mock,\
                mock.patch.object(fw_handler.client, 'prepare') as prepare_mock:
            prepare_mock.return_value = fw_handler.client
            rpc_mock.return_value = True
            value = fw_handler.create_firewall("context", "firewall", "host")
        prepare_mock.assert_called_once_with("host")
        rpc_mock.assert_called_once_with(
            'context', 'create_firewall', "firewall", "host")
        self.assertEqual(value, True)

    def test_update_firewall(self):
        fw_handler = rpc.FwaasRpc(topic="FWAAS_RPC_TOPIC")
        with mock.patch.object(fw_handler.client, 'cast') as rpc_mock,\
                mock.patch.object(fw_handler.client, 'prepare') as prepare_mock:
            prepare_mock.return_value = fw_handler.client
            rpc_mock.return_value = True
            value = fw_handler.update_firewall("context", "firewall", "host")
        prepare_mock.assert_called_once_with("host")
        rpc_mock.assert_called_once_with(
            'context', 'update_firewall', "firewall", "host")
        self.assertEqual(value, True)

    def test_delete_firewall(self):
        fw_handler = rpc.FwaasRpc(topic="FWAAS_RPC_TOPIC")
        with mock.patch.object(fw_handler.client, 'cast') as rpc_mock,\
                mock.patch.object(fw_handler.client, 'prepare') as prepare_mock:
            prepare_mock.return_value = fw_handler.client
            rpc_mock.return_value = True
            value = fw_handler.delete_firewall("context", "firewall", "host")
        prepare_mock.assert_called_once_with("host")
        rpc_mock.assert_called_once_with(
            'context', 'delete_firewall', "firewall", "host")
        self.assertEqual(value, True)


if __name__ == '__main__':
    unittest.main()
