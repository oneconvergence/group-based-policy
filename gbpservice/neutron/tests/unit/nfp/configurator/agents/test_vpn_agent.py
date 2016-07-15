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


import mock

from gbpservice.neutron.tests.unit.nfp.configurator.test_data import (
    vpn_test_data)
from gbpservice.nfp.configurator.agents import vpn
from gbpservice.nfp.configurator.lib import vpn_constants as const

from neutron.tests import base


class VPNaasRpcManagerTestCase(base.BaseTestCase):
    '''
    Implements test cases for RPC manager methods of vpn agent
    '''
    def __init__(self, *args, **kwargs):
        super(VPNaasRpcManagerTestCase, self).__init__(*args, **kwargs)
        self.dict_obj = vpn_test_data.VPNTestData()
        self.conf = self.dict_obj.conf
        self.sc = mock.Mock()
        self.rpcmgr = vpn.VPNaasRpcManager(self.conf, self.sc)

    def test_vpnservice_updated(self):
        resource_data = self.dict_obj._create_ipsec_site_conn_obj()
        with mock.patch.object(self.sc, 'new_event',
                               return_value='foo'), (
             mock.patch.object(self.sc, 'post_event')) as mock_post_event:
            self.rpcmgr.vpnservice_updated(
                        self.dict_obj.make_service_context(),
                        resource_data=resource_data)
            mock_post_event.assert_called_with('foo')


class VPNaasEventHandlerTestCase(base.BaseTestCase):
    '''
    Implements test cases for RPC manager methods of vpn agent
    '''
    def __init__(self, *args, **kwargs):
        super(VPNaasEventHandlerTestCase, self).__init__(*args, **kwargs)
        self.dict_obj = vpn_test_data.VPNTestData()
        self.sc = self.dict_obj.sc
        self.conf = self.dict_obj.conf
        self.handler = vpn.VPNaasEventHandler(self.dict_obj.sc,
                                              self.dict_obj.drivers)
        self.ev = vpn_test_data.FakeEvent()
        self.rpc_sender = vpn.VpnaasRpcSender(self.sc)
        self.driver = mock.Mock()

    def test_handle_event(self):
        '''
        Test to handle the vpn agent's vpnservice_updated method to
        handle various vpn operations

        '''
        with mock.patch.object(self.handler,
                               '_get_driver',
                               return_value=self.dict_obj.drivers), (
             mock.patch.object(
                     self.driver,
                     'vpnservice_updated')) as mock_vpnservice_updated:
            self.handler._vpnservice_updated(self.ev, self.driver)
            mock_vpnservice_updated.assert_called_with(self.ev.data['context'],
                                                       self.ev.data[
                                                           'resource_data'])

    def test_sync(self):
        '''
        Test to handle the vpn service status like ACTIVE, ERROR
        after the configurations.

        '''
        with mock.patch.object(self.handler,
                               '_get_driver',
                               return_value=self.driver), (
             mock.patch.object(self.rpc_sender,
                               'get_vpn_servicecontext')), (
             mock.patch.object(self.driver,
                               'check_status',
                               return_value=const.STATE_ACTIVE)):

            self.assertEqual(self.handler.sync(self.ev), {'poll': False})
