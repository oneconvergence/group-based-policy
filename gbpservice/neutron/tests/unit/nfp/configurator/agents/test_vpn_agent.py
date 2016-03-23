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


from gbpservice.nfp.configurator.agents import vpn
from gbpservice.nfp.configurator.drivers.vpn.vyos import vyos_vpn_driver
from gbpservice.neutron.tests.unit.nfp.configurator.test_data import (
                                                                test_vpn_data)
import json
import unittest
import mock
import requests


class VPNaasEventHandlerTestCase(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(VPNaasEventHandlerTestCase, self).__init__(*args, **kwargs)
        self.dict_obj = test_vpn_data.MakeDictionaries()
        self.handler = vpn.VPNaasEventHandler(self.dict_obj.sc,
                                              self.dict_obj.drivers)
        self.ev = test_vpn_data.FakeEvent()
        self.driver = vyos_vpn_driver.VpnaasIpsecDriver(
                                                self.handler.plugin_rpc)

    def test_handle_event(self):
        '''
        Test to handle the vpn agent's vpnservice_updated method to 
        handle various vpn operations

        '''
        with mock.patch.object(self.handler,
                               '_get_driver',
                               return_value=self.dict_obj.drivers) as (
                                                                mock_drivers),\
            mock.patch.object(self.driver, 'vpnservice_updated') as (
                                                    mock_vpnservice_updated):
            self.handler.vpnservice_updated(self.ev, self.driver)
            mock_vpnservice_updated.assert_called_with(self.ev.data['context'],
                                                       self.ev.data['kwargs'])

    def test_sync(self):
        '''
        Implements a testcase methos for vpns sync method
        '''

        context = self.dict_obj._make_service_context()
        with mock.patch.object(self.handler,
                               '_get_driver',
                               return_value=self.driver) as mock_drivers,\
            mock.patch.object(self.driver, 'check_status') as (
                                                mock_update_status):
            self.handler.sync(context)
            mock_update_status.assert_called_with(context,
                                                  self.dict_obj.svc_context)


if __name__ == '__main__':
    unittest.main()

