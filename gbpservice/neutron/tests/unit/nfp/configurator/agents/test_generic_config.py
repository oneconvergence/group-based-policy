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
import subprocess
import unittest

from oslo_config import cfg
from oslo_log import log as logging

from gbpservice.neutron.tests.unit.nfp.configurator.test_data import (
                                                        fw_test_data as fo)
from gbpservice.nfp.configurator.agents import generic_config as gc
from gbpservice.nfp.configurator.drivers.firewall.vyos import (
                                                    vyos_fw_driver as fw_dvr)
from gbpservice.nfp.configurator.lib import (
                                    generic_config_constants as gen_cfg_const)

LOG = logging.getLogger(__name__)

STATUS_ACTIVE = "ACTIVE"

""" Implement test cases for RPC manager methods of generic config agent.

"""


class GenericConfigRpcManagerTestCase(unittest.TestCase):
    ''' Generic Config RPC receiver for Firewall module '''

    def __init__(self, *args, **kwargs):
        super(GenericConfigRpcManagerTestCase, self).__init__(
                                                        *args, **kwargs)
        self.fo = fo.FakeObjects()

    @mock.patch(__name__ + '.fo.FakeObjects.sc')
    @mock.patch(__name__ + '.fo.FakeObjects.conf')
    def _get_GenericConfigRpcManager_object(self, conf, sc):
        """ Retrieves RPC manager object of generic config agent.

        :param sc: mocked service controller object of process model framework
        :param conf: mocked OSLO configuration file

        Returns: object of generic config's RPC manager
        and service controller.

        """

        agent = gc.GenericConfigRpcManager(sc, conf)
        return agent, sc

    def _test_event_creation(self, method):
        """ Tests event creation and enqueueing for create/delete
        operation of generic config agent's RPC manager.

        :param method: CONFIGURE_INTERFACES/CLEAR_INTERFACES/
        CONFIGURE_ROUTES/CLEAR_ROUTES

        Returns: none

        """

        agent, sc = self._get_GenericConfigRpcManager_object()
        arg_dict = {'context': self.fo.context,
                    'kwargs': self.fo.kwargs}
        with mock.patch.object(
                    sc, 'new_event', return_value='foo') as mock_sc_event, \
            mock.patch.object(sc, 'post_event') as mock_sc_rpc_event:
            call_method = getattr(agent, method.lower())

            call_method(self.fo.context, self.fo.kwargs)

            if 'HEALTHMONITOR' in method:
                mock_sc_event.assert_called_with(id=method,
                                                 data=arg_dict,
                                                 key=self.fo.kwargs['vmid'])
            else:
                mock_sc_event.assert_called_with(id=method,
                                                 data=arg_dict, key=None)
            mock_sc_rpc_event.assert_called_with('foo')

    def test_configure_interfaces_genericconfigrpcmanager(self):
        """ Implements test case for configure interfaces method
        of generic config agent RPCmanager.

        Returns: none

        """

        self._test_event_creation('CONFIGURE_INTERFACES')

    def test_clear_interfaces_genericconfigrpcmanager(self):
        """ Implements test case for clear interfaces method
        of generic config agent RPCmanager.

        Returns: none

        """

        self._test_event_creation('CLEAR_INTERFACES')

    def test_configure_routes_genericconfigrpcmanager(self):
        """ Implements test case for configure routes method
        of generic config agent RPCmanager.

        Returns: none

        """

        self._test_event_creation('CONFIGURE_ROUTES')

    def test_clear_routes_genericconfigrpcmanager(self):
        """ Implements test case for clear routes method
        of generic config agent RPCmanager.

        Returns: none

        """

        self._test_event_creation('CLEAR_ROUTES')

    def test_configure_hm_genericconfigrpcmanager(self):
        """ Implements test case for configure healthmonitor method
        of generic config agent RPCmanager.

        Returns: none

        """

        self._test_event_creation('CONFIGURE_HEALTHMONITOR')

    def test_clear_hm_genericconfigrpcmanager(self):
        """ Implements test case for clear healthmonitor method
        of generic config agent RPCmanager.

        Returns: none

        """

        self._test_event_creation('CLEAR_HEALTHMONITOR')

""" Implements test cases for event handler methods
of generic config agent.

"""


class GenericConfigEventHandlerTestCase(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(GenericConfigEventHandlerTestCase, self).__init__(
                                                        *args, **kwargs)
        self.fo = fo.FakeObjects()
        self.empty = self.fo.empty_dict
        self.context = {'notification_data': {},
                        'resource': 'interfaces'}

    @mock.patch(__name__ + '.fo.FakeObjects.rpcmgr')
    @mock.patch(__name__ + '.fo.FakeObjects.drivers')
    @mock.patch(__name__ + '.fo.FakeObjects.sc')
    def _get_GenericConfigEventHandler_object(self, sc, drivers, rpcmgr):
        """ Retrieves event handler object of generic config.

        :param sc: mocked service controller object of process model framework
        :param rpcmgr: object of configurator's RPC manager
        :param drivers: list of driver objects for firewall agent

        Returns: object of generic config's event handler

        """

        agent = gc.GenericConfigEventHandler(sc, drivers, rpcmgr)
        return agent, sc

    def _test_handle_event(self, ev):
        """ Test handle event method of generic config agent for various
        device configuration operations.

        :param ev: fake event data which has to be actually sent by
        process framework.

        Returns: None

        """

        agent, sc = self._get_GenericConfigEventHandler_object()
        with mock.patch.object(cfg, 'CONF') as mock_cfg:
            mock_cfg.configure_mock(rest_timeout='30', host='foo')
            driver = fw_dvr.FwaasDriver()

        with mock.patch.object(
                driver, 'configure_interfaces') as mock_config_inte, \
            mock.patch.object(
                driver, 'clear_interfaces') as mock_clear_inte, \
            mock.patch.object(
                driver, 'configure_routes') as mock_config_src_routes, \
            mock.patch.object(
                driver, 'clear_routes') as mock_delete_src_routes, \
            mock.patch.object(
                sc, 'poll_event') as mock_hm_poll_event, \
            mock.patch.object(
                sc, 'poll_event_done') as mock_hm_poll_event_done, \
            mock.patch.object(
                driver, 'configure_healthmonitor', return_value='SUCCESS'), \
            mock.patch.object(
                agent, '_get_driver', return_value=driver):

            if 'CONFIGURE_HEALTHMONITOR' in ev.id:
                ev.id, periodicity = ev.id.split()

            agent.handle_event(ev)

            kwargs = self.fo._fake_kwargs()
            kwargs.pop('request_info')
            if ev.id == 'CONFIGURE_INTERFACES':
                mock_config_inte.assert_called_with(
                                        self.empty, kwargs)
            elif ev.id == 'CLEAR_INTERFACES':
                mock_clear_inte.assert_called_with(
                                        self.empty, kwargs)
            elif ev.id == 'CONFIGURE_ROUTES':
                mock_config_src_routes.assert_called_with(
                            self.empty, kwargs)
            elif ev.id == 'CLEAR_ROUTES':
                mock_delete_src_routes.assert_called_with(
                            self.empty, kwargs)
            elif 'CONFIGURE_HEALTHMONITOR' in ev.id:
                if periodicity == gen_cfg_const.INITIAL_HM_RETRIES:
                    mock_hm_poll_event.assert_called_with(
                                ev, max_times=gen_cfg_const.INITIAL_HM_RETRIES)
                elif periodicity == gen_cfg_const.FOREVER:
                    mock_hm_poll_event.assert_called_with(ev)
            elif ev.id == 'CLEAR_HEALTHMONITOR':
                mock_hm_poll_event_done.assert_called_with(ev)

    def _test_handle_periodic_event(self, ev):
        """ Test handle periodic event method of generic config agent
        for healthmonitor configuration.

        :param ev: fake event data which has to be actually sent by
        process framewrok.

        Returns: None

        """

        agent, sc = self._get_GenericConfigEventHandler_object()
        with mock.patch.object(cfg, 'CONF') as mock_cfg:
            mock_cfg.configure_mock(rest_timeout='30', host='foo')
            driver = fw_dvr.FwaasDriver()
        with mock.patch.object(
                agent, '_get_driver', return_value=driver), \
            mock.patch.object(
                    driver, 'configure_healthmonitor',
                    return_value='SUCCESS'), \
            mock.patch.object(
                sc, 'poll_event_done') as mock_poll_event_done, \
            mock.patch.object(subprocess, 'check_output', return_value=True):

            agent.handle_configure_healthmonitor(ev)
            mock_poll_event_done.assert_called_with(ev)

    def test_configure_interfaces_genericconfigeventhandler(self):
        """ Implements test case for configure interfaces method
        of generic config event handler.

        Returns: none

        """

        ev = fo.FakeEvent()
        ev.id = 'CONFIGURE_INTERFACES'
        self._test_handle_event(ev)

    def test_clear_interfaces_genericconfigeventhandler(self):
        """ Implements test case for clear interfaces method
        of generic config event handler.

        Returns: none

        """

        ev = fo.FakeEvent()
        ev.id = 'CLEAR_INTERFACES'
        self._test_handle_event(ev)

    def test_configure_routes_genericconfigeventhandler(self):
        """ Implements test case for configure routes method
        of generic config event handler.

        Returns: none

        """

        ev = fo.FakeEvent()
        ev.id = 'CONFIGURE_ROUTES'
        self._test_handle_event(ev)

    def test_clear_routes_genericconfigeventhandler(self):
        """ Implements test case for clear routes method
        of generic config event handler.

        Returns: none

        """

        ev = fo.FakeEvent()
        ev.id = 'CLEAR_ROUTES'
        self._test_handle_event(ev)

    def test_configure_hm_initial_genericconfigeventhandler(self):
        """ Implements test case for configure health monitor method
         with specified polling in generic config event handler.

        Returns: none

        """

        ev = fo.FakeEvent()
        ev.id = 'CONFIGURE_HEALTHMONITOR initial'
        self._test_handle_event(ev)

    def test_configure_hm_forever_genericconfigeventhandler(self):
        """ Implements test case for configure health monitor method
        with forever polling in generic config event handler.

        Returns: none

        """

        ev = fo.FakeEvent()
        ev.data['kwargs'].update({'periodicity': gen_cfg_const.FOREVER})
        ev.id = 'CONFIGURE_HEALTHMONITOR forever'
        self._test_handle_event(ev)

    def test_clear_hm_genericconfigeventhandler(self):
        """ Implements test case for clear health monitor method
        of generic config event handler.

        Returns: none

        """

        ev = fo.FakeEvent()
        ev.id = 'CLEAR_HEALTHMONITOR'
        self._test_handle_event(ev)

    def test_handle_configure_healthmonitor_genericconfigeventhandler(self):
        """ Implements test case for handle configure health monitor
         method of generic config event handler.

        Returns: none

        """

        ev = fo.FakeEvent()
        ev.id = 'CONFIGURE_HEALTHMONITOR'
        self._test_handle_periodic_event(ev)


if __name__ == '__main__':
    unittest.main()
