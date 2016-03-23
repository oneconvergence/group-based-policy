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
import os
import sys
import ast
import json
import time

from oslo_log import log as logging
import oslo_messaging as messaging

from gbpservice.nfp.lib.transport import *
from gbpservice.nfp.proxy_agent.lib import topics

from gbpservice.nfp.proxy_agent.modules.proxy_agent import RpcHandler as rpc_manager
from gbpservice.nfp.proxy_agent.lib import RestClientOverUnix as rc
from neutron import context as ctx

import mock
import unittest

class TestContext(object):
    def get_context(self):
        try:
            return ctx.Context('some_user', 'some_tenant')
        except:
            return ctx.Context('some_user', 'some_tenant')



class ConfigAgentProxyTestCase(unittest.TestCase):

    def setUp(self):
		self.manager = rpc_manager('conf','sc')
		self.context = TestContext().get_context()
		self.imprt_rc = 'gbpservice.nfp.proxy_agent.lib.RestClientOverUnix'

    def _post(self, path, body, delete=False):
        return (200,'')

    def _get(self, path):
        return(200, " ")

    def test_create_network_function_config(self):
        _data = "data"
        with mock.patch(self.imprt_rc + '.post') as mock_post:
            mock_post.side_effect = self._post
            self.manager.create_network_function_config(self.context,_data)

    def test_delete_network_function_config(self):
        _data = "data"
        with mock.patch(self.imprt_rc + '.post') as mock_post:
            mock_post.side_effect = self._post
            self.manager.delete_network_function_config(self.context,_data)

    def test_create_network_function_device_config(self):
        _data = "data"
        with mock.patch(self.imprt_rc + '.post') as mock_post:
            mock_post.side_effect = self._post
            self.manager.create_network_function_device_config(self.context,_data)

    def test_delete_network_function_device_config(self):
        _data = "data"
        with mock.patch(self.imprt_rc + '.post') as mock_post:
            mock_post.side_effect = self._post
            self.manager.delete_network_function_device_config(self.context,_data)

    def test_get_notifications(self):
        _data = "data"
        with mock.patch(self.imprt_rc + '.get') as mock_get, \
        mock.patch.object(json, 'loads') as mock_loads:
            mock_get.side_effect = self._get
            mock_loads.return_value = True
            self.manager.get_notifications(self.context)

if __name__ == "__main__":
    unittest.main()
