#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

#import json
import mock
import unittest

import oslo_serialization.jsonutils as jsonutils
import pecan
from pecan import rest
import webtest

from gbpservice.nfp.configurator.api import root_controller
from gbpservice.nfp.configurator.api.v1.controllers import controller

"""This class contains all the unittest cases for REST server of configurator.

This class tests success and failure cases for all the HTTP requests which
are implemented in REST server. run_tests.sh file is used for running all
the tests in this class. All the methods of this class started with test
prefix called and on success it will print ok and on failure it will
print the error trace.

"""


class ControllerTestCase(unittest.TestCase, rest.RestController):

    def setUp(self):
        """Standard method of TestCase to setup environment before each test.

        This method set the value of required variables that is used in
        test cases before execution of each test case.


        """
        RootController = root_controller.RootController()
        self.app = webtest.TestApp(pecan.make_app(RootController))
        self.data = {'request_data': {'info': {}, 'config': [
            {'resource': 'Res', 'kwargs': {'context': 'context'}}]}}

    def test_get_notifications(self):
        """Tests HTTP get request get_notifications.

        Returns: none

        """

        with mock.patch.object(
                controller.RPCClient, 'call') as rpc_mock:
            rpc_mock.return_value = jsonutils.dumps(self.data)
            response = self.app.get(
                '/v1/nfp/get_notifications',
            )
        rpc_mock.assert_called_with()
        self.assertEqual(response.status_code, 200)

    def test_post_create_network_function_device_config(self):
        """Tests HTTP post request create_network_function_device_config.

        Returns: none

        """

        with mock.patch.object(
                controller.RPCClient, 'cast') as rpc_mock:
            response = self.app.post(
                '/v1/nfp/create_network_function_device_config',
                jsonutils.dumps(self.data))
        rpc_mock.assert_called_with(
            'create_network_function_device_config', self.data)
        self.assertEqual(response.status_code, 204)

    def test_post_create_network_function_device_config(self):
        """Tests HTTP post request create_network_function_device_config.

        Returns: none

        """

        with mock.patch.object(
                controller.RPCClient, 'cast') as rpc_mock:
            response = self.app.post(
                '/v1/nfp/create_network_function_device_config',
                jsonutils.dumps(self.data))
        rpc_mock.assert_called_with(
            'create_network_function_device_config', self.data)
        self.assertEqual(response.status_code, 204)

    def test_post_create_network_function_config(self):
        """Tests HTTP post request create_network_function_config.

        Returns: none

        """

        with mock.patch.object(
                controller.RPCClient, 'cast') as rpc_mock:
            response = self.app.post(
                '/v1/nfp/create_network_function_config',
                jsonutils.dumps(self.data))
        rpc_mock.assert_called_with(
            'create_network_function_config', self.data)
        self.assertEqual(response.status_code, 204)

    def test_post_delete_network_function_device_config(self):
        """Tests HTTP post request delete_network_function_device_config.

        Returns: none

        """

        with mock.patch.object(
                controller.RPCClient, 'cast') as rpc_mock:
            response = self.app.post(
                '/v1/nfp/delete_network_function_device_config',
                jsonutils.dumps(self.data))
        rpc_mock.assert_called_with(
            'delete_network_function_device_config', self.data)
        self.assertEqual(response.status_code, 204)

    def test_post_delete_network_function_config(self):
        """Tests HTTP post request delete_network_function_config.

        Returns: none

        """

        with mock.patch.object(
                controller.RPCClient, 'cast') as rpc_mock:
            response = self.app.post(
                '/v1/nfp/delete_network_function_config',
                jsonutils.dumps(self.data))
        rpc_mock.assert_called_with(
            'delete_network_function_config', self.data)
        self.assertEqual(response.status_code, 204)

    def test_put_update_network_function_device_config(self):
        """Tests HTTP put request update_network_function_device_config.

        Returns: none

        """

        with mock.patch.object(
                controller.RPCClient, 'cast') as rpc_mock:
            response = self.app.put(
                '/v1/nfp/update_network_function_device_config',
                jsonutils.dumps(self.data))
        rpc_mock.assert_called_with(
            'update_network_function_device_config', self.data)
        self.assertEqual(response.status_code, 204)

    def test_put_update_network_function_config(self):
        """Tests HTTP put request update_network_function_config.

        Returns: none

        """

        with mock.patch.object(
                controller.RPCClient, 'cast') as rpc_mock:
            response = self.app.put(
                '/v1/nfp/update_network_function_config',
                jsonutils.dumps(self.data))
        rpc_mock.assert_called_with(
            'update_network_function_config', self.data)
        self.assertEqual(response.status_code, 204)

    def test_call(self):
        """Tests call function of RPCClient.

        Returns: none

        """
        rpcclient = controller.RPCClient('topic_name', 'host_name')
        with mock.patch.object(
            rpcclient.client, 'call') as rpc_mock,\
            mock.patch.object(
                rpcclient.client, 'prepare') as (
                    prepare_mock):
            prepare_mock.return_value = rpcclient.client
            rpc_mock.return_value = True
            value = rpcclient.call()
        self.assertEqual(value, True)

    def test_cast(self):
        """Tests cast function of RPCClient.

        Returns: none

        """
        rpcclient = controller.RPCClient('topic_name', 'host_name')
        with mock.patch.object(
            rpcclient.client, 'cast') as rpc_mock,\
            mock.patch.object(
                rpcclient.client, 'prepare') as (
                    prepare_mock):
            prepare_mock.return_value = rpcclient.client
            rpc_mock.return_value = True
            value = rpcclient.cast('rpc_method_name',
                                   jsonutils.dumps(self.data))
        self.assertEqual(value, True)

    def test_get_notifications_fail(self):
        """Tests failure case of HTTP get request get_notifications.

        Returns: none

        """

        with mock.patch.object(
                controller.RPCClient, 'call') as rpc_mock:
            rpc_mock.return_value = Exception
            response = self.app.get(
                '/v1/nfp/get_notifications',
                expect_errors=True)
            self.assertEqual(response.status_code, 400)

    def test_post_create_network_function_device_config_fail(self):
        """Tests failure case of HTTP post request
        create_network_function_device_config

        Returns: none

        """

        with mock.patch.object(
                controller.RPCClient, 'cast') as rpc_mock:
            rpc_mock.return_value = Exception
            response = self.app.post(
                '/v1/nfp/create_network_function_device_config',
                expect_errors=True)
            self.assertEqual(response.status_code, 400)

    def test_post_create_network_function_config_fail(self):
        """Tests failure case of HTTP post request
        create_network_function_config

        Returns: none

        """

        with mock.patch.object(
                controller.RPCClient, 'cast') as rpc_mock:
            rpc_mock.return_value = Exception
            response = self.app.post(
                '/v1/nfp/create_network_function_config',
                expect_errors=True)
            self.assertEqual(response.status_code, 400)

    def test_post_delete_network_function_device_config_fail(self):
        """Tests failure case of HTTP post request
        delete_network_function_device_config

        Returns: none

        """

        with mock.patch.object(
                controller.RPCClient, 'cast') as rpc_mock:
            rpc_mock.return_value = Exception
            response = self.app.post(
                '/v1/nfp/delete_network_function_device_config',
                expect_errors=True)
            self.assertEqual(response.status_code, 400)

    def test_post_delete_network_function_config_fail(self):
        """Tests failure case of HTTP post request
        delete_network_function_config

        Returns: none

        """

        with mock.patch.object(
                controller.RPCClient, 'cast') as rpc_mock:
            rpc_mock.return_value = Exception
            response = self.app.post(
                '/v1/nfp/delete_network_function_config',
                expect_errors=True)
            self.assertEqual(response.status_code, 400)

    def test_put_update_network_function_device_config_fail(self):
        """Tests failure case of HTTP put request
        update_network_function_device_config

        Returns: none

        """

        with mock.patch.object(
                controller.RPCClient, 'cast') as rpc_mock:
            rpc_mock.return_value = Exception
            response = self.app.post(
                '/v1/nfp/update_network_function_device_config',
                expect_errors=True)
            self.assertEqual(response.status_code, 400)

    def test_put_update_network_function_config_fail(self):
        """Tests failure case of HTTP put request
        update_network_function_config

        Returns: none

        """

        with mock.patch.object(
                controller.RPCClient, 'cast') as rpc_mock:
            rpc_mock.return_value = Exception
            response = self.app.post(
                '/v1/nfp/update_network_function_config',
                expect_errors=True)
            self.assertEqual(response.status_code, 400)


if __name__ == '__main__':
    unittest.main()
