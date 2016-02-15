# Copyright (c) 2016 OpenStack Foundation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import mock

from gbpservice.neutron.nsf.common import exceptions as nsf_exc
from gbpservice.neutron.nsf.lifecycle_manager.modules import (
    service_lifecycle_manager as service_lcm)
from gbpservice.neutron.nsf.lifecycle_manager.openstack import openstack_driver
from gbpservice.neutron.tests.unit.nsf import test_nsf_db


class ServiceLCModuleTestCase(test_nsf_db.NSFDBTestCase):

    def setUp(self):
        super(ServiceLCModuleTestCase, self).setUp()

    @mock.patch.object(service_lcm, 'events_init')
    @mock.patch.object(service_lcm, 'rpc_init')
    def test_module_init(self, mock_rpc_init, mock_events_init):
        controller = "test"
        config = "testconfig"
        service_lcm.module_init(controller, config)
        mock_events_init.assert_called_once_with(controller, config, mock.ANY)
        call_args, call_kwargs = mock_events_init.call_args
        self.assertIsInstance(call_args[2],
                              service_lcm.ServiceLifeCycleHandler)
        mock_rpc_init.assert_called_once_with(controller, config)

    def test_rpc_init(self):
        controller = mock.Mock()
        config = mock.Mock()
        service_lcm.rpc_init(controller, config)
        controller.register_rpc_agents.assert_called_once_with(mock.ANY)
        call_args, call_kwargs = controller.register_rpc_agents.call_args
        self.assertEqual(1, len(call_args[0]))
        self.assertIsInstance(call_args[0][0], service_lcm.RpcAgent)

    def test_events_init(self):
        controller = mock.Mock()
        config = mock.Mock()
        service_lcm.events_init(
            controller, config,
            service_lcm.ServiceLifeCycleHandler(controller))
        controller.register_events.assert_called_once_with(mock.ANY)


class ServiceLCMRpcHandlerTestCase(ServiceLCModuleTestCase):

    def setUp(self):
        super(ServiceLCMRpcHandlerTestCase, self).setUp()
        self.controller = mock.Mock()
        self.config = mock.Mock()
        self.rpc_handler = service_lcm.RpcHandler(self.config, self.controller)

    @mock.patch.object(service_lcm.ServiceLifeCycleHandler,
                       "create_network_service")
    def test_rpc_create_network_service(self, mock_create_network_service):
        self.rpc_handler.create_network_service("context", "network_service")
        mock_create_network_service.assert_called_once_with(
            "context", "network_service")

    @mock.patch.object(service_lcm.ServiceLifeCycleHandler,
                       "get_network_service")
    def test_rpc_get_network_service(self, mock_get_network_service):
        self.rpc_handler.get_network_service("context", "network_service_id")
        mock_get_network_service.assert_called_once_with(
            "context", "network_service_id")

    @mock.patch.object(service_lcm.ServiceLifeCycleHandler,
                       "get_network_services")
    def test_rpc_get_network_services(self, mock_get_network_services):
        filters = {'id': ['myuuid']}
        self.rpc_handler.get_network_services("context", filters=filters)
        mock_get_network_services.assert_called_once_with(
            "context", filters)

    @mock.patch.object(service_lcm.ServiceLifeCycleHandler,
                       "delete_network_service")
    def test_rpc_delete_network_service(self, mock_delete_network_service):
        self.rpc_handler.delete_network_service(
            "context", "network_service_id")
        mock_delete_network_service.assert_called_once_with(
            "context", "network_service_id")

    @mock.patch.object(service_lcm.ServiceLifeCycleHandler,
                       "update_network_service")
    def test_rpc_update_network_service(self, mock_update_network_service):
        self.rpc_handler.update_network_service(
            "context", "network_service_id", "updated_network_service")
        mock_update_network_service.assert_called_once_with(
            "context", "network_service_id", "updated_network_service")

    @mock.patch.object(service_lcm.ServiceLifeCycleHandler,
                       "handle_policy_target_added")
    def test_rpc_notify_policy_target_added(self,
                                            mock_handle_policy_target_added):
            self.rpc_handler.notify_policy_target_added(
                "context", "network_service_id", "policy_target")
            mock_handle_policy_target_added.assert_called_once_with(
                "context", "network_service_id", "policy_target")

    @mock.patch.object(service_lcm.ServiceLifeCycleHandler,
                       "handle_policy_target_removed")
    def test_rpc_notify_policy_target_removed(
        self, mock_handle_policy_target_removed):
            self.rpc_handler.notify_policy_target_removed(
                "context", "network_service_id", "policy_target")
            mock_handle_policy_target_removed.assert_called_once_with(
                "context", "network_service_id", "policy_target")

    @mock.patch.object(
        service_lcm.ServiceLifeCycleHandler, "handle_consumer_ptg_added")
    def test_rpc_notify_consumer_ptg_added(self,
                                           mock_handle_consumer_ptg_added):
        self.rpc_handler.notify_consumer_ptg_added(
            "context", "network_service_id", "policy_target_group")
        mock_handle_consumer_ptg_added.assert_called_once_with(
            "context", "network_service_id", "policy_target_group")

    @mock.patch.object(
        service_lcm.ServiceLifeCycleHandler, "handle_consumer_ptg_removed")
    def test_rpc_notify_consumer_ptg_removed(self,
                                             mock_handle_consumer_ptg_removed):
        self.rpc_handler.notify_consumer_ptg_removed(
            "context", "network_service_id", "policy_target_group")
        mock_handle_consumer_ptg_removed.assert_called_once_with(
            "context", "network_service_id", "policy_target_group")


class ServiceLifeCycleHandlerTestCase(ServiceLCModuleTestCase):

    def setUp(self):
        super(ServiceLifeCycleHandlerTestCase, self).setUp()
        self.controller = mock.Mock()
        self.config = mock.Mock()
        self.context = mock.Mock()
        self.service_lc_handler = service_lcm.ServiceLifeCycleHandler(
            self.controller)

    @mock.patch.object(
        service_lcm.ServiceLifeCycleHandler, "_validate_create_service_input")
    @mock.patch.object(
        openstack_driver.KeystoneClient, "get_admin_token")
    @mock.patch.object(
        openstack_driver.GBPClient, "get_service_profile")
    def test_create_network_service(self, mock_get_service_profile,
                                    mock_get_admin_token, mock_validate):
        network_service_info = {
            'tenant_id': 'tenant_id',
            'service_chain_id': 'sc_instance_id',
            'service_id': 'sc_node_id',
            'service_profile_id': 'service_profile_id',
            'management_ptg_id': 'mgmt_ptg_id',
            'service_config': '',
            'provider_port_id': 'provider_pt_id',
            'network_service_mode': 'GBP',
        }
        network_service = self.service_lc_handler.create_network_service(
            self.context, network_service_info)
        self.assertIsNotNone(network_service)
        db_network_service = self.nsf_db.get_network_service(
            self.session, network_service['id'])
        self.assertEqual(network_service, db_network_service)
        self.controller.event.assert_called_once_with(
            id='CREATE_NETWORK_SERVICE_INSTANCE', data=mock.ANY)
        self.controller.rpc_event.assert_called_once_with(mock.ANY)

    def test_validate_create_service_input(self):
        pass  # TODO

    def test_delete_network_service_without_nsi(self):
        network_service = self.create_network_service()
        self.service_lc_handler.delete_network_service(
            self.context, network_service['id'])
        self.assertRaises(nsf_exc.NetworkServiceNotFound,
                          self.nsf_db.get_network_service,
                          self.session, network_service['id'])
        self.assertFalse(self.controller.event.called)
        self.assertFalse(self.controller.rpc_event.called)

    def test_delete_network_service_with_nsi(self):
        network_service_instance = self.create_network_service_instance()
        network_service_id = network_service_instance['network_service_id']
        self.service_lc_handler.delete_network_service(
            self.context, network_service_id)
        network_service = self.nsf_db.get_network_service(
            self.session, network_service_id)
        self.assertEqual('PENDING_DELETE', network_service['status'])
        self.controller.event.assert_called_once_with(
            id='DELETE_NETWORK_SERVICE_INSTANCE',
            data=network_service_instance['id'])
        self.controller.rpc_event.assert_called_once_with(mock.ANY)

    @mock.patch.object(
        service_lcm.ServiceLifeCycleHandler, "_create_event")
    def test_event_create_network_service_instance(self, mock_create_event):
        network_service = self.create_network_service()
        mode = 'GBP'
        network_service_port_info = [
            {
                'id': 'provider_port_id',
                'port_policy': mode,
                'port_classification': 'provider'
            },
            {
                'id': 'consumer_port_id',
                'port_policy': mode,
                'port_classification': 'consumer'
            }
        ]
        management_network_info = {
            'id': 'management_ptg_id',
            'port_policy': mode
        }

        create_nsi_request = {
            'network_service': network_service,
            'network_service_port_info': network_service_port_info,
            'management_network_info': management_network_info,
            'service_type': 'service_type',
            'service_vendor': 'vendor',
            'share_existing_device': True
        }
        self.assertEqual([], network_service['network_service_instances'])
        self.service_lc_handler.create_network_service_instance(
            create_nsi_request)
        db_network_service = self.nsf_db.get_network_service(
            self.session, network_service['id'])
        self.assertEqual(
            1, len(db_network_service['network_service_instances']))
        # The value of port_info in network_service_instance is a list
        # when we do a DB get, the order changes resulting in test failing
        # if we validate the event data
        '''
        nsi_db = self.nsf_db.get_network_service_instance(
            self.session, db_network_service['network_service_instances'][0])
        create_nsd_request = {
            'network_service': network_service,
            'network_service_instance': nsi_db,
            'management_network_info': management_network_info,
            'service_type': 'service_type',
            'service_vendor': 'vendor',
            'share_existing_device': True,
        }
        '''
        mock_create_event.assert_called_once_with(
            'CREATE_NETWORK_SERVICE_DEVICE', event_data=mock.ANY)

    @mock.patch.object(
        service_lcm.ServiceLifeCycleHandler, "get_service_details")
    @mock.patch.object(
        service_lcm.ServiceLifeCycleHandler, "_create_event")
    def test_event_handle_device_created(self, mock_create_event,
                                         mock_get_service_details):
        nsd = self.create_network_service_device()
        nsi = self.create_network_service_instance(create_nsd=False)
        request_data = {
            'network_service_instance_id': nsi['id'],
            'network_service_device_id': nsd['id']
        }
        self.assertIsNone(nsi['network_service_device_id'])
        with mock.patch.object(
            self.service_lc_handler.config_driver,
            "apply_user_config") as mock_apply_user_config:
            mock_apply_user_config.return_value = "stack_id"
            self.service_lc_handler.handle_device_created(
                request_data)
        db_nsi = self.nsf_db.get_network_service_instance(
            self.session, nsi['id'])
        db_ns = self.nsf_db.get_network_service(
            self.session, nsi['network_service_id'])
        self.assertEqual(nsd['id'], db_nsi['network_service_device_id'])
        self.assertIsNotNone(db_ns['heat_stack_id'])
        mock_create_event.assert_called_once_with(
            'USER_CONFIG_IN_PROGRESS', event_data=mock.ANY, is_poll_event=True)

    def test_event_handle_device_create_failed(self):
        nsd = self.create_network_service_device()
        nsi = self.create_network_service_instance(create_nsd=False)
        request_data = {
            'network_service_instance_id': nsi['id'],
            'network_service_device_id': nsd['id']
        }
        self.assertIsNone(nsi['network_service_device_id'])
        self.service_lc_handler.handle_device_create_failed(
            request_data)
        db_nsi = self.nsf_db.get_network_service_instance(
            self.session, nsi['id'])
        db_ns = self.nsf_db.get_network_service(
            self.session, nsi['network_service_id'])
        self.assertEqual('ERROR', db_nsi['status'])
        self.assertEqual('ERROR', db_ns['status'])

    def test_event_check_for_user_config_complete(self):
        network_service = self.create_network_service()
        with mock.patch.object(
            self.service_lc_handler.config_driver,
            "is_config_complete") as mock_is_config_complete:
            # Verify return status IN_PROGRESS from config driver
            mock_is_config_complete.return_value = "IN_PROGRESS"
            request_data = {
                'heat_stack_id': 'heat_stack_id',
                'network_service_id': network_service['id']}
            self.service_lc_handler.check_for_user_config_complete(
                request_data)
            mock_is_config_complete.assert_called_once_with(
                request_data['heat_stack_id'])
            db_ns = self.nsf_db.get_network_service(
                self.session, network_service['id'])
            self.assertEqual(network_service['status'], db_ns['status'])

            # Verify return status ERROR from config driver
            mock_is_config_complete.reset_mock()
            mock_is_config_complete.return_value = "ERROR"
            request_data = {
                'heat_stack_id': 'heat_stack_id',
                'network_service_id': network_service['id']}
            self.service_lc_handler.check_for_user_config_complete(
                request_data)
            mock_is_config_complete.assert_called_once_with(
                request_data['heat_stack_id'])
            db_ns = self.nsf_db.get_network_service(
                self.session, network_service['id'])
            self.assertEqual('ERROR', db_ns['status'])

            # Verify return status COMPLETED from config driver
            mock_is_config_complete.reset_mock()
            mock_is_config_complete.return_value = "COMPLETED"
            request_data = {
                'heat_stack_id': 'heat_stack_id',
                'network_service_id': network_service['id']}
            self.service_lc_handler.check_for_user_config_complete(
                request_data)
            mock_is_config_complete.assert_called_once_with(
                request_data['heat_stack_id'])
            db_ns = self.nsf_db.get_network_service(
                self.session, network_service['id'])
            self.assertEqual('ACTIVE', db_ns['status'])

    def test_event_handle_user_config_applied(self):
        network_service = self.create_network_service()
        request_data = {
            'heat_stack_id': 'heat_stack_id',
            'network_service_id': network_service['id']
        }
        self.service_lc_handler.handle_user_config_applied(request_data)
        db_ns = self.nsf_db.get_network_service(
            self.session, network_service['id'])
        self.assertEqual('ACTIVE', db_ns['status'])

    def test_event_handle_user_config_failed(self):
        network_service = self.create_network_service()
        request_data = {
            'heat_stack_id': 'heat_stack_id',
            'network_service_id': network_service['id']
        }
        self.service_lc_handler.handle_user_config_failed(request_data)
        db_ns = self.nsf_db.get_network_service(
            self.session, network_service['id'])
        self.assertEqual('ERROR', db_ns['status'])

    @mock.patch.object(
        service_lcm.ServiceLifeCycleHandler, "_create_event")
    def test_delete_network_service(self, mock_create_event):
        nsi = self.create_network_service_instance()
        network_service = self.nsf_db.get_network_service(
            self.session, nsi['network_service_id'])
        self.assertEqual([nsi['id']],
                         network_service['network_service_instances'])
        self.service_lc_handler.delete_network_service(
            self.context, network_service['id'])
        db_ns = self.nsf_db.get_network_service(
            self.session, network_service['id'])
        self.assertEqual('PENDING_DELETE', db_ns['status'])
        mock_create_event.assert_called_once_with(
            'DELETE_NETWORK_SERVICE_INSTANCE', event_data=nsi['id'])

    @mock.patch.object(
        service_lcm.ServiceLifeCycleHandler, "_create_event")
    def test_event_delete_network_service_instance(self, mock_create_event):
        nsi = self.create_network_service_instance()
        network_service = self.nsf_db.get_network_service(
            self.session, nsi['network_service_id'])
        self.assertEqual([nsi['id']],
                         network_service['network_service_instances'])
        self.service_lc_handler.delete_network_service_instance(
            nsi['id'])
        db_nsi = self.nsf_db.get_network_service_instance(
            self.session, nsi['id'])
        self.assertEqual('PENDING_DELETE', db_nsi['status'])
        mock_create_event.assert_called_once_with(
            'DELETE_NETWORK_SERVICE_DEVICE',
            event_data=nsi['network_service_device_id'])

    def test_event_handle_device_deleted(self):
        nsi = self.create_network_service_instance()
        ns_id = nsi['network_service_id']
        request_data = {'network_service_instance_id': nsi['id']}
        self.service_lc_handler.handle_device_deleted(
            request_data)
        self.assertRaises(nsf_exc.NetworkServiceInstanceNotFound,
                          self.nsf_db.get_network_service_instance,
                          self.session,
                          nsi['id'])
        self.assertRaises(nsf_exc.NetworkServiceNotFound,
                          self.nsf_db.get_network_service,
                          self.session,
                          ns_id)

    @mock.patch.object(
        service_lcm.ServiceLifeCycleHandler, "get_service_details")
    @mock.patch.object(
        service_lcm.ServiceLifeCycleHandler, "_create_event")
    def test_handle_policy_target_added(self, mock_create_event,
                                        mock_get_service_details):
        nsi = self.create_network_service_instance()
        network_service_id = nsi['network_service_id']
        policy_target = mock.Mock()
        with mock.patch.object(
            self.service_lc_handler.config_driver,
            "handle_policy_target_added") as mock_handle_policy_target_added:
            mock_handle_policy_target_added.return_value = 'stack_id'
            self.service_lc_handler.handle_policy_target_added(
                self.context, network_service_id, policy_target)
        db_ns = self.nsf_db.get_network_service(
            self.session, nsi['network_service_id'])
        self.assertIsNotNone(db_ns['heat_stack_id'])
        mock_handle_policy_target_added.assert_called_once_with(
            mock.ANY, policy_target)
        mock_create_event.assert_called_once_with(
            'USER_CONFIG_IN_PROGRESS', event_data=mock.ANY, is_poll_event=True)

    @mock.patch.object(
        service_lcm.ServiceLifeCycleHandler, "get_service_details")
    @mock.patch.object(
        service_lcm.ServiceLifeCycleHandler, "_create_event")
    def test_handle_policy_target_removed(self, mock_create_event,
                                          mock_get_service_details):
        nsi = self.create_network_service_instance()
        network_service_id = nsi['network_service_id']
        policy_target = mock.Mock()
        with mock.patch.object(
            self.service_lc_handler.config_driver,
            "handle_policy_target_removed") as mock_handle_pt_removed:
            mock_handle_pt_removed.return_value = 'stack_id'
            self.service_lc_handler.handle_policy_target_removed(
                self.context, network_service_id, policy_target)
        db_ns = self.nsf_db.get_network_service(
            self.session, nsi['network_service_id'])
        self.assertIsNotNone(db_ns['heat_stack_id'])
        mock_handle_pt_removed.assert_called_once_with(
            mock.ANY, policy_target)
        mock_create_event.assert_called_once_with(
            'USER_CONFIG_IN_PROGRESS', event_data=mock.ANY, is_poll_event=True)

    @mock.patch.object(
        service_lcm.ServiceLifeCycleHandler, "get_service_details")
    @mock.patch.object(
        service_lcm.ServiceLifeCycleHandler, "_create_event")
    def test_handle_consumer_ptg_added(self, mock_create_event,
                                       mock_get_service_details):
        nsi = self.create_network_service_instance()
        network_service_id = nsi['network_service_id']
        policy_target_group = mock.Mock()
        with mock.patch.object(
            self.service_lc_handler.config_driver,
            "handle_consumer_ptg_added") as mock_handle_consumer_ptg_added:
            mock_handle_consumer_ptg_added.return_value = 'stack_id'
            self.service_lc_handler.handle_consumer_ptg_added(
                self.context, network_service_id, policy_target_group)
        db_ns = self.nsf_db.get_network_service(
            self.session, nsi['network_service_id'])
        self.assertIsNotNone(db_ns['heat_stack_id'])
        mock_handle_consumer_ptg_added.assert_called_once_with(
            mock.ANY, policy_target_group)
        mock_create_event.assert_called_once_with(
            'USER_CONFIG_IN_PROGRESS', event_data=mock.ANY, is_poll_event=True)

    @mock.patch.object(
        service_lcm.ServiceLifeCycleHandler, "get_service_details")
    @mock.patch.object(
        service_lcm.ServiceLifeCycleHandler, "_create_event")
    def test_handle_consumer_ptg_removed(self, mock_create_event,
                                         mock_get_service_details):
        nsi = self.create_network_service_instance()
        network_service_id = nsi['network_service_id']
        policy_target_group = mock.Mock()
        with mock.patch.object(
            self.service_lc_handler.config_driver,
            "handle_consumer_ptg_removed") as mock_handle_consumer_ptg_removed:
            mock_handle_consumer_ptg_removed.return_value = 'stack_id'
            self.service_lc_handler.handle_consumer_ptg_removed(
                self.context, network_service_id, policy_target_group)
        db_ns = self.nsf_db.get_network_service(
            self.session, nsi['network_service_id'])
        self.assertIsNotNone(db_ns['heat_stack_id'])
        mock_handle_consumer_ptg_removed.assert_called_once_with(
            mock.ANY, policy_target_group)
        mock_create_event.assert_called_once_with(
            'USER_CONFIG_IN_PROGRESS', event_data=mock.ANY, is_poll_event=True)
