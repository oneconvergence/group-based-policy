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

from gbpservice.nfp.common import exceptions as nfp_exc
from gbpservice.nfp.core.main import Event
from gbpservice.nfp.orchestrator.modules import (
    service_orchestrator as nso)
from gbpservice.nfp.orchestrator.openstack import openstack_driver
from gbpservice.neutron.tests.unit.nfp.orchestrator import test_nfp_db


class NSOoduleTestCase(test_nfp_db.NFPDBTestCase):

    def setUp(self):
        super(NSOoduleTestCase, self).setUp()

    @mock.patch.object(nso, 'events_init')
    @mock.patch.object(nso, 'rpc_init')
    def test_module_init(self, mock_rpc_init, mock_events_init):
        controller = mock.Mock()
        config = "testconfig"
        nso.module_init(controller, config)
        mock_events_init.assert_called_once_with(controller, config, mock.ANY)
        call_args, call_kwargs = mock_events_init.call_args
        self.assertIsInstance(call_args[2],
                              nso.ServiceOrchestrator)
        mock_rpc_init.assert_called_once_with(controller, config)

    def test_rpc_init(self):
        controller = mock.Mock()
        config = mock.Mock()
        nso.rpc_init(controller, config)
        controller.register_rpc_agents.assert_called_once_with(mock.ANY)
        call_args, call_kwargs = controller.register_rpc_agents.call_args
        self.assertEqual(1, len(call_args[0]))
        self.assertIsInstance(call_args[0][0], nso.RpcAgent)

    def test_events_init(self):
        controller = mock.Mock()
        config = mock.Mock()
        nso.events_init(
            controller, config,
            nso.ServiceOrchestrator(controller))
        controller.register_events.assert_called_once_with(mock.ANY)


class NSORpcHandlerTestCase(NSOoduleTestCase):

    def setUp(self):
        super(NSORpcHandlerTestCase, self).setUp()
        self.controller = mock.Mock()
        self.config = mock.Mock()
        self.rpc_handler = nso.RpcHandler(self.config, self.controller)

    @mock.patch.object(nso.ServiceOrchestrator,
                       "create_network_function")
    def test_rpc_create_network_function(self, mock_create_network_function):
        self.rpc_handler.create_network_function("context", "network_function")
        mock_create_network_function.assert_called_once_with(
            "context", "network_function")

    @mock.patch.object(nso.ServiceOrchestrator,
                       "get_network_function")
    def test_rpc_get_network_function(self, mock_get_network_function):
        self.rpc_handler.get_network_function("context", "network_function_id")
        mock_get_network_function.assert_called_once_with(
            "context", "network_function_id")

    @mock.patch.object(nso.ServiceOrchestrator,
                       "get_network_functions")
    def test_rpc_get_network_functions(self, mock_get_network_functions):
        filters = {'id': ['myuuid']}
        self.rpc_handler.get_network_functions("context", filters=filters)
        mock_get_network_functions.assert_called_once_with(
            "context", filters)

    @mock.patch.object(nso.ServiceOrchestrator,
                       "delete_network_function")
    def test_rpc_delete_network_function(self, mock_delete_network_function):
        self.rpc_handler.delete_network_function(
            "context", "network_function_id")
        mock_delete_network_function.assert_called_once_with(
            "context", "network_function_id")

    @mock.patch.object(nso.ServiceOrchestrator,
                       "update_network_function")
    def test_rpc_update_network_function(self, mock_update_network_function):
        self.rpc_handler.update_network_function(
            "context", "network_function_id", "updated_network_function")
        mock_update_network_function.assert_called_once_with(
            "context", "network_function_id", "updated_network_function")

    @mock.patch.object(nso.ServiceOrchestrator,
                       "handle_policy_target_added")
    def test_rpc_policy_target_added_notification(
        self, mock_handle_policy_target_added):
            self.rpc_handler.policy_target_added_notification(
                "context", "network_function_id", "policy_target")
            mock_handle_policy_target_added.assert_called_once_with(
                "context", "network_function_id", "policy_target")

    @mock.patch.object(nso.ServiceOrchestrator,
                       "handle_policy_target_removed")
    def test_rpc_policy_target_removed_notification(
        self, mock_handle_policy_target_removed):
            self.rpc_handler.policy_target_removed_notification(
                "context", "network_function_id", "policy_target")
            mock_handle_policy_target_removed.assert_called_once_with(
                "context", "network_function_id", "policy_target")

    @mock.patch.object(
        nso.ServiceOrchestrator, "handle_consumer_ptg_added")
    def test_rpc_consumer_ptg_added_notification(
        self, mock_handle_consumer_ptg_added):
            self.rpc_handler.consumer_ptg_added_notification(
                "context", "network_function_id", "policy_target_group")
            mock_handle_consumer_ptg_added.assert_called_once_with(
                "context", "network_function_id", "policy_target_group")

    @mock.patch.object(
        nso.ServiceOrchestrator, "handle_consumer_ptg_removed")
    def test_rpc_consumer_ptg_removed_notification(
        self, mock_handle_consumer_ptg_removed):
            self.rpc_handler.consumer_ptg_removed_notification(
                "context", "network_function_id", "policy_target_group")
            mock_handle_consumer_ptg_removed.assert_called_once_with(
                "context", "network_function_id", "policy_target_group")


class ServiceOrchestratorTestCase(NSOoduleTestCase):

    def setUp(self):
        super(ServiceOrchestratorTestCase, self).setUp()
        self.controller = mock.Mock()
        self.config = mock.Mock()
        self.context = mock.Mock()
        self.service_lc_handler = nso.ServiceOrchestrator(
            self.controller)

    @mock.patch.object(
        nso.ServiceOrchestrator, "_validate_create_service_input")
    @mock.patch.object(
        openstack_driver.KeystoneClient, "get_admin_token")
    @mock.patch.object(
        openstack_driver.GBPClient, "get_service_profile")
    @mock.patch.object(
        nso.ServiceOrchestrator, "_create_event")
    def test_create_network_function(self, mock_create_event,
                                     mock_get_service_profile,
                                     mock_get_admin_token, mock_validate):
        network_function_info = {
            'tenant_id': 'tenant_id',
            'service_chain_id': 'sc_instance_id',
            'service_id': 'sc_node_id',
            'service_profile_id': 'service_profile_id',
            'management_ptg_id': 'mgmt_ptg_id',
            'service_config': '',
            'provider_port_id': 'provider_pt_id',
            'network_function_mode': 'GBP',
        }
        network_function = self.service_lc_handler.create_network_function(
            self.context, network_function_info)
        self.assertIsNotNone(network_function)
        db_network_function = self.nfp_db.get_network_function(
            self.session, network_function['id'])
        self.assertEqual(network_function, db_network_function)
        mock_create_event.assert_called_once_with(
            'CREATE_NETWORK_FUNCTION_INSTANCE',
            event_data=mock.ANY)

    def test_validate_create_service_input(self):
        network_function = {}
        self.assertRaises(
            Exception,
            self.service_lc_handler._validate_create_service_input,
            self.context, network_function)

        network_function = {
            "tenant_id": "test",
            "service_id": "test",
            "service_chain_id": "test",
            "service_profile_id": "test",
            "network_function_mode": "test"
        }
        return_value = self.service_lc_handler._validate_create_service_input(
            self.context, network_function)
        self.assertIsNone(return_value)

    def test_delete_network_function_without_nfi(self):
        network_function = self.create_network_function()
        self.service_lc_handler.delete_network_function(
            self.context, network_function['id'])
        self.assertRaises(nfp_exc.NetworkFunctionNotFound,
                          self.nfp_db.get_network_function,
                          self.session, network_function['id'])
        self.assertFalse(self.controller.event.called)
        self.assertFalse(self.controller.rpc_event.called)

    @mock.patch.object(
        nso.ServiceOrchestrator, "get_service_details")
    @mock.patch.object(
        nso.ServiceOrchestrator, "_create_event")
    def test_delete_network_function_with_nfi(self, mock_create_event,
                                              mock_get_service_details):
        service_details = mock.Mock()
        mock_get_service_details.return_value = service_details
        network_function_instance = self.create_network_function_instance()
        network_function_id = network_function_instance['network_function_id']
        network_function = self.nfp_db.get_network_function(
            self.session, network_function_id)
        with mock.patch.object(
            self.service_lc_handler.config_driver,
            "delete") as mock_delete:
            self.service_lc_handler.delete_network_function(
                self.context, network_function_id)
            mock_delete.assert_called_once_with(
                service_details, network_function['heat_stack_id'])
            network_function = self.nfp_db.get_network_function(
                self.session, network_function_id)
            self.assertEqual('PENDING_DELETE', network_function['status'])
            request_data = {
                'tenant_id': network_function['tenant_id'],
                'heat_stack_id': network_function['heat_stack_id'],
                'network_function_id': network_function_id
            }
            mock_create_event.assert_called_once_with(
                'DELETE_USER_CONFIG_IN_PROGRESS',
                event_data=request_data,
                is_poll_event=True)

    @mock.patch.object(
        nso.ServiceOrchestrator, "_create_event")
    def test_event_create_network_function_instance(self, mock_create_event):
        network_function = self.create_network_function()
        mode = 'GBP'
        network_function_port_info = [
            {
                'id': 'provider_port_id',
                'port_model': mode,
                'port_classification': 'provider'
            },
            {
                'id': 'consumer_port_id',
                'port_model': mode,
                'port_classification': 'consumer'
            }
        ]
        management_network_info = {
            'id': 'management_ptg_id',
            'port_model': mode
        }

        create_nfi_request = {
            'network_function': network_function,
            'network_function_port_info': network_function_port_info,
            'management_network_info': management_network_info,
            'service_type': 'service_type',
            'service_vendor': 'vendor',
            'share_existing_device': True
        }
        test_event = Event(data=create_nfi_request)
        self.assertEqual([], network_function['network_function_instances'])
        self.service_lc_handler.create_network_function_instance(
            test_event)
        db_network_function = self.nfp_db.get_network_function(
            self.session, network_function['id'])
        self.assertEqual(
            1, len(db_network_function['network_function_instances']))
        # The value of port_info in network_function_instance is a list
        # when we do a DB get, the order changes resulting in test failing
        # if we validate the event data
        '''
        nfi_db = self.nfp_db.get_network_function_instance(
            self.session, db_network_function['network_function_instances'][0])
        create_nfd_request = {
            'network_function': network_function,
            'network_function_instance': nfi_db,
            'management_network_info': management_network_info,
            'service_type': 'service_type',
            'service_vendor': 'vendor',
            'share_existing_device': True,
        }
        '''
        mock_create_event.assert_called_once_with(
            'CREATE_NETWORK_FUNCTION_DEVICE', event_data=mock.ANY)

    @mock.patch.object(
        nso.ServiceOrchestrator, "get_service_details")
    @mock.patch.object(
        nso.ServiceOrchestrator, "_create_event")
    def test_event_handle_device_created(self, mock_create_event,
                                         mock_get_service_details):
        nfd = self.create_network_function_device()
        nfi = self.create_network_function_instance(create_nfd=False)
        request_data = {
            'network_function_instance_id': nfi['id'],
            'network_function_device_id': nfd['id']
        }
        test_event = Event(data=request_data)
        self.assertIsNone(nfi['network_function_device_id'])
        with mock.patch.object(
            self.service_lc_handler.config_driver,
            "apply_user_config") as mock_apply_user_config:
            mock_apply_user_config.return_value = "stack_id"
            self.service_lc_handler.handle_device_created(
                test_event)
        db_nfi = self.nfp_db.get_network_function_instance(
            self.session, nfi['id'])
        db_nf = self.nfp_db.get_network_function(
            self.session, nfi['network_function_id'])
        self.assertEqual(nfd['id'], db_nfi['network_function_device_id'])
        self.assertIsNotNone(db_nf['heat_stack_id'])
        mock_create_event.assert_called_once_with(
            'APPLY_USER_CONFIG_IN_PROGRESS',
            event_data=mock.ANY,
            is_poll_event=True)

    def test_event_handle_device_create_failed(self):
        nfd = self.create_network_function_device()
        nfi = self.create_network_function_instance(create_nfd=False)
        request_data = {
            'network_function_instance_id': nfi['id'],
            'network_function_device_id': nfd['id']
        }
        test_event = Event(data=request_data)
        self.assertIsNone(nfi['network_function_device_id'])
        self.service_lc_handler.handle_device_create_failed(
            test_event)
        db_nfi = self.nfp_db.get_network_function_instance(
            self.session, nfi['id'])
        db_nf = self.nfp_db.get_network_function(
            self.session, nfi['network_function_id'])
        self.assertEqual('ERROR', db_nfi['status'])
        self.assertEqual('ERROR', db_nf['status'])

    def test_event_check_for_user_config_complete(self):
        network_function = self.create_network_function()
        with mock.patch.object(
            self.service_lc_handler.config_driver,
            "is_config_complete") as mock_is_config_complete:
            # Verify return status IN_PROGRESS from config driver
            mock_is_config_complete.return_value = "IN_PROGRESS"
            request_data = {
                'tenant_id': network_function['tenant_id'],
                'heat_stack_id': 'heat_stack_id',
                'network_function_id': network_function['id']}
            test_event = Event(data=request_data)
            self.service_lc_handler.check_for_user_config_complete(
                test_event)
            mock_is_config_complete.assert_called_once_with(
                request_data['heat_stack_id'], network_function['tenant_id'])
            db_nf = self.nfp_db.get_network_function(
                self.session, network_function['id'])
            self.assertEqual(network_function['status'], db_nf['status'])

            # Verify return status ERROR from config driver
            mock_is_config_complete.reset_mock()
            mock_is_config_complete.return_value = "ERROR"
            request_data = {
                'tenant_id': network_function['tenant_id'],
                'heat_stack_id': 'heat_stack_id',
                'network_function_id': network_function['id']}
            test_event = Event(data=request_data)
            self.service_lc_handler.check_for_user_config_complete(
                test_event)
            mock_is_config_complete.assert_called_once_with(
                request_data['heat_stack_id'], network_function['tenant_id'])
            db_nf = self.nfp_db.get_network_function(
                self.session, network_function['id'])
            self.assertEqual('ERROR', db_nf['status'])
            self.controller.poll_event_done.assert_called_once_with(
                test_event)

            # Verify return status COMPLETED from config driver
            self.controller.poll_event_done.reset_mock()
            mock_is_config_complete.reset_mock()
            mock_is_config_complete.return_value = "COMPLETED"
            request_data = {
                'tenant_id': network_function['tenant_id'],
                'heat_stack_id': 'heat_stack_id',
                'network_function_id': network_function['id']}
            test_event = Event(data=request_data)
            self.service_lc_handler.check_for_user_config_complete(
                test_event)
            mock_is_config_complete.assert_called_once_with(
                request_data['heat_stack_id'], network_function['tenant_id'])
            db_nf = self.nfp_db.get_network_function(
                self.session, network_function['id'])
            self.assertEqual('ACTIVE', db_nf['status'])
            self.controller.poll_event_done.assert_called_once_with(
                test_event)

    def test_event_handle_user_config_applied(self):
        network_function = self.create_network_function()
        request_data = {
            'heat_stack_id': 'heat_stack_id',
            'network_function_id': network_function['id']
        }
        test_event = Event(data=request_data)
        self.service_lc_handler.handle_user_config_applied(test_event)
        db_nf = self.nfp_db.get_network_function(
            self.session, network_function['id'])
        self.assertEqual('ACTIVE', db_nf['status'])

    def test_event_handle_user_config_failed(self):
        network_function = self.create_network_function()
        request_data = {
            'heat_stack_id': 'heat_stack_id',
            'network_function_id': network_function['id']
        }
        test_event = Event(data=request_data)
        self.service_lc_handler.handle_user_config_failed(test_event)
        db_nf = self.nfp_db.get_network_function(
            self.session, network_function['id'])
        self.assertEqual('ERROR', db_nf['status'])

    @mock.patch.object(
        nso.ServiceOrchestrator, "_create_event")
    def test_event_check_for_user_config_deleted(self, mock_create_event):
        network_function = self.create_network_function()
        with mock.patch.object(
            self.service_lc_handler.config_driver,
            "is_config_delete_complete") as mock_is_config_delete_complete:
            # Verify return status IN_PROGRESS from config driver
            mock_is_config_delete_complete.return_value = "IN_PROGRESS"
            request_data = {
                'tenant_id': network_function['tenant_id'],
                'heat_stack_id': 'heat_stack_id',
                'network_function_id': network_function['id']}
            test_event = Event(data=request_data)
            self.service_lc_handler.check_for_user_config_deleted(
                test_event)
            mock_is_config_delete_complete.assert_called_once_with(
                request_data['heat_stack_id'], network_function['tenant_id'])
            db_nf = self.nfp_db.get_network_function(
                self.session, network_function['id'])
            self.assertEqual(network_function['status'], db_nf['status'])
            self.assertEqual(network_function['heat_stack_id'],
                             db_nf['heat_stack_id'])

            # Verify return status ERROR from config driver
            mock_is_config_delete_complete.reset_mock()
            mock_is_config_delete_complete.return_value = "ERROR"
            request_data = {
                'tenant_id': network_function['tenant_id'],
                'heat_stack_id': 'heat_stack_id',
                'network_function_id': network_function['id']}
            test_event = Event(data=request_data)
            self.service_lc_handler.check_for_user_config_deleted(
                test_event)
            mock_is_config_delete_complete.assert_called_once_with(
                request_data['heat_stack_id'], network_function['tenant_id'])
            event_data = {
                'network_function_id': network_function['id']
            }
            mock_create_event.assert_called_once_with(
                'USER_CONFIG_DELETE_FAILED', event_data=event_data)
            self.controller.poll_event_done.assert_called_once_with(
                test_event)

            # Verify return status COMPLETED from config driver
            self.controller.poll_event_done.reset_mock()
            mock_is_config_delete_complete.reset_mock()
            mock_create_event.reset_mock()
            mock_is_config_delete_complete.return_value = "COMPLETED"
            request_data = {
                'tenant_id': network_function['tenant_id'],
                'heat_stack_id': 'heat_stack_id',
                'network_function_id': network_function['id']}
            test_event = Event(data=request_data)
            self.service_lc_handler.check_for_user_config_deleted(
                test_event)
            mock_is_config_delete_complete.assert_called_once_with(
                request_data['heat_stack_id'], network_function['tenant_id'])
            db_nf = self.nfp_db.get_network_function(
                self.session, network_function['id'])
            self.assertEqual(None, db_nf['heat_stack_id'])
            event_data = {
                'network_function_id': network_function['id']
            }
            mock_create_event.assert_called_once_with(
                'USER_CONFIG_DELETED', event_data=event_data)
            self.controller.poll_event_done.assert_called_once_with(
                test_event)

    @mock.patch.object(
        nso.ServiceOrchestrator, "_create_event")
    def test_event_handle_user_config_deleted(self, mock_create_event):
        nfi = self.create_network_function_instance()
        request_data = {
            'network_function_id': nfi['network_function_id']
        }
        test_event = Event(data=request_data)
        self.service_lc_handler.handle_user_config_deleted(test_event)
        mock_create_event.assert_called_once_with(
            'DELETE_NETWORK_FUNCTION_INSTANCE', event_data=nfi['id'])

    def test_event_handle_user_config_delete_failed(self):
        network_function = self.create_network_function()
        request_data = {
            'network_function_id': network_function['id']
        }
        test_event = Event(data=request_data)
        self.service_lc_handler.handle_user_config_delete_failed(test_event)
        db_nf = self.nfp_db.get_network_function(
            self.session, network_function['id'])
        self.assertEqual('ERROR', db_nf['status'])

    @mock.patch.object(
        nso.ServiceOrchestrator, "get_service_details")
    @mock.patch.object(
        nso.ServiceOrchestrator, "_create_event")
    def test_delete_network_function(self, mock_create_event,
                                     mock_get_service_details):
        service_details = mock.Mock()
        mock_get_service_details.return_value = service_details
        nfi = self.create_network_function_instance()
        network_function = self.nfp_db.get_network_function(
            self.session, nfi['network_function_id'])
        self.assertEqual([nfi['id']],
                         network_function['network_function_instances'])
        with mock.patch.object(
                self.service_lc_handler.config_driver,
                "delete") as mock_delete:
            self.service_lc_handler.delete_network_function(
                self.context, network_function['id'])
            mock_delete.assert_called_once_with(
                service_details,
                network_function['heat_stack_id'])
            db_nf = self.nfp_db.get_network_function(
                self.session, network_function['id'])
            self.assertEqual('PENDING_DELETE', db_nf['status'])
            event_data = {
                'tenant_id': network_function['tenant_id'],
                'heat_stack_id': network_function['heat_stack_id'],
                'network_function_id': network_function['id']
            }
            mock_create_event.assert_called_once_with(
                'DELETE_USER_CONFIG_IN_PROGRESS',
                event_data=event_data,
                is_poll_event=True)

    @mock.patch.object(
        nso.ServiceOrchestrator, "_create_event")
    def test_event_delete_network_function_instance(self, mock_create_event):
        nfi = self.create_network_function_instance()
        network_function = self.nfp_db.get_network_function(
            self.session, nfi['network_function_id'])
        self.assertEqual([nfi['id']],
                         network_function['network_function_instances'])
        test_event = Event(data=nfi['id'])
        self.service_lc_handler.delete_network_function_instance(
            test_event)
        db_nfi = self.nfp_db.get_network_function_instance(
            self.session, nfi['id'])
        self.assertEqual('PENDING_DELETE', db_nfi['status'])
        delete_event_data = {
            'network_function_id': nfi['network_function_id'],
            'network_function_device_id': nfi['network_function_device_id'],
            'network_function_instance': db_nfi
        }
        mock_create_event.assert_called_once_with(
            'DELETE_NETWORK_FUNCTION_DEVICE',
            event_data=delete_event_data)

    def test_event_handle_device_deleted(self):
        nfi = self.create_network_function_instance()
        ns_id = nfi['network_function_id']
        request_data = {'network_function_instance_id': nfi['id']}
        test_event = Event(data=request_data)
        self.service_lc_handler.handle_device_deleted(
            test_event)
        self.assertRaises(nfp_exc.NetworkFunctionInstanceNotFound,
                          self.nfp_db.get_network_function_instance,
                          self.session,
                          nfi['id'])
        self.assertRaises(nfp_exc.NetworkFunctionNotFound,
                          self.nfp_db.get_network_function,
                          self.session,
                          ns_id)

    @mock.patch.object(
        nso.ServiceOrchestrator, "get_service_details")
    @mock.patch.object(
        nso.ServiceOrchestrator, "_create_event")
    def test_handle_policy_target_added(self, mock_create_event,
                                        mock_get_service_details):
        nfi = self.create_network_function_instance()
        network_function_id = nfi['network_function_id']
        policy_target = mock.Mock()
        with mock.patch.object(
            self.service_lc_handler.config_driver,
            "handle_policy_target_added") as mock_handle_policy_target_added:
            mock_handle_policy_target_added.return_value = 'stack_id'
            self.service_lc_handler.handle_policy_target_added(
                self.context, network_function_id, policy_target)
        db_nf = self.nfp_db.get_network_function(
            self.session, nfi['network_function_id'])
        self.assertIsNotNone(db_nf['heat_stack_id'])
        mock_handle_policy_target_added.assert_called_once_with(
            mock.ANY, policy_target)
        mock_create_event.assert_called_once_with(
            'APPLY_USER_CONFIG_IN_PROGRESS',
            event_data=mock.ANY,
            is_poll_event=True)

    @mock.patch.object(
        nso.ServiceOrchestrator, "get_service_details")
    @mock.patch.object(
        nso.ServiceOrchestrator, "_create_event")
    def test_handle_policy_target_removed(self, mock_create_event,
                                          mock_get_service_details):
        nfi = self.create_network_function_instance()
        network_function_id = nfi['network_function_id']
        policy_target = mock.Mock()
        with mock.patch.object(
            self.service_lc_handler.config_driver,
            "handle_policy_target_removed") as mock_handle_pt_removed:
            mock_handle_pt_removed.return_value = 'stack_id'
            self.service_lc_handler.handle_policy_target_removed(
                self.context, network_function_id, policy_target)
        db_nf = self.nfp_db.get_network_function(
            self.session, nfi['network_function_id'])
        self.assertIsNotNone(db_nf['heat_stack_id'])
        mock_handle_pt_removed.assert_called_once_with(
            mock.ANY, policy_target)
        mock_create_event.assert_called_once_with(
            'APPLY_USER_CONFIG_IN_PROGRESS',
            event_data=mock.ANY,
            is_poll_event=True)

    @mock.patch.object(
        nso.ServiceOrchestrator, "get_service_details")
    @mock.patch.object(
        nso.ServiceOrchestrator, "_create_event")
    def test_handle_consumer_ptg_added(self, mock_create_event,
                                       mock_get_service_details):
        nfi = self.create_network_function_instance()
        network_function_id = nfi['network_function_id']
        policy_target_group = mock.Mock()
        with mock.patch.object(
            self.service_lc_handler.config_driver,
            "handle_consumer_ptg_added") as mock_handle_consumer_ptg_added:
            mock_handle_consumer_ptg_added.return_value = 'stack_id'
            self.service_lc_handler.handle_consumer_ptg_added(
                self.context, network_function_id, policy_target_group)
        db_nf = self.nfp_db.get_network_function(
            self.session, nfi['network_function_id'])
        self.assertIsNotNone(db_nf['heat_stack_id'])
        mock_handle_consumer_ptg_added.assert_called_once_with(
            mock.ANY, policy_target_group)
        mock_create_event.assert_called_once_with(
            'APPLY_USER_CONFIG_IN_PROGRESS',
            event_data=mock.ANY,
            is_poll_event=True)

    @mock.patch.object(
        nso.ServiceOrchestrator, "get_service_details")
    @mock.patch.object(
        nso.ServiceOrchestrator, "_create_event")
    def test_handle_consumer_ptg_removed(self, mock_create_event,
                                         mock_get_service_details):
        nfi = self.create_network_function_instance()
        network_function_id = nfi['network_function_id']
        policy_target_group = mock.Mock()
        with mock.patch.object(
            self.service_lc_handler.config_driver,
            "handle_consumer_ptg_removed") as mock_handle_consumer_ptg_removed:
            mock_handle_consumer_ptg_removed.return_value = 'stack_id'
            self.service_lc_handler.handle_consumer_ptg_removed(
                self.context, network_function_id, policy_target_group)
        db_nf = self.nfp_db.get_network_function(
            self.session, nfi['network_function_id'])
        self.assertIsNotNone(db_nf['heat_stack_id'])
        mock_handle_consumer_ptg_removed.assert_called_once_with(
            mock.ANY, policy_target_group)
        mock_create_event.assert_called_once_with(
            'APPLY_USER_CONFIG_IN_PROGRESS',
            event_data=mock.ANY,
            is_poll_event=True)
