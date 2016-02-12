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

from gbpservice.neutron.nsf.common import topics as nsf_rpc_topics
from gbpservice.neutron.nsf.lifecycle_manager.modules import (
    service_lifecycle_manager as service_lcm)
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


class ServiceLCMEventsTestCase(ServiceLCModuleTestCase):

    def test_event_delete_network_service(self):
        pass

    def test_event_delete_network_service_instance(self):
        pass

    def test_event_create_network_service_instance(self):
        pass

    def test_event_handle_device_created(self):
        pass

    def test_event_check_for_user_config_complete(self):
        pass

    def test_event_handle_user_config_applied(self):
        pass

    def test_event_handle_device_deleted(self):
        pass

    def test_event_handle_device_create_failed(self):
        pass

    def test_event_handle_user_config_failed(self):
        pass

    def test_create_network_service_workflow_success(self):
        pass

    def test_create_network_service_workflow_device_create_fail(self):
        pass

    def test_create_network_service_workflow_config_failure(self):
        pass

    def test_delete_network_service_workflow(self):
        pass

    def test_delete_network_service_workflow_device_delete_fail(self):
        pass

    def test_delete_network_service_workflow_config_delete_fail(self):
        pass
