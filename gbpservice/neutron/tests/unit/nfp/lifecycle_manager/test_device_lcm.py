import sys
import unittest
import mock
import copy
from mock import patch

from gbpservice.nfp.lifecycle_manager.modules import (
    device_lifecycle_manager)
from gbpservice.nfp.lifecycle_manager.drivers import (
    lifecycle_driver_base)
from gbpservice.nfp.lifecycle_manager.drivers import (
    haproxy_lifecycle_driver)
from gbpservice.nfp.db import api as db_api
from gbpservice.nfp.db import nfp_db as nfpdb


class DummyEvent():
    def __init__(self, data, status, ref_count=0):
        self.data = {}
        self.data['status'] = status
        self.data['id'] = 'vm-id'

        self.data['network_function_id'] = 'network_function_id'
        self.data['network_function_instance_id'] = (
            'network_function_instance_id')
        self.data['ports'] = [{'id': 'myid1',
                     'port_model': 'neutron',
                     'port_classification': 'management',
                     'port_role': 'active'},]
        self.data['mgmt_port_id'] = [
                        {'id': 'myid1',
                         'port_model': 'neutron',
                         'port_classification': 'management',
                         'port_role': 'active'},
                        ]
        self.data['interfaces_in_use'] = 1
        self.data['reference_count'] = ref_count


param_req = {'param1': 'value1', 'param2': 'value2'}

haproxy_driver = haproxy_lifecycle_driver.HaproxyLifeCycleDriver()
LIFECYCLE_MANAGER_CLASS_PATH = ('gbpservice.nfp.lifecycle_manager'
                                 '.modules.device_lifecycle_manager')
LIFECYCLE_DRIVER_CLASS_PATH = ('gbpservice.nfp.lifecycle_manager'
                                 '.drivers.lifecycle_driver_base')


class DeviceLCModuleTestCase(unittest.TestCase):
    @mock.patch.object(device_lifecycle_manager, 'events_init')
    @mock.patch.object(device_lifecycle_manager, 'rpc_init')
    def test_module_init(self, mock_rpc_init, mock_events_init):
         controller = "dummy-controller"
         config = "dummy-config"
         device_lifecycle_manager.module_init(controller, config)
         mock_events_init.assert_called_once_with(controller, config)
         mock_rpc_init.assert_called_once_with(controller, config)


    def test_rpc_init(self):
        controller = mock.Mock()
        config = mock.Mock()
        device_lifecycle_manager.rpc_init(controller, config)
        controller.register_rpc_agents.assert_called_once_with(mock.ANY)
        call_args, call_kwargs = controller.register_rpc_agents.call_args
        self.assertEqual(1, len(call_args[0]))
        self.assertIsInstance(call_args[0][0],
                              device_lifecycle_manager.RpcAgent)

    def test_events_init(self):
        controller = mock.Mock()
        config = mock.Mock()
        device_lifecycle_manager.events_init(
            controller, config)
        controller.register_events.assert_called_once_with(mock.ANY)


class DeviceLCMRpcHandlerTestCase():

    def setUp(self):
        super(DeviceLCMRpcHandlerTestCase, self).setUp()
        self.controller = mock.Mock()
        self.config = mock.Mock()
        self.rpc_handler = device_lifecycle_manager.RpcHandler(self.config,
                                                               self.controller)

    @mock.patch.object(device_lifecycle_manager.DeviceLifeCycleHandler,
                       "get_network_function_config_info")
    def test_rpc_create_network_function(self,
                                         mock_get_network_function_config_info):
        self.rpc_response = {'notification_data': {
                                    'kwargs': [{'resource': 'healthmonitor',
                                                'kwargs': {'result': 'success',
                                                'device_id': 'dev-id'}}]
                            }}
        self.rpc_handler.get_network_function_config_info("context",
                                                          rpc_response)
        event_id = 'DEVICE_HEALTHY'
        event_data = {'device_id': 'dev-id'}
        self.controller._create_event.assert_called_once_with(event_id=event_id,
                                                        event_data=event_data)
        self.rpc_handler.get_network_function_config_info.assert_called_once_with(
            "context", rpc_response)


@patch(LIFECYCLE_MANAGER_CLASS_PATH + '.DLCMConfiguratorRpcApi.__init__',
        mock.MagicMock(return_value=None))
class DeviceLCMRpcApiTestCase(unittest.TestCase):

    def setUp(self):
        super(DeviceLCMRpcApiTestCase, self).setUp()
        self.controller = mock.Mock()
        self.config = mock.Mock()

    def test_create_network_function_device_config(self):
        self.rpc_handler = device_lifecycle_manager.DLCMConfiguratorRpcApi(
            'context')
        self.rpc_handler.context = 'context'
        self.rpc_handler.rpc_api = mock.MagicMock(return_value=True)
        device_data = 'device_data'
        config_params = {'param1': 'value1'}
        self.rpc_handler.create_network_function_device_config(device_data,
                                                               config_params)
        self.rpc_handler.rpc_api.cast.assert_called_once_with(
            self.rpc_handler.context, 'create_network_function_device_config',
            config_params=config_params)

    def test_delete_network_function_device_config(self):
        self.rpc_handler = device_lifecycle_manager.DLCMConfiguratorRpcApi(
            'context')
        self.rpc_handler.context = 'context'
        self.rpc_handler.rpc_api = mock.MagicMock(return_value=True)
        device_data = 'device_data'
        config_params = {'param1': 'value1'}
        self.rpc_handler.delete_network_function_device_config(device_data,
                                                               config_params)
        self.rpc_handler.rpc_api.cast.assert_called_once_with(
            self.rpc_handler.context, 'delete_network_function_device_config',
            config_params=config_params)




@patch(LIFECYCLE_MANAGER_CLASS_PATH + '.DeviceLifeCycleHandler._create_event',
        mock.MagicMock(return_value=True))
@patch(LIFECYCLE_MANAGER_CLASS_PATH +
        '.DeviceLifeCycleHandler._get_vendor_lifecycle_driver',
        mock.MagicMock(return_value=haproxy_driver))
@patch(LIFECYCLE_MANAGER_CLASS_PATH + '.DLCMConfiguratorRpcApi.__init__',
        mock.MagicMock(return_value=None))
@patch(LIFECYCLE_DRIVER_CLASS_PATH + '.LifeCycleDriverBase.__init__',
        mock.MagicMock(return_value=param_req))
class DeviceLifeCycleHandlerTestCase(unittest.TestCase):

    def _initialize_dlcm_handler(self):
        dlcm_handler = device_lifecycle_manager.DeviceLifeCycleHandler(
                object, object)
        self.event = DummyEvent(100, 'PENDING_CREATE')
        return dlcm_handler

    @mock.patch.object(device_lifecycle_manager.DeviceLifeCycleHandler,
            'device_configuration_complete')
    def test_handle_event(self, mock_device_configuration_complete):
        dlcm_mgr = device_lifecycle_manager.DeviceLifeCycleManager(object,
                                                                   object)
        mock_device_configuration_complete.return_value = True
        self.event = DummyEvent(100, 'DEVICE_CONFIGURED')
        self.event.id = 'DEVICE_CONFIGURED'

        dlcm_mgr.handle_event(self.event)
        mock_device_configuration_complete.assert_called_with(self.event)

    @mock.patch.object(nfpdb.NFPDbBase, 'update_network_function_device')
    def test_check_device_up(self, mock_update_nsd):
        dlcm_handler = self._initialize_dlcm_handler()
        dlcm_handler._controller = mock.MagicMock(return_value='')
        mock_update_nsd.return_value = 100
        orig_event_data = copy.deepcopy(self.event.data)

        dlcm_handler.lifecycle_driver.get_network_function_device_status = (
                mock.MagicMock(return_value='ACTIVE'))
        status = 'DEVICE_UP'
        orig_event_data['status'] = status
        orig_event_data['status_description'] = dlcm_handler.state_map[status]

        dlcm_handler.check_device_is_up(self.event)
        mock_update_nsd.assert_called_with(dlcm_handler.db_session,
                                           orig_event_data['id'],
                                           orig_event_data)

        dlcm_handler.lifecycle_driver.get_network_function_device_status = (
                mock.MagicMock(return_value='ERROR'))
        status = 'DEVICE_NOT_UP'
        orig_event_data['status'] = status
        orig_event_data['status_description'] = dlcm_handler.state_map[status]

        dlcm_handler.check_device_is_up(self.event)
        mock_update_nsd.assert_called_with(dlcm_handler.db_session,
                                           orig_event_data['id'],
                                           orig_event_data)

    @mock.patch.object(nfpdb.NFPDbBase, 'update_network_function_device')
    def test_health_check(self, mock_update_nsd):
        dlcm_handler = self._initialize_dlcm_handler()
        mock_update_nsd.return_value = 100
        orig_event_data = copy.deepcopy(self.event.data)

        dlcm_handler.configurator_rpc.create_network_function_device_config = (
            mock.MagicMock(return_value=101))
        dlcm_handler.lifecycle_driver.get_network_function_device_healthcheck_info = (
            mock.MagicMock(return_value=param_req))

        status = 'HEALTH_CHECK_PENDING'
        orig_event_data['status'] = status
        orig_event_data['status_description'] = dlcm_handler.state_map[status]

        dlcm_handler.perform_health_check(self.event)
        mock_update_nsd.assert_called_with(dlcm_handler.db_session,
                                           orig_event_data['id'],
                                           orig_event_data)
        dlcm_handler.configurator_rpc.create_network_function_device_config.assert_called_with(
            orig_event_data, param_req)

    @mock.patch.object(nfpdb.NFPDbBase, 'update_network_function_device')
    def test_plug_interfaces(self, mock_update_nsd):
        dlcm_handler = self._initialize_dlcm_handler()

        mock_update_nsd.return_value = 100
        orig_event_data = copy.deepcopy(self.event.data)
        orig_event_data['status_description'] = ''

        dlcm_handler.lifecycle_driver.plug_network_function_device_interfaces = (
            mock.MagicMock(return_value=True))
        dlcm_handler._create_event = mock.MagicMock(return_value=True)

        orig_event_data['interfaces_in_use'] += len(orig_event_data['ports'])

        dlcm_handler.plug_interfaces(self.event)
        mock_update_nsd.assert_called_with(dlcm_handler.db_session,
                                           orig_event_data['id'],
                                           orig_event_data)

        dlcm_handler.lifecycle_driver.plug_network_function_device_interfaces = (
            mock.MagicMock(return_value=False))
        dlcm_handler._create_event = mock.MagicMock(return_value=True)
        event_id = 'DEVICE_CONFIGURATION_FAILED'

        dlcm_handler.plug_interfaces(self.event)
        dlcm_handler._create_event.assert_called_with(event_id=event_id,
                                             event_data=orig_event_data)

    @mock.patch.object(nfpdb.NFPDbBase, 'update_network_function_device')
    def test_create_device_configuration(self, mock_update_nsd):
        dlcm_handler = self._initialize_dlcm_handler()
        device = self.event.data
        config_params = {'param1': 'value1', 'parama2': 'value2'}
        dlcm_handler.lifecycle_driver.get_network_function_device_config_info = (
            mock.MagicMock(return_value=config_params))
        dlcm_handler.configurator_rpc.create_network_function_device_config = (
                mock.MagicMock(return_value=True))

        dlcm_handler.create_device_configuration(self.event)
        dlcm_handler.configurator_rpc.create_network_function_device_config.assert_called_with(
                device, config_params)

    @mock.patch.object(nfpdb.NFPDbBase, 'update_network_function_device')
    def test_device_configuration_complete(self,
                                           mock_update_nsd):
        dlcm_handler = self._initialize_dlcm_handler()
        device = self.event.data

        dlcm_handler._create_event = mock.MagicMock(return_value=True)
        orig_event_data = copy.deepcopy(self.event.data)
        status = 'ACTIVE'
        orig_event_data['status'] = status
        orig_event_data['status_description'] = dlcm_handler.state_map[status]
        orig_event_data['reference_count'] += 1

        dlcm_handler.device_configuration_complete(self.event)
        mock_update_nsd.assert_called_with(dlcm_handler.db_session,
                                           orig_event_data['id'],
                                           orig_event_data)

        event_id = 'DEVICE_ACTIVE'
        device_created_data = {
                'network_function_id' : orig_event_data['network_function_id'],
                'network_function_instance_id' : (
                    orig_event_data['network_function_instance_id']),
                'network_function_device_id' : orig_event_data['id'],
                }
        dlcm_handler._create_event.assert_called_with(event_id=event_id,
                                             event_data=device_created_data)

    @mock.patch.object(nfpdb.NFPDbBase, 'get_network_function_device')
    @mock.patch.object(nfpdb.NFPDbBase, 'update_network_function_device')
    @mock.patch.object(nfpdb.NFPDbBase, 'get_port_info')
    def test_delete_network_function_device(self, mock_get_port,
                                            mock_update_nsd, mock_get_nsd):
        dlcm_handler = self._initialize_dlcm_handler()
        delete_event_req = DummyEvent(100, 'ACTIVE')
        delete_event_req.data = {'network_function_device_id': 'device-id',
                'network_function_instance': {'id': 'nfi-id', 'port_info': []}}

        mgmt_port_id = {'id': 'port-id', 'port_model': 'port-policy'}
        mock_get_port.return_value = mgmt_port_id
        mock_get_nsd.return_value = {'id': 'device-id',
                                     'mgmt_port_id': ['mgmt-data-port-id']}

        event_id = 'DELETE_CONFIGURATION'
        event_data = {'id': 'device-id', 'mgmt_port_id': [mgmt_port_id],
                      'compute_policy': 'nova',
                      'network_model': 'port-policy',
                      'network_function_instance_id': 'nfi-id',
                      'ports': []}
        dlcm_handler._create_event = mock.MagicMock(return_value=True)

        dlcm_handler.delete_network_function_device(delete_event_req)
        dlcm_handler._create_event.assert_called_with(event_id=event_id,
                                             event_data=event_data)

    @mock.patch.object(nfpdb.NFPDbBase, 'update_network_function_device')
    def test_delete_device_configuration(self, mock_update_nsd):
        dlcm_handler = self._initialize_dlcm_handler()
        config_params = {'param1': 'value1', 'parama2': 'value2'}
        self.event = DummyEvent(101, 'ACTIVE')
        dlcm_handler.lifecycle_driver.get_network_function_device_config_info = (
            mock.MagicMock(return_value=config_params))
        dlcm_handler.configurator_rpc.delete_network_function_device_config = (
                mock.MagicMock(return_value=True))

        dlcm_handler.delete_device_configuration(self.event)
        dlcm_handler.configurator_rpc.delete_network_function_device_config.assert_called_with(
            self.event.data, config_params)

    @mock.patch.object(nfpdb.NFPDbBase, 'update_network_function_device')
    def test_unplug_interfaces(self, mock_update_nsd):

        dlcm_handler = self._initialize_dlcm_handler()
        self.event = DummyEvent(101, 'ACTIVE')
        orig_event_data = copy.deepcopy(self.event.data)
        orig_event_data['status_description'] = dlcm_handler.state_map['ACTIVE']
        dlcm_handler.lifecycle_driver.unplug_network_function_device_interfaces = (
            mock.MagicMock(return_value=True))

        dlcm_handler.unplug_interfaces(self.event)

        orig_event_data['interfaces_in_use'] -= len(orig_event_data['ports'])
        mock_update_nsd.assert_called_with(dlcm_handler.db_session,
                                           orig_event_data['id'],
                                           orig_event_data)

        self.event = DummyEvent(101, 'ACTIVE')
        event_data = copy.deepcopy(self.event.data)
        orig_event_data['status_description'] = dlcm_handler.state_map['ACTIVE']

        dlcm_handler.lifecycle_driver.unplug_network_function_device_interfaces = (
            mock.MagicMock(return_value=True))

        dlcm_handler.unplug_interfaces(self.event)
        mock_update_nsd.assert_called_with(dlcm_handler.db_session,
                                           orig_event_data['id'],
                                           orig_event_data)

    @mock.patch.object(nfpdb.NFPDbBase, 'delete_network_function_device')
    def test_device_delete(self, mock_delete_nsd):
        dlcm_handler = self._initialize_dlcm_handler()
        self.event = DummyEvent(101, 'ACTIVE', 1)
        orig_event_data = copy.deepcopy(self.event.data)
        dlcm_handler.lifecycle_driver.delete_network_function_device = (
            mock.MagicMock(return_value=True))
        dlcm_handler._create_event = mock.MagicMock(return_value=True)

        dlcm_handler.delete_device(self.event)

        event_id = 'DEVICE_DELETED'
        orig_event_data['reference_count'] -= 1
        #status = 'PENDING_DELETE'
        #orig_event_data['status'] = event_id
        #orig_event_data['status_description'] = dlcm_handler.state_map[status]

        mock_delete_nsd.assert_called_with(dlcm_handler.db_session,
                                           self.event.data['id'])
        dlcm_handler._create_event.assert_called_with(event_id=event_id,
                                             event_data=orig_event_data)

    @mock.patch.object(nfpdb.NFPDbBase, 'update_network_function_device')
    def test_handle_device_error(self, mock_update_nsd):
        dlcm_handler = self._initialize_dlcm_handler()
        status = 'ERROR'
        desc = 'Internal Server Error'
        self.event = DummyEvent(101, status, 1)
        orig_event_data = copy.deepcopy(self.event.data)
        orig_event_data['status_description'] = desc
        orig_event_data['network_function_device_id'] = orig_event_data['id']
        dlcm_handler._create_event = mock.MagicMock(return_value=True)

        dlcm_handler.handle_device_error(self.event)
        mock_update_nsd.assert_called_with(dlcm_handler.db_session,
                                            orig_event_data['id'],
                                            orig_event_data)

    @mock.patch.object(nfpdb.NFPDbBase, 'update_network_function_device')
    def test_handle_device_not_up(self, mock_update_nsd):
        dlcm_handler = self._initialize_dlcm_handler()
        status = 'ERROR'
        desc = 'Device not became ACTIVE'
        self.event = DummyEvent(101, status, 1)
        orig_event_data = copy.deepcopy(self.event.data)
        orig_event_data['status_description'] = desc
        dlcm_handler._create_event = mock.MagicMock(return_value=True)

        dlcm_handler.handle_device_not_up(self.event)
        orig_event_data['network_function_device_id'] = orig_event_data['id']
        mock_update_nsd.assert_called_with(dlcm_handler.db_session,
                                                  orig_event_data['id'],
                                                        orig_event_data)

    @mock.patch.object(nfpdb.NFPDbBase, 'update_network_function_device')
    def test_handle_device_not_reachable(self, mock_update_nsd):
        dlcm_handler = self._initialize_dlcm_handler()
        status = 'ERROR'
        self.event = DummyEvent(101, status, 1)
        orig_event_data = copy.deepcopy(self.event.data)
        desc = 'Device not reachable, Health Check Failed'
        orig_event_data['status_description'] = desc
        dlcm_handler._create_event = mock.MagicMock(return_value=True)

        dlcm_handler.handle_device_not_reachable(self.event)
        orig_event_data['network_function_device_id'] = orig_event_data['id']
        mock_update_nsd.assert_called_with(dlcm_handler.db_session,
                                                  orig_event_data['id'],
                                                        orig_event_data)

    @mock.patch.object(nfpdb.NFPDbBase, 'update_network_function_device')
    def test_handle_device_config_failed(self, mock_update_nsd):
        dlcm_handler = self._initialize_dlcm_handler()
        status = 'DEVICE_CONFIG_FAILED'
        desc = 'Configuring Device Failed.'
        self.event = DummyEvent(101, status, 1)
        orig_event_data = copy.deepcopy(self.event.data)
        orig_event_data['status_description'] = desc
        dlcm_handler._create_event = mock.MagicMock(return_value=True)

        dlcm_handler.handle_device_config_failed(self.event)
        orig_event_data['network_function_device_id'] = orig_event_data['id']
        mock_update_nsd.assert_called_with(dlcm_handler.db_session,
                                                  orig_event_data['id'],
                                                        orig_event_data)


def main():
    unittest.main()

if __name__ == '__main__':
    main()


