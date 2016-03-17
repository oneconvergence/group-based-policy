
import json
import mock
import requests
import subprocess
import unittest

from oslo_log import log as logging

from gbpservice.nfp.modules import configurator as cfgr
from gbpservice.nfp.configurator.agents import firewall as fw
from gbpservice.nfp.configurator.agents import generic_config as gc
from gbpservice.nfp.configurator.drivers.firewall.vyos import (
                                                    vyos_fw_driver as fw_dvr)
from gbpservice.nfp.configurator.lib import demuxer as demuxer_lib
from gbpservice.nfp.configurator.lib import (
                                    generic_config_constants as gen_cfg_const)

LOG = logging.getLogger(__name__)

STATUS_ACTIVE = "ACTIVE"

""" Implements fake objects for assertion.

"""


class FakeObjects(object):
    sc = 'sc'
    empty_dict = {}
    context = {'notification_data': {},
               'resource': 'interfaces'}
    firewall = 'firewall'
    host = 'host'
    conf = 'conf'
    kwargs = {'vmid': 'vmid'}
    rpcmgr = 'rpcmgr'
    drivers = 'drivers'
    vm_mgmt_ip = '172.24.4.5'
    service_vendor = 'service_vendor'
    source_cidrs = ['1.2.3.4/24']
    destination_cidr = 'destination_cidr'
    gateway_ip = '1.2.3.4'
    provider_interface_position = 'provider_interface_position'
    url = 'http://172.24.4.5:8888'
    url_for_add_inte = "%s/add_rule" % url
    url_for_del_inte = "%s/delete_rule" % url
    url_for_add_src_route = "%s/add-source-route" % url
    url_for_del_src_route = "%s/delete-source-route" % url
    url_for_config_fw = "%s/configure-firewall-rule" % url
    url_for_update_fw = "%s/update-firewall-rule" % url
    url_for_delete_fw = "%s/delete-firewall-rule" % url
    data = '{"stitching_mac": "00:0a:95:9d:68:25", "provider_mac": "00:0a:95:9d:68:16"}'
    data_for_interface = '{"stitching_mac": "00:0a:95:9d:68:25", "provider_mac": "00:0a:95:9d:68:16"}'
    data_for_add_src_route = '[{"source_cidr": "1.2.3.4/24", "gateway_ip": "1.2.3.4"}]'
    data_for_del_src_route = '[{"source_cidr": "1.2.3.4/24"}]'
    timeout = 30

    def fake_request_data_generic_bulk(self):
        """ A sample bulk request data for generic APIs

        Returns: data which is the input for generic configuration
        RPC receivers of configurator.

        """

        request_data = {
            "info": {
                "version": 1
            },
            "config": [{
                "resource": "interfaces",
                "kwargs": {
                    "stitching_mac": None,
                    "context": {
                        "domain": None},
                    "mgmt_ip": "120.0.0.15",
                    "service_vendor": "vyos",
                    "request_info": {
                        "network_function_id": (
                                    "5084bb63-459f-4edd-a090-97168764e632"),
                        "network_function_device_id": (
                                    "9b7f6b15-3e67-4f26-8463-b4efb36cbb08"),
                        "network_function_instance_id": (
                                    "940dcdf3-77c8-4119-9f95-ec1e16a50fa8")
                    },
                    "provider_mac": "fa:16:3e:0f:0f:06",
                    "provider_interface_position": 2,
                    "stitching_cidr": None,
                    "provider_ip": "11.0.0.1",
                    "stitching_interface_position": 3,
                    "provider_cidr": "11.0.0.0/24",
                    "stitching_ip": None
                }
            }, {
                "resource": "routes",
                "kwargs": {
                    "mgmt_ip": "120.0.0.15",
                    "service_vendor": "vyos",
                    "request_info": {
                        "network_function_id": (
                                    "5084bb63-459f-4edd-a090-97168764e632"),
                        "network_function_device_id": (
                                    "9b7f6b15-3e67-4f26-8463-b4efb36cbb08"),
                        "network_function_instance_id": (
                                    "940dcdf3-77c8-4119-9f95-ec1e16a50fa8")
                    },
                    "provider_interface_position": 2,
                    "gateway_ip": None,
                    "destination_cidr": None,
                    "context": {
                        "domain": None},
                    "source_cidrs": ["11.0.0.0/24"]
                }
            }]
        }
        return request_data

    def fake_request_data_generic_single(self):
        """ A sample single request data for generic APIs

        Returns: data which is the input for generic configuration
        RPC receivers of configurator.

        """

        request_data = self.fake_request_data_generic_bulk()
        request_data['config'].pop()
        return request_data

    def fake_request_data_fw(self):
        """ A sample request data for FwaaS APIs

        Returns: data which is the input for firewall configuration
        RPC receivers of configurator.

        """

        request_data = {
            "info": {
                "version": 1,
                "service_type": 'firewall'
            },
            "config": [{
                "resource": "firewall",
                "kwargs": {
                    "context": self.context,
                    "firewall": self._fake_firewall_obj(),
                    "host": self.host
                    }}]}
        return request_data

    def fake_sa_req_list(self):
        """ A sample data for agent handlers

        Returns: data which is the input for event handler
        functions of agents.

        """

        sa_req_list = [{
            'service_type': 'generic',
            'resource': 'interfaces',
            'method': 'configure_interfaces',
            'context': {
                'domain': None
            },
            'kwargs': {
                'kwargs': {
                    'stitching_mac': None,
                    'service_vendor': 'vyos',
                    'provider_interface_position': 2,
                    'provider_ip': '11.0.0.1',
                    'stitching_interface_position': 3,
                    'stitching_ip': None,
                    'mgmt_ip': '120.0.0.15',
                    'stitching_cidr': None,
                    'request_info': {
                        'network_function_id': (
                                    '5084bb63-459f-4edd-a090-97168764e632'),
                        'network_function_device_id': (
                                    '9b7f6b15-3e67-4f26-8463-b4efb36cbb08'),
                        'network_function_instance_id': (
                                    '940dcdf3-77c8-4119-9f95-ec1e16a50fa8')
                    },
                    'provider_mac': 'fa:16:3e:0f:0f:06',
                    'provider_cidr': '11.0.0.0/24'
                }
            }
        }, {
            'service_type': 'generic',
            'resource': 'routes',
            'method': 'configure_routes',
            'context': {
                'domain': None
            },
            'kwargs': {
                'kwargs': {
                    'provider_interface_position': 2,
                    'gateway_ip': None,
                    'destination_cidr': None,
                    'mgmt_ip': '120.0.0.15',
                    'source_cidrs': ['11.0.0.0/24'],
                    'service_vendor': 'vyos',
                    'request_info': {
                        'network_function_id': (
                                    '5084bb63-459f-4edd-a090-97168764e632'),
                        'network_function_device_id': (
                                    '9b7f6b15-3e67-4f26-8463-b4efb36cbb08'),
                        'network_function_instance_id': (
                                    '940dcdf3-77c8-4119-9f95-ec1e16a50fa8')
                    }
                }
            }
        }]
        return sa_req_list

    def _fake_kwargs(self):
        """ A sample keyword arguments for configurator

        Returns: kwargs

        """

        kwargs = {'service_type': 'firewall',
                  'vm_mgmt_ip': '172.24.4.5',
                  'mgmt_ip': '172.24.4.5',
                  'source_cidrs': ['1.2.3.4/24'],
                  'destination_cidr': ['1.2.3.4/24'],
                  'gateway_ip': '1.2.3.4',
                  'provider_interface_position': '1',
                  'request_info': 'some_id',
                  'periodicity': 'initial',
                  'rule_info': {
                        'active_provider_mac': '00:0a:95:9d:68:16',
                        'provider_mac': '00:0a:95:9d:68:16',
                        'active_stitching_mac': '00:0a:95:9d:68:25',
                        'stitching_mac': '00:0a:95:9d:68:25',
                        'active_fip': '172.24.4.5',
                        'fip': '172.24.4.5',
                        'service_id': '1df1cd7a-d82e-4bbd-8b26-a1f106075a6b',
                        'tenant_id': '6bb921bb81254b3e90e3d8c71a6d72dc'},
                  'context': {'notification_data': 'hello'}
                  }
        return kwargs

    def _fake_firewall_obj(self):
        """ A sample firewall resource object

        Returns: firewall object

        """

        firewall = {
                     "admin_state_up": True,
                     "description": "",
                     "firewall_policy_id": (
                                "c69933c1-b472-44f9-8226-30dc4ffd454c"),
                     "id": "3b0ef8f4-82c7-44d4-a4fb-6177f9a21977",
                     "name": "",
                     "status": "PENDING_CREATE",
                     "router_ids": [
                         "650bfd2f-7766-4a0d-839f-218f33e16998"
                     ],
                     "tenant_id": "45977fa2dbd7482098dd68d0d8970117",
                     "firewall_rule_list": True,
                     "description": '{\
                                    "vm_management_ip": "172.24.4.5",\
                                    "service_vendor": "vyos"}',
                     "firewall_rule_list": True
                    }
        return firewall

""" Tests RPC manager class of configurator

"""


class ConfiguratorRpcManagerTestCase(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(ConfiguratorRpcManagerTestCase, self).__init__(*args, **kwargs)
        self.fo = FakeObjects()

    @mock.patch(__name__ + '.FakeObjects.conf')
    @mock.patch(__name__ + '.FakeObjects.sc')
    def _get_ConfiguratorRpcManager_object(self, sc, conf):
        """ Retrieves RPC manager object of configurator.

        :param sc: mocked service controller object of process model framework
        :param conf: mocked OSLO configuration file

        Returns: object of configurator's RPC manager.

        """

        cm = cfgr.ConfiguratorModule(sc)
        demuxer = demuxer_lib.ServiceAgentDemuxer()
        rpc_mgr = cfgr.ConfiguratorRpcManager(sc, cm, conf, demuxer)
        return sc, conf, rpc_mgr

    def _get_GenericConfigRpcManager_object(self, conf, sc):
        """ Retrieves RPC manager object of generic config agent.

        :param sc: mocked service controller object of process model framework
        :param conf: mocked OSLO configuration file

        Returns: object of generic config's RPC manager
        and service controller.

        """

        agent = gc.GenericConfigRpcManager(sc, conf)
        return agent, sc

    @mock.patch(__name__ + '.FakeObjects.drivers')
    def _get_GenericConfigEventHandler_object(self, sc, rpcmgr, drivers):
        """ Retrieves event handler object of generic configuration.

        :param sc: mocked service controller object of process model framework
        :param rpcmgr: object of configurator's RPC manager
        :param drivers: list of driver objects for firewall agent

        Returns: object of generic config's event handler

        """

        agent = gc.GenericConfigEventHandler(sc, drivers, rpcmgr)
        return agent

    def _get_FWaasRpcManager_object(self, conf, sc):
        """ Retrieves RPC manager object of firewall agent.

        :param sc: mocked service controller object of process model framework
        :param conf: mocked OSLO configuration file

        Returns: object of firewall's RPC manager and service controller

        """

        agent = fw.FWaasRpcManager(sc, conf)
        return agent, sc

    def _test_network_device_config(self, operation, method, batch=False):
        """ Tests generic config APIs

        :param operation: create/delete
        :param method: CONFIGURE_ROUTES/CLEAR_ROUTES/
        CONFIGURE_INTERFACES/CLEAR_INTERFACES
        :param batch: True or False. Indicates if the
        request is a batch request

        Returns: none

        """

        sc, conf, rpc_mgr = self._get_ConfiguratorRpcManager_object()
        agent, sc = self._get_GenericConfigRpcManager_object(conf, sc)

        request_data = {'batch': {
                'request_data_actual': (
                            self.fo.fake_request_data_generic_bulk()),
                'request_data_expected': (
                            self.fo.fake_request_data_generic_bulk())},
                        'single': {
                'request_data_actual': (
                            self.fo.fake_request_data_generic_single()),
                'request_data_expected': (
                            self.fo.fake_request_data_generic_single())}
                        }
        if batch:
            request_data_actual, request_data_expected = (
                                            request_data['batch'].values())
        else:
            request_data_actual, request_data_expected = (
                                            request_data['single'].values())

        if 'ROUTES' in method:
            request_data_expected['config'][0]['resource'] = 'routes'
            request_data_actual['config'][0]['resource'] = 'routes'

        with mock.patch.object(
                    sc, 'new_event', return_value='foo') as mock_sc_event, \
            mock.patch.object(sc, 'post_event') as mock_sc_rpc_event, \
            mock.patch.object(rpc_mgr,
                              '_get_service_agent_instance',
                              return_value=agent):
            if operation == 'create':
                rpc_mgr.create_network_function_device_config(
                                    self.fo.context, request_data_actual)
            elif operation == 'delete':
                rpc_mgr.delete_network_function_device_config(
                                    self.fo.context, request_data_actual)

            context = request_data_expected['config'][0]['kwargs'][
                                                                    'context']
            context.update({'notification_data': {}})
            context.update(
                    {'resource': request_data_expected['config'][0][
                                                                'resource']})
            del request_data_expected['config'][0]['kwargs']['context']
            kwargs = request_data_expected['config'][0]['kwargs']
            if batch:
                sa_req_list = self.fo.fake_sa_req_list()
                if operation == 'delete':
                    sa_req_list[0]['method'] = 'clear_interfaces'
                    sa_req_list[1]['method'] = 'clear_routes'
                args_dict = {
                         'sa_req_list': sa_req_list,
                         'notification_data': {}
                        }
            else:
                args_dict = {'context': context,
                             'kwargs': kwargs}
            mock_sc_event.assert_called_with(id=method,
                                             data=args_dict, key=None)
            mock_sc_rpc_event.assert_called_with('foo')

    def _test_fw_event_creation(self, operation):
        """ Tests firewall APIs

        :param operation: CREATE_FIREWALL/UPDATE_FIREWALL/DELETE_FIREWALL

        Returns: none

        """

        sc, conf, rpc_mgr = self._get_ConfiguratorRpcManager_object()
        agent, sc = self._get_FWaasRpcManager_object(conf, sc)
        arg_dict = {'context': self.fo.context,
                    'firewall': self.fo._fake_firewall_obj(),
                    'host': self.fo.host}
        method = {'CREATE_FIREWALL': 'create_network_function_config',
                  'UPDATE_FIREWALL': 'update_network_function_config',
                  'DELETE_FIREWALL': 'delete_network_function_config'}
        request_data = self.fo.fake_request_data_fw()
        with mock.patch.object(sc, 'new_event', return_value='foo') as (
                                                        mock_sc_event), \
            mock.patch.object(sc, 'post_event') as mock_sc_rpc_event, \
            mock.patch.object(rpc_mgr,
                              '_get_service_agent_instance',
                              return_value=agent):
            getattr(rpc_mgr, method[operation])(self.fo.context, request_data)

            mock_sc_event.assert_called_with(id=operation,
                                             data=arg_dict, key=None)
            mock_sc_rpc_event.assert_called_with('foo')

    def _test_notifications(self):
        """ Tests response path notification  APIs

        Returns: none

        """

        sc, conf, rpc_mgr = self._get_ConfiguratorRpcManager_object()
        agent = self._get_GenericConfigEventHandler_object(sc, rpc_mgr)

        data = "PUT ME IN THE QUEUE!"
        with mock.patch.object(sc, 'new_event', return_value='foo') as (
                                                            mock_new_event), \
            mock.patch.object(sc, 'poll_event') as mock_poll_event:

            agent.notify._notification(data)

            mock_new_event.assert_called_with(id='NOTIFICATION_EVENT',
                                              key='NOTIFICATION_EVENT',
                                              data=data)
            mock_poll_event.assert_called_with('foo')

    def test_configure_routes_configurator_api(self):
        """ Implements test case for configure routes API

        Returns: none

        """

        method = "CONFIGURE_ROUTES"
        operation = 'create'
        self._test_network_device_config(operation, method)

    def test_clear_routes_configurator_api(self):
        """ Implements test case for clear routes API

        Returns: none

        """

        method = "CLEAR_ROUTES"
        operation = 'delete'
        self._test_network_device_config(operation, method)

    def test_configure_interfaces_configurator_api(self):
        """ Implements test case for configure interfaces API

        Returns: none

        """

        method = "CONFIGURE_INTERFACES"
        operation = 'create'
        self._test_network_device_config(operation, method)

    def test_clear_interfaces_configurator_api(self):
        """ Implements test case for clear interfaces API

        Returns: none

        """

        method = "CLEAR_INTERFACES"
        operation = 'delete'
        self._test_network_device_config(operation, method)

    def test_configure_bulk_configurator_api(self):
        """ Implements test case for bulk configure request API

        Returns: none

        """

        method = "PROCESS_BATCH"
        operation = 'create'
        self._test_network_device_config(operation, method, True)

    def test_clear_bulk_configurator_api(self):
        """ Implements test case for bulk clear request API

        Returns: none

        """

        method = "PROCESS_BATCH"
        operation = 'delete'
        self._test_network_device_config(operation, method, True)

    def test_create_firewall_configurator_api(self):
        """ Implements test case for create firewall API

        Returns: none

        """

        self._test_fw_event_creation('CREATE_FIREWALL')

    def test_update_firewall_configurator_api(self):
        """ Implements test case for update firewall API

        Returns: none

        """

        self._test_fw_event_creation('UPDATE_FIREWALL')

    def test_delete_firewall_configurator_api(self):
        """ Implements test case for delete firewall API

        Returns: none

        """

        self._test_fw_event_creation('DELETE_FIREWALL')

    def test_get_notifications_generic_configurator_api(self):
        """ Implements test case for get notifications API
        of configurator

        Returns: none

        """

        self._test_notifications()

""" Implement test cases for RPC manager methods of firewall agent.

"""


class FWaasRpcManagerTestCase(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(FWaasRpcManagerTestCase, self).__init__(*args, **kwargs)
        self.fo = FakeObjects()

    @mock.patch(__name__ + '.FakeObjects.sc')
    @mock.patch(__name__ + '.FakeObjects.conf')
    def _get_FWaasRpcManager_object(self, conf, sc):
        """ Retrieves RPC manager object of firewall agent.

        :param sc: mocked service controller object of process model framework
        :param conf: mocked OSLO configuration file

        Returns: object of firewall's RPC manager and service controller

        """

        agent = fw.FWaasRpcManager(sc, conf)
        return agent, sc

    def _test_event_creation(self, method):
        """ Tests event creation and enqueueing for create/update/delete
        operation of firewall agent's RPC manager.

        Returns: none

        """

        agent, sc = self._get_FWaasRpcManager_object()
        arg_dict = {'context': self.fo.context,
                    'firewall': self.fo.firewall,
                    'host': self.fo.host}
        with mock.patch.object(sc, 'new_event', return_value='foo') as (
                                                        mock_sc_event), \
            mock.patch.object(sc, 'post_event') as mock_sc_rpc_event:
            call_method = getattr(agent, method.lower())
            call_method(self.fo.context, self.fo.firewall, self.fo.host)

            mock_sc_event.assert_called_with(id=method,
                                             data=arg_dict, key=None)
            mock_sc_rpc_event.assert_called_with('foo')

    def test_create_firewall_fwaasrpcmanager(self):
        """ Implements test case for create firewall method
        of firewall agent's RPC manager.

        Returns: none

        """

        self._test_event_creation('CREATE_FIREWALL')

    def test_update_firewall_fwaasrpcmanager(self):
        """ Implements test case for update firewall method
        of firewall agent's RPC manager.

        Returns: none

        """

        self._test_event_creation('UPDATE_FIREWALL')

    def test_delete_firewall_fwaasrpcmanager(self):
        """ Implements test case for delete firewall method
        of firewall agent's RPC manager.

        Returns: none

        """

        self._test_event_creation('DELETE_FIREWALL')

""" Implement test cases for RPC manager methods of generic config agent.

"""


class GenericConfigRpcManagerTestCase(unittest.TestCase):
    ''' Generic Config RPC receiver for Firewall module '''

    def __init__(self, *args, **kwargs):
        super(GenericConfigRpcManagerTestCase, self).__init__(
                                                        *args, **kwargs)
        self.fo = FakeObjects()

    @mock.patch(__name__ + '.FakeObjects.sc')
    @mock.patch(__name__ + '.FakeObjects.conf')
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

""" Implements a fake event class for process framework to use

"""


class FakeEvent(object):
    def __init__(self):
        fo = FakeObjects()
        kwargs = fo._fake_kwargs()
        self.data = {
                    'context': {'notification_data': {},
                                'resource': 'firewall'},
                    'firewall': fo._fake_firewall_obj(),
                    'host': fo.host,
                    'kwargs': kwargs,
                    'vm_mgmt_ip': fo.vm_mgmt_ip,
                    'service_vendor': fo.service_vendor,
                    'source_cidrs': fo.source_cidrs,
                    'destination_cidr': fo.destination_cidr,
                    'gateway_ip': fo.gateway_ip,
                    'provider_interface_position': (
                                        fo.provider_interface_position)}
        self.id = 'dummy'

""" Implements test cases for event handler methods
of generic config agent.

"""


class GenericConfigEventHandlerTestCase(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(GenericConfigEventHandlerTestCase, self).__init__(
                                                        *args, **kwargs)
        self.fo = FakeObjects()
        self.empty = self.fo.empty_dict
        self.context = {'notification_data': {},
                        'resource': 'interfaces'}

    @mock.patch(__name__ + '.FakeObjects.rpcmgr')
    @mock.patch(__name__ + '.FakeObjects.drivers')
    @mock.patch(__name__ + '.FakeObjects.sc')
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
            elif ev.id == 'CONFIGURE_HEALTHMONITOR':
                ev.id = ev.id.split()[0]
                periodicity = ev.id.split()[1]
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

        ev = FakeEvent()
        ev.id = 'CONFIGURE_INTERFACES'
        self._test_handle_event(ev)

    def test_clear_interfaces_genericconfigeventhandler(self):
        """ Implements test case for clear interfaces method
        of generic config event handler.

        Returns: none

        """

        ev = FakeEvent()
        ev.id = 'CLEAR_INTERFACES'
        self._test_handle_event(ev)

    def test_configure_routes_genericconfigeventhandler(self):
        """ Implements test case for configure routes method
        of generic config event handler.

        Returns: none

        """

        ev = FakeEvent()
        ev.id = 'CONFIGURE_ROUTES'
        self._test_handle_event(ev)

    def test_clear_routes_genericconfigeventhandler(self):
        """ Implements test case for clear routes method
        of generic config event handler.

        Returns: none

        """

        ev = FakeEvent()
        ev.id = 'CLEAR_ROUTES'
        self._test_handle_event(ev)

    def test_configure_hm_initial_genericconfigeventhandler(self):
        """ Implements test case for configure health monitor method
         with specified polling in generic config event handler.

        Returns: none

        """

        ev = FakeEvent()
        ev.id = 'CONFIGURE_HEALTHMONITOR initial'
        self._test_handle_event(ev)

    def test_configure_hm_forever_genericconfigeventhandler(self):
        """ Implements test case for configure health monitor method
        with forever polling in generic config event handler.

        Returns: none

        """

        ev = FakeEvent()
        ev.data['kwargs'].update({'periodicity': gen_cfg_const.FOREVER})
        ev.id = 'CONFIGURE_HEALTHMONITOR forever'
        self._test_handle_event(ev)

    def test_clear_hm_genericconfigeventhandler(self):
        """ Implements test case for clear health monitor method
        of generic config event handler.

        Returns: none

        """

        ev = FakeEvent()
        ev.id = 'CLEAR_HEALTHMONITOR'
        self._test_handle_event(ev)

    def test_handle_configure_healthmonitor_genericconfigeventhandler(self):
        """ Implements test case for handle configure health monitor
         method of generic config event handler.

        Returns: none

        """

        ev = FakeEvent()
        ev.id = 'CONFIGURE_HEALTHMONITOR'
        self._test_handle_periodic_event(ev)

""" Implements test cases for event handler methods
of firewall agent.

"""


class FwaasHandlerTestCase(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(FwaasHandlerTestCase, self).__init__(*args, **kwargs)
        self.fo = FakeObjects()
        self.ev = FakeEvent()

    @mock.patch(__name__ + '.FakeObjects.rpcmgr')
    @mock.patch(__name__ + '.FakeObjects.drivers')
    @mock.patch(__name__ + '.FakeObjects.sc')
    def _get_FwHandler_objects(self, sc, drivers, rpcmgr):
        """ Retrieves event handler object of firewall agent.

        :param sc: mocked service controller object of process model framework
        :param drivers: list of driver objects for firewall agent
        :param rpcmgr: object of configurator's RPC manager

        Returns: object of firewall agents's event handler

        """

        agent = fw.FWaasEventHandler(sc, drivers, rpcmgr)
        return agent

    def _test_handle_event(self, rule_list_info=True):
        """ Test handle event method of firewall agent for various
        device configuration operations.

        :param rule_list_info: an atrribute of firewall resource object
        sent from plugin which contains the firewall rules.

        Returns: None

        """

        agent = self._get_FwHandler_objects()
        driver = fw_dvr.FwaasDriver()

        with mock.patch.object(
             agent.plugin_rpc, 'set_firewall_status') as (
                                                    mock_set_fw_status), \
            mock.patch.object(
                agent.plugin_rpc, 'firewall_deleted') as (mock_fw_deleted), \
            mock.patch.object(
                driver, 'create_firewall') as mock_create_fw, \
            mock.patch.object(
                driver, 'update_firewall') as mock_update_fw, \
            mock.patch.object(
                driver, 'delete_firewall') as mock_delete_fw, \
            mock.patch.object(
                agent, '_get_driver', return_value=driver):

            firewall = self.fo._fake_firewall_obj()
            if not rule_list_info:
                firewall.update({'firewall_rule_list': False})
                self.ev.data.get('firewall').update(
                                            {'firewall_rule_list': False})
            else:
                self.ev.data.get('firewall').update(
                                            {'firewall_rule_list': True})

            agent.handle_event(self.ev)
            if not rule_list_info:
                if self.ev.id == 'CREATE_FIREWALL':
                    mock_set_fw_status.assert_called_with(
                            self.fo.context,
                            firewall['id'], STATUS_ACTIVE)
                elif self.ev.id == 'UPDATE_FIREWALL':
                    mock_set_fw_status.assert_called_with(
                            self.fo.context,
                            firewall['id'], STATUS_ACTIVE)
                elif self.ev.id == 'DELETE_FIREWALL':
                    mock_fw_deleted.assert_called_with(
                            self.fo.context, firewall['id'])
            else:
                if self.ev.id == 'CREATE_FIREWALL':
                    mock_create_fw.assert_called_with(
                            self.fo.context,
                            firewall, self.fo.host)
                elif self.ev.id == 'UPDATE_FIREWALL':
                    mock_update_fw.assert_called_with(
                            self.fo.context,
                            firewall, self.fo.host)
                elif self.ev.id == 'DELETE_FIREWALL':
                    mock_delete_fw.assert_called_with(
                            self.fo.context,
                            firewall, self.fo.host)

    def test_create_firewall_with_rule_list_info_true(self):
        """ Implements test case for create firewall method
        of firewall agent's event handler with firewall rules.

        Returns: none

        """

        self.ev.id = 'CREATE_FIREWALL'
        self._test_handle_event()

    def test_update_firewall_with_rule_list_info_true(self):
        """ Implements test case for update firewall method
        of firewall agent's event handler with firewall rules.

        Returns: none

        """

        self.ev.id = 'UPDATE_FIREWALL'
        self._test_handle_event()

    def test_delete_firewall_with_rule_list_info_true(self):
        """ Implements test case for delete firewall method
        of firewall agent's event handler with firewall rules.

        Returns: none

        """

        self.ev.id = 'DELETE_FIREWALL'
        self._test_handle_event()

    def test_create_firewall_with_rule_list_info_false(self):
        """ Implements test case for create firewall method
        of firewall agent's event handler without firewall rules.

        Returns: none

        """

        self.ev.id = 'CREATE_FIREWALL'
        self._test_handle_event(False)

    def test_update_firewall_with_rule_list_info_false(self):
        """ Implements test case for update firewall method
        of firewall agent's event handler without firewall rules.

        Returns: none

        """

        self.ev.id = 'UPDATE_FIREWALL'
        self._test_handle_event(False)

    def test_delete_firewall_with_rule_list_info_false(self):
        """ Implements test case for delete firewall method
        of firewall agent's event handler without firewall rules.

        Returns: none

        """

        self.ev.id = 'DELETE_FIREWALL'
        self._test_handle_event(False)

""" Implements test cases for driver methods
of generic config.

"""


class FwGenericConfigDriverTestCase(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(FwGenericConfigDriverTestCase, self).__init__(*args, **kwargs)
        self.fo = FakeObjects()
        self.driver = fw_dvr.FwGenericConfigDriver()
        self.resp = mock.Mock()
        self.fake_resp_dict = {'status': True}
        self.kwargs = self.fo._fake_kwargs()

    def test_configure_interfaces(self):
        """ Implements test case for configure interfaces method
        of generic config driver.

        Returns: none

        """

        with mock.patch.object(
                requests, 'post', return_value=self.resp) as mock_post, \
             mock.patch.object(
                self.resp, 'json', return_value=self.fake_resp_dict):
            self.driver.configure_interfaces(self.fo.context, self.kwargs)

            mock_post.assert_called_with(self.fo.url_for_add_inte,
                                         self.fo.data_for_interface,
                                         timeout=self.fo.timeout)

    def test_clear_interfaces(self):
        """ Implements test case for clear interfaces method
        of generic config driver.

        Returns: none

        """

        self.resp = mock.Mock(status_code=200)
        with mock.patch.object(
                requests, 'delete', return_value=self.resp) as mock_delete, \
            mock.patch.object(
                self.resp, 'json', return_value=self.fake_resp_dict):
            self.driver.clear_interfaces(self.fo.context, self.kwargs)

            mock_delete.assert_called_with(
                                self.fo.url_for_del_inte,
                                data=self.fo.data_for_interface,
                                timeout=self.fo.timeout)

    def test_configure_source_routes(self):
        """ Implements test case for configure routes method
        of generic config driver.

        Returns: none

        """

        with mock.patch.object(
                requests, 'post', return_value=self.resp) as mock_post, \
             mock.patch.object(
                self.resp, 'json', return_value=self.fake_resp_dict):
            self.driver.configure_routes(
                self.fo.context, self.kwargs)

            mock_post.assert_called_with(self.fo.url_for_add_src_route,
                                         data=self.fo.data_for_add_src_route,
                                         timeout=60)

    def test_delete_source_routes(self):
        """ Implements test case for clear routes method
        of generic config driver.

        Returns: none

        """

        with mock.patch.object(
                requests, 'delete', return_value=self.resp) as mock_delete, \
             mock.patch.object(
                self.resp, 'json', return_value=self.fake_resp_dict):
            self.driver.clear_routes(
                self.fo.context, self.kwargs)

            mock_delete.assert_called_with(
                                self.fo.url_for_del_src_route,
                                data=self.fo.data_for_del_src_route,
                                timeout=self.fo.timeout)

""" Implements test cases for driver methods
of firewall.

"""


class FwaasDriverTestCase(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(FwaasDriverTestCase, self).__init__(*args, **kwargs)
        self.fo = FakeObjects()
        self.driver = fw_dvr.FwaasDriver()
        self.resp = mock.Mock()
        self.fake_resp_dict = {'status': True,
                               'config_success': True,
                               'delete_success': True}
        self.fo.firewall = self.fo._fake_firewall_obj()
        self.firewall = json.dumps(self.fo.firewall)

    def test_create_firewall_fwaasdriver(self):
        """ Implements test case for create firewall method
        of firewall's drivers.

        Returns: none

        """

        with mock.patch.object(
                requests, 'post', return_value=self.resp) as mock_post, \
             mock.patch.object(
                self.resp, 'json', return_value=self.fake_resp_dict):
            self.driver.create_firewall(self.fo.context,
                                        self.fo.firewall, self.fo.host)
            mock_post.assert_called_with(self.fo.url_for_config_fw,
                                         self.firewall, timeout=30)

    def test_create_firewall_key_error_fwaasdriver(self):
        """ Implements test case for catching key error in
        create firewall method of firewall's drivers.

        Returns: none

        """

        self.fo.firewall.pop('description')
        with self.assertRaises(KeyError):
            self.driver.create_firewall(self.fo.context,
                                        self.fo.firewall, self.fo.host)

    def test_update_firewall_fwaasdriver(self):
        """ Implements test case for update firewall method
        of firewall's drivers.

        Returns: none

        """

        with mock.patch.object(
                requests, 'put', return_value=self.resp) as mock_put, \
             mock.patch.object(
                self.resp, 'json', return_value=self.fake_resp_dict):
            self.driver.update_firewall(self.fo.context,
                                        self.fo.firewall, self.fo.host)
            mock_put.assert_called_with(self.fo.url_for_update_fw,
                                        data=self.firewall, timeout=30)

    def test_update_firewall_key_error_fwaasdriver(self):
        """ Implements test case for catching key error in
        update firewall method of firewall's drivers.

        Returns: none

        """

        self.fo.firewall.pop('description')
        with self.assertRaises(KeyError):
            self.driver.update_firewall(self.fo.context,
                                        self.fo.firewall, self.fo.host)

    def test_delete_firewall_fwaasdriver(self):
        """ Implements test case for delete firewall method
        of firewall's drivers.

        Returns: none

        """

        with mock.patch.object(
                requests, 'delete', return_value=self.resp) as mock_delete, \
             mock.patch.object(
                self.resp, 'json', return_value=self.fake_resp_dict):
            self.driver.delete_firewall(self.fo.context,
                                        self.fo.firewall, self.fo.host)
            mock_delete.assert_called_with(self.fo.url_for_delete_fw,
                                           data=self.firewall, timeout=30)

    def test_delete_firewall_key_error_fwaasdriver(self):
        """ Implements test case for catching key error in
        delete firewall method of firewall's drivers.

        Returns: none

        """

        self.fo.firewall.pop('description')
        with self.assertRaises(KeyError):
            self.driver.delete_firewall(self.fo.context,
                                        self.fo.firewall, self.fo.host)


if __name__ == '__main__':
    unittest.main()
