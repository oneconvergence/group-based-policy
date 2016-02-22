import json
import mock
import unittest

from pecan import rest
from pecan import set_config
from pecan.testing import load_test_app

from gbpservice.neutron.nsf.configurator.api.v1.controllers import controller



class ControllerTestCase(unittest.TestCase, rest.RestController):

    def setUp(self):
        self.app = load_test_app('config.py')

    def tearDown(self):
        set_config({}, overwrite=True)

    def test_get(self):
        controller_object = controller.Controller("module_name")
        with mock.patch.object(controller_object, '_get_notifications') as rpc_mock:
            rpc_mock.return_value = True
            value = controller_object.get()
            rpc_mock.assert_called_once_with()
        self.assertEqual(value, True)

    def test_post(self):
        with mock.patch.object(self.app, 'post') as rpc_mock:
            rpc_mock.return_value = 200
            value = self.app.post(
                '/v1/nfp/create_network_function_device_config',
                headers={
                    'content-type': 'application/json'})
        self.assertEqual(value, 200)

    def test_put(self):
        with mock.patch.object(self.app, 'put') as rpc_mock:
            rpc_mock.return_value = 200
            value = self.app.put('/v1/nfp/delete_network_function_device_config')
        self.assertEqual(value, 200)

    def test_get_notifications(self):
        controller_object = controller.Controller("module_name")
        with mock.patch.object(controller_object.rpcclient, 'get_notifications') as rpc_mock:
            rpc_mock.return_value = True
            value = controller_object._get_notifications()
            rpc_mock.assert_called_once_with()
        self.assertEqual(value, 'true')

    def test_create_network_device_config(self):
        controller_object = controller.Controller("module_name")
        with mock.patch.object(controller_object.rpcclient, 'create_network_device_config') as rpc_mock:
            rpc_mock.return_value = True
            value = controller_object._create_network_device_config(
                        body=({"request_data":
                              {"info": {},
                               "config": [{"resource": "Res", "kwargs":
                                          {"context": "context"}}]}}))
            rpc_mock.assert_called_once_with({"info": {}, "config": [
                {"resource": "Res", "kwargs": {"context": "context"}}]})
        self.assertEqual(value, 'true')

    def test_create_network_function_config(self):
        controller_object = controller.Controller("module_name")
        with mock.patch.object(controller_object.rpcclient, 'create_network_service_config') as rpc_mock:
            rpc_mock.return_value = True
            value = controller_object._create_network_function_config(
                        body=({"request_data":
                              {"info": {},
                               "config": [{"resource": "Res", "kwargs":
                                          {"context": "context"}}]}}))
        rpc_mock.assert_called_once_with(
            {"info": {},
             "config": [{"resource": "Res",
                         "kwargs": {"context": "context"}}]})
        self.assertEqual(value, 'true')

    def test_update_network_device_config(self):
        controller_object = controller.Controller("module_name")
        with mock.patch.object(controller_object.rpcclient, 'update_network_device_config') as rpc_mock:
            rpc_mock.return_value = True
            value = controller_object._update_network_device_config(
                        body=({"request_data":
                              {"info": {},
                               "config": [{"resource": "Res", "kwargs":
                                          {"context": "context"}}]}}))
        rpc_mock.assert_called_once_with(
            {"info": {},
             "config": [{"resource": "Res",
                         "kwargs": {"context": "context"}}]})
        self.assertEqual(value, 'true')

    def test_update_network_service_config(self):
        controller_object = controller.Controller("module_name")
        with mock.patch.object(controller_object.rpcclient, 'update_network_service_config') as rpc_mock:
            rpc_mock.return_value = True
            value = controller_object._update_network_service_config(
                        body=({"request_data":
                              {"info": {},
                               "config": [{"resource": "Res", "kwargs":
                                          {"context": "context"}}]}}))
        rpc_mock.assert_called_once_with(
            {"info": {},
             "config": [{"resource": "Res",
                         "kwargs": {"context": "context"}}]})
        self.assertEqual(value, 'true')

    def test_delete_network_device_config(self):
        controller_object = controller.Controller("module_name")
        with mock.patch.object(controller_object.rpcclient, 'delete_network_device_config') as rpc_mock:
            rpc_mock.return_value = True
            value = controller_object._delete_network_device_config(
                        body=({"request_data":
                              {"info": {},
                               "config": [{"resource": "Res", "kwargs":
                                          {"context": "context"}}]}}))
        rpc_mock.assert_called_once_with(
            {"info": {},
             "config": [{"resource": "Res",
                         "kwargs": {"context": "context"}}]})
        self.assertEqual(value, 'true')

    def test_delete_network_service_config(self):
        controller_object = controller.Controller("module_name")
        with mock.patch.object(controller_object.rpcclient, 'delete_network_service_config') as rpc_mock:
            rpc_mock.return_value = True
            value = controller_object._delete_network_service_config(
                        body=({"request_data":
                              {"info": {},
                               "config": [{"resource": "Res", "kwargs":
                                          {"context": "context"}}]}}))
        rpc_mock.assert_called_once_with(
            {"info": {},
             "config": [{"resource": "Res",
                         "kwargs": {"context": "context"}}]})
        self.assertEqual(value, 'true')

    def test_get_notifications_rpcclient(self):
        rpcclient = controller.RPCClient("topic", "host")
        with mock.patch.object(rpcclient.client, 'call') as rpc_mock,\
                mock.patch.object(rpcclient.client, 'prepare') as prepare_mock:
            prepare_mock.return_value = rpcclient.client
            rpc_mock.return_value = True
            value = rpcclient.get_notifications()
        prepare_mock.assert_called_once_with(server="host")
        rpc_mock.assert_called_once_with(rpcclient, 'get_notifications')
        self.assertEqual(value, True)

    def test_create_network_device_config_rpcclient(self):
        rpcclient = controller.RPCClient("topic", "host")
        with mock.patch.object(rpcclient.client, 'cast') as rpc_mock,\
                mock.patch.object(rpcclient.client, 'prepare') as prepare_mock:
            prepare_mock.return_value = rpcclient.client
            rpc_mock.return_value = True
            value = rpcclient.create_network_device_config(
                {"info": {},
                 "config": [{"resource": "Res",
                             "kwargs": {"context": "context"}}]})
        prepare_mock.assert_called_once_with(server="host")
        rpc_mock.assert_called_once_with('context',
                                         'create_network_device_config',
                                         request_data={'info': {},
                                                       'config':
                                                       [{'resource': 'Res',
                                                         'kwargs': {}}]})
        self.assertEqual(value, True)

    def test_create_network_service_config_rpcclient(self):
        rpcclient = controller.RPCClient("topic", "host")
        with mock.patch.object(rpcclient.client, 'cast') as rpc_mock,\
                mock.patch.object(rpcclient.client, 'prepare') as prepare_mock:
            prepare_mock.return_value = rpcclient.client
            rpc_mock.return_value = True
            value = rpcclient.create_network_service_config(
                {"info": {},
                 "config": [{"resource": "Res",
                             "kwargs": {"context": "context"}}]})
        prepare_mock.assert_called_once_with(server="host")
        rpc_mock.assert_called_once_with('context',
                                         'create_network_service_config',
                                         request_data={'info': {},
                                                       'config':
                                                       [{'resource': 'Res',
                                                         'kwargs': {}}]})
        self.assertEqual(value, True)

    def test_update_network_device_config_rpcclient(self):
        rpcclient = controller.RPCClient("topic", "host")
        with mock.patch.object(rpcclient.client, 'cast') as rpc_mock,\
                mock.patch.object(rpcclient.client, 'prepare') as prepare_mock:
            prepare_mock.return_value = rpcclient.client
            rpc_mock.return_value = True
            value = rpcclient.update_network_device_config(
                {"info": {},
                 "config": [{"resource": "Res",
                             "kwargs": {"context": "context"}}]})
        prepare_mock.assert_called_once_with(server="host")
        rpc_mock.assert_called_once_with('context',
                                         'update_network_device_config',
                                         request_data={'info': {},
                                                       'config':
                                                       [{'resource': 'Res',
                                                         'kwargs': {}}]})
        self.assertEqual(value, True)

    def test_update_network_service_config_rpcclient(self):
        rpcclient = controller.RPCClient("topic", "host")
        with mock.patch.object(rpcclient.client, 'cast') as rpc_mock,\
                mock.patch.object(rpcclient.client, 'prepare') as prepare_mock:
            prepare_mock.return_value = rpcclient.client
            rpc_mock.return_value = True
            value = rpcclient.update_network_service_config(
                {"info": {},
                 "config": [{"resource": "Res",
                             "kwargs": {"context": "context"}}]})
        prepare_mock.assert_called_once_with(server="host")
        rpc_mock.assert_called_once_with('context',
                                         'update_network_service_config',
                                         request_data={'info': {},
                                                       'config':
                                                       [{'resource': 'Res',
                                                         'kwargs': {}}]})
        self.assertEqual(value, True)

    def test_delete_network_device_config_rpcclient(self):
        rpcclient = controller.RPCClient("topic", "host")
        with mock.patch.object(rpcclient.client, 'cast') as rpc_mock,\
                mock.patch.object(rpcclient.client, 'prepare') as prepare_mock:
            prepare_mock.return_value = rpcclient.client
            rpc_mock.return_value = True
            value = rpcclient.delete_network_device_config(
                {"info": {},
                 "config": [{"resource": "Res",
                             "kwargs": {"context": "context"}}]})
        prepare_mock.assert_called_once_with(server="host")
        rpc_mock.assert_called_once_with('context',
                                         'delete_network_device_config',
                                         request_data={'info': {},
                                                       'config':
                                                       [{'resource': 'Res',
                                                         'kwargs': {}}]})
        self.assertEqual(value, True)

    def test_delete_network_service_config_rpcclient(self):
        rpcclient = controller.RPCClient("topic", "host")
        with mock.patch.object(rpcclient.client, 'cast') as rpc_mock,\
                mock.patch.object(rpcclient.client, 'prepare') as prepare_mock:
            prepare_mock.return_value = rpcclient.client
            rpc_mock.return_value = True
            value = rpcclient.delete_network_service_config(
                {"info": {},
                 "config": [{"resource": "Res",
                             "kwargs": {"context": "context"}}]})
        prepare_mock.assert_called_once_with(server="host")
        rpc_mock.assert_called_once_with('context',
                                         'delete_network_service_config',
                                         request_data={'info': {},
                                                       'config':
                                                       [{'resource': 'Res',
                                                         'kwargs': {}}]})
        self.assertEqual(value, True)


if __name__ == '__main__':
    unittest.main()
