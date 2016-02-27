import requests
import unittest
import mock
import json

from oslo_config import cfg
from oslo_log import log as logging
import oslo_messaging

from neutron.common import rpc as n_rpc

from gbpservice.nfp.configurator.agents import firewall as fw
from gbpservice.nfp.configurator.agents import generic_config as gc
from gbpservice.nfp.configurator.drivers.firewall.\
                            vyos.vyos_fw_driver import FwaasDriver
from gbpservice.nfp.configurator.drivers.firewall.\
                            vyos.vyos_fw_driver import FwGenericConfigDriver



LOG = logging.getLogger(__name__)

FIREWALL_RPC_TOPIC = "firewall_topic"
FIREWALL_GENERIC_CONFIG_RPC_TOPIC = "vyos_firewall_topic"
HOST = 'configurator-dpak'
STATUS_ACTIVE = "ACTIVE"


class FakeObjects(object):
    sc = 'sc'
    context = {'notification_data': {},
               'resource': 'interfaces'}
    firewall = 'firewall'
    host = 'host'
    conf = 'conf'
    kwargs = 'kwargs'
    rpcmgr = 'rpcmgr'
    nqueue = 'nqueue'
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

    def _fake_kwargs(self):
        kwargs = {'service_type': 'firewall',
                  'vm_mgmt_ip': '172.24.4.5',
                  'mgmt_ip': '172.24.4.5',
                  'source_cidrs': ['1.2.3.4/24'],
                  'destination_cidr': ['1.2.3.4/24'],
                  'gateway_ip': '1.2.3.4',
                  'provider_interface_position': '1',
                  'request_info': 'some_id',
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
                     'description': {
                                    "vm_management_ip": "172.24.4.5",
                                    "service_vendor": "vyos"},
                     'firewall_rule_list': True
                    }
        return firewall

    def fake_request_data_generic_config(self):
        data = {
                'context': {},
                'kwargs': self._fake_kwargs(),
                'request_info': 'xxx'}

        request_data = {
                 'info':   {
                             'version': 'v1'},

                 'config': [
                        {'resource': 'interfaces',
                         'kwargs': data}
                    ]
                }

        return request_data


class FWaasRpcManagerTestCase(unittest.TestCase):
    ''' Fwaas RPC receiver for Firewall module '''

    def __init__(self, *args, **kwargs):
        super(FWaasRpcManagerTestCase, self).__init__(*args, **kwargs)
        self.fo = FakeObjects()

    @mock.patch(__name__ + '.FakeObjects.sc')
    @mock.patch(__name__ + '.FakeObjects.conf')
    def _get_FWaasRpcManager_object(self, conf, sc):
        agent = fw.FWaasRpcManager(sc, conf)
        return agent, sc

    def _test_event_creation(self, method):
        agent, sc = self._get_FWaasRpcManager_object()
        arg_dict = {'context': self.fo.context,
                    'firewall': self.fo.firewall,
                    'host': self.fo.host}
        with mock.patch.object(sc, 'new_event', return_value='foo') as (
                                                        mock_sc_event), \
            mock.patch.object(sc, 'post_event') as mock_sc_rpc_event:
            call_method = getattr(agent, method.lower())
            call_method(self.fo.context, self.fo.firewall, self.fo.host)

            mock_sc_event.assert_called_with(id=method, data=arg_dict)
            mock_sc_rpc_event.assert_called_with('foo')

    def test_create_firewall_fwaasrpcmanager(self):
        ''' create_firewall method in RPC Receiver '''
        self._test_event_creation('CREATE_FIREWALL')

    def test_update_firewall_fwaasrpcmanager(self):
        ''' update_firewall method in RPC Receiver '''
        self._test_event_creation('UPDATE_FIREWALL')

    def test_delete_firewall_fwaasrpcmanager(self):
        ''' delete_firewall method in RPC Receiver '''
        self._test_event_creation('DELETE_FIREWALL')


class GenericConfigRpcManagerTestCase(unittest.TestCase):
    ''' Generic Config RPC receiver for Firewall module '''

    def __init__(self, *args, **kwargs):
        super(GenericConfigRpcManagerTestCase, self).__init__(
                                                        *args, **kwargs)
        self.fo = FakeObjects()

    @mock.patch(__name__ + '.FakeObjects.sc')
    @mock.patch(__name__ + '.FakeObjects.conf')
    def _get_GenericConfigRpcManager_object(self, conf, sc):
        agent = gc.GenericConfigRpcManager(sc, conf)
        return agent, sc

    def _test_event_creation(self, method):
        agent, sc = self._get_GenericConfigRpcManager_object()
        arg_dict = {'context': self.fo.context,
                    'kwargs': self.fo.kwargs}
        with mock.patch.object(
                    sc, 'new_event', return_value='foo') as mock_sc_event, \
            mock.patch.object(sc, 'post_event') as mock_sc_rpc_event:
            call_method = getattr(agent, method.lower())

            if method == 'CONFIGURE_INTERFACES':
                call_method(self.fo.context, self.fo.kwargs)
            elif method == 'CLEAR_INTERFACES':
                call_method(self.fo.context, self.fo.kwargs)
            elif method == 'CONFIGURE_ROUTES':
                call_method(self.fo.context, self.fo.kwargs)
            elif method == 'CLEAR_ROUTES':
                call_method(self.fo.context, self.fo.kwargs)

            mock_sc_event.assert_called_with(id=method, data=arg_dict)
            mock_sc_rpc_event.assert_called_with('foo')

    def test_configure_interfaces_genericconfigrpcmanager(self):
        ''' configure_interfaces method in RPC Receiver '''
        self._test_event_creation('CONFIGURE_INTERFACES')

    def test_clear_interfaces_genericconfigrpcmanager(self):
        ''' clear_interfaces method in RPC Receiver '''
        self._test_event_creation('CLEAR_INTERFACES')

    def test_configure_source_routes_genericconfigrpcmanager(self):
        ''' configure_source_routes method in RPC Receiver '''
        self._test_event_creation('CONFIGURE_ROUTES')

    def test_delete_source_routes_genericconfigrpcmanager(self):
        ''' delete_source_routes method in RPC Receiver '''
        self._test_event_creation('CLEAR_ROUTES')


class FakeEvent(object):
    def __init__(self):
        self.fo = FakeObjects()
        kwargs = self.fo._fake_kwargs()
        self.data = {
                    'context': self.fo.context,
                    'firewall': self.fo._fake_firewall_obj(),
                    'host': self.fo.host,
                    'kwargs': kwargs,
                    'vm_mgmt_ip': self.fo.vm_mgmt_ip,
                    'service_vendor': self.fo.service_vendor,
                    'source_cidrs': self.fo.source_cidrs,
                    'destination_cidr': self.fo.destination_cidr,
                    'gateway_ip': self.fo.gateway_ip,
                    'provider_interface_position': (
                                        self.fo.provider_interface_position)}
        self.id = 'dummy'


class GenericConfigEventHandlerTestCase(unittest.TestCase):
    ''' Generic Config Handler for Firewall module '''

    def __init__(self, *args, **kwargs):
        super(GenericConfigEventHandlerTestCase, self).__init__(
                                                        *args, **kwargs)
        self.fo = FakeObjects()
        self.ev = FakeEvent()

    @mock.patch(__name__ + '.FakeObjects.nqueue')
    @mock.patch(__name__ + '.FakeObjects.rpcmgr')
    @mock.patch(__name__ + '.FakeObjects.drivers')
    @mock.patch(__name__ + '.FakeObjects.sc')
    def _get_GenericConfigEventHandler_object(self, sc,
                                              drivers, rpcmgr, nqueue):
        agent = gc.GenericConfigEventHandler(sc, drivers, rpcmgr, nqueue)
        return agent

    def _test_handle_event(self):
        agent = self._get_GenericConfigEventHandler_object()
        driver = FwGenericConfigDriver()
        with mock.patch.object(
                driver, 'configure_interfaces') as mock_config_inte, \
             mock.patch.object(
                driver, 'clear_interfaces') as mock_clear_inte, \
             mock.patch.object(
                driver, 'configure_routes') as mock_config_src_routes, \
             mock.patch.object(
                driver, 'clear_routes') as mock_delete_src_routes, \
             mock.patch.object(
                agent, '_get_driver', return_value=driver):
            self.ev.data.update({'context': self.fo.context})
	    import pdb;pdb.set_trace()
            agent.handle_event(self.ev)

            kwargs = self.fo._fake_kwargs()
            kwargs.pop('request_info')
            if self.ev.id == 'CONFIGURE_INTERFACES':
                mock_config_inte.assert_called_with(
                                        self.fo.context, kwargs)
            elif self.ev.id == 'CLEAR_INTERFACES':
                mock_clear_inte.assert_called_with(
                                        self.fo.context, kwargs)
            elif self.ev.id == 'CONFIGURE_ROUTES':
                mock_config_src_routes.assert_called_with(
                            self.fo.context, kwargs)
            elif self.ev.id == 'CLEAR_ROUTES':
                mock_delete_src_routes.delete_source_routes(
                            self.fo.context, kwargs)

    def test_configure_interfaces_genericconfigeventhandler(self):
        ''' Handle event for configure_interfaces '''
        self.ev.id = 'CONFIGURE_INTERFACES'
        self._test_handle_event()

    def test_clear_interfaces_genericconfigeventhandler(self):
        ''' Handle event for clear_interfaces '''
        self.ev.id = 'CLEAR_INTERFACES'
        self._test_handle_event()

    def test_configure_source_routes_genericconfigeventhandler(self):
        ''' Handle event for configure_source_routes '''
        self.ev.id = 'CONFIGURE_ROUTES'
        self._test_handle_event()

    def test_delete_source_routes_genericconfigeventhandler(self):
        ''' Handle event for delete_source_routes '''
        self.ev.id = 'CLEAR_ROUTES'
        self._test_handle_event()


"""
class FwaasHandlerTestCase(unittest.TestCase):
    ''' Generic Config Handler for Firewall module '''

    def __init__(self, *args, **kwargs):
        super(FwaasHandlerTestCase, self).__init__(*args, **kwargs)
        self.fo = FakeObjects()
        self.ev = FakeEvent()

    @mock.patch(__name__ + '.FakeObjects.nqueue')
    @mock.patch(__name__ + '.FakeObjects.rpcmgr')
    @mock.patch(__name__ + '.FakeObjects.drivers')
    @mock.patch(__name__ + '.FakeObjects.sc')
    def _get_FwHandler_objects(self, sc, drivers, rpcmgr, nqueue):
        agent = fw.FWaasEventHandler(sc, drivers, rpcmgr, nqueue)
        return agent

    def _test_handle_event(self, rule_list_info=True):
        agent = self._get_FwHandler_objects()
        driver = FwaasDriver()

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
        ''' Handle event for create_firewall '''
        self.ev.id = 'CREATE_FIREWALL'
        self._test_handle_event()

    def test_update_firewall_with_rule_list_info_true(self):
        ''' Handle event for update_firewall '''
        self.ev.id = 'UPDATE_FIREWALL'
        self._test_handle_event()

    def test_delete_firewall_with_rule_list_info_true(self):
        ''' Handle event for delete_firewall '''
        self.ev.id = 'DELETE_FIREWALL'
        self._test_handle_event()

    def test_create_firewall_with_rule_list_info_false(self):
        ''' Handle event for create_firewall '''
        self.ev.id = 'CREATE_FIREWALL'
        self._test_handle_event(False)

    def test_update_firewall_with_rule_list_info_false(self):
        ''' Handle event for update_firewall '''
        self.ev.id = 'UPDATE_FIREWALL'
        self._test_handle_event(False)

    def test_delete_firewall_with_rule_list_info_false(self):
        ''' Handle event for delete_firewall '''
        self.ev.id = 'DELETE_FIREWALL'
        self._test_handle_event(False)


class FwGenericConfigDriverTestCase(unittest.TestCase):
    ''' Generic Config Driver for Firewall module '''

    def __init__(self, *args, **kwargs):
        super(FwGenericConfigDriverTestCase, self).__init__(*args, **kwargs)
        self.fo = FakeObjects()
        self.driver = FwGenericConfigDriver()
        self.resp = mock.Mock()
        self.fake_resp_dict = {'status': True}
        self.kwargs = self.fo._fake_kwargs()

    def test_configure_interfaces(self):
        with mock.patch.object(
                requests, 'post', return_value=self.resp) as mock_post, \
             mock.patch.object(
                self.resp, 'json', return_value=self.fake_resp_dict):
            self.driver.configure_interfaces(self.fo.context, self.kwargs)

            mock_post.assert_called_with(self.fo.url_for_add_inte,
                                         self.fo.data_for_interface,
                                         timeout=self.fo.timeout)

    def test_configure_interfaces_key_error(self):
        self.kwargs['rule_info'].pop('active_fip')
        with self.assertRaises(KeyError):
            self.driver.configure_interfaces(self.fo.context, self.kwargs)

    def test_clear_interfaces(self):
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

    def test_clear_interfaces_key_error(self):
        self.kwargs['rule_info'].pop('fip')
        with self.assertRaises(KeyError):
            self.driver.clear_interfaces(self.fo.context, self.kwargs)

    def test_configure_source_routes(self):
        with mock.patch.object(
                requests, 'post', return_value=self.resp) as mock_post, \
             mock.patch.object(
                self.resp, 'json', return_value=self.fake_resp_dict):
            self.driver.configure_source_routes(
                self.fo.context, self.kwargs)

            mock_post.assert_called_with(self.fo.url_for_add_src_route,
                                         data=self.fo.data_for_add_src_route,
                                         timeout=60)

    def test_delete_source_routes(self):
        with mock.patch.object(
                requests, 'delete', return_value=self.resp) as mock_delete, \
             mock.patch.object(
                self.resp, 'json', return_value=self.fake_resp_dict):
            self.driver.delete_source_routes(
                self.fo.context, self.kwargs)

            mock_delete.assert_called_with(
                                self.fo.url_for_del_src_route,
                                data=self.fo.data_for_del_src_route,
                                timeout=self.fo.timeout)


class FwaasDriverTestCase(unittest.TestCase):
    ''' Fwaas Driver for Firewall module '''

    def __init__(self, *args, **kwargs):
        super(FwaasDriverTestCase, self).__init__(*args, **kwargs)
        self.fo = FakeObjects()
        self.driver = FwaasDriver()
        self.resp = mock.Mock()
        self.fake_resp_dict = {'status': True,
                               'config_success': True,
                               'delete_success': True}
        self.fo.firewall = self.fo._fake_firewall_obj()
        self.firewall = json.dumps(self.fo.firewall)

    def test_create_firewall_fwaasdriver(self):
        with mock.patch.object(
                requests, 'post', return_value=self.resp) as mock_post, \
             mock.patch.object(
                self.resp, 'json', return_value=self.fake_resp_dict):
            self.driver.create_firewall(self.fo.context,
                                        self.fo.firewall, self.fo.host)
            mock_post.assert_called_with(self.fo.url_for_config_fw,
                                         self.firewall, timeout=30)

    def test_create_firewall_key_error_fwaasdriver(self):
        self.fo.firewall.pop('description')
        with self.assertRaises(KeyError):
            self.driver.create_firewall(self.fo.context,
                                        self.fo.firewall, self.fo.host)

    def test_update_firewall_fwaasdriver(self):
        with mock.patch.object(
                requests, 'put', return_value=self.resp) as mock_put, \
             mock.patch.object(
                self.resp, 'json', return_value=self.fake_resp_dict):
            self.driver.update_firewall(self.fo.context,
                                        self.fo.firewall, self.fo.host)
            mock_put.assert_called_with(self.fo.url_for_update_fw,
                                        data=self.firewall, timeout=30)

    def test_update_firewall_key_error_fwaasdriver(self):
        self.fo.firewall.pop('description')
        with self.assertRaises(KeyError):
            self.driver.update_firewall(self.fo.context,
                                        self.fo.firewall, self.fo.host)

    def test_delete_firewall_fwaasdriver(self):
        with mock.patch.object(
                requests, 'delete', return_value=self.resp) as mock_delete, \
             mock.patch.object(
                self.resp, 'json', return_value=self.fake_resp_dict):
            self.driver.delete_firewall(self.fo.context,
                                        self.fo.firewall, self.fo.host)
            mock_delete.assert_called_with(self.fo.url_for_delete_fw,
                                           data=self.firewall, timeout=30)

    def test_delete_firewall_key_error_fwaasdriver(self):
        self.fo.firewall.pop('description')
        with self.assertRaises(KeyError):
            self.driver.delete_firewall(self.fo.context,
                                        self.fo.firewall, self.fo.host)
"""

if __name__ == '__main__':
    unittest.main()
