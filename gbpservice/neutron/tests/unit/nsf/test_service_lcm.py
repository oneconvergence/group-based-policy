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

from gbpservice.neutron.nsf.lifecycle_manager.modules import (
    service_lifecycle_manager as service_lcm)
from gbpservice.neutron.tests.unit.nsf import test_nsf_db


class ServiceLCMTestCase(test_nsf_db.NSFDBTestCase):

    def setUp(self):
        super(ServiceLCMTestCase, self).setUp()

    def test_module_init(self):
        with mock.patch.object(service_lcm, 'events_init') as events_init:
            with mock.patch.object(service_lcm, 'rpc_init') as rpc_init:
                controller = "test"
                config = "testconfig"
                service_lcm.module_init(controller, config)
                events_init.assert_called_once_with(controller, config)
                rpc_init.assert_called_once_with(controller, config)

    def test_rpc_init(self):
        pass

    def test_events_init(self):
        pass

    def test_rpc_create_network_service(self):
        pass

    def test_rpc_get_network_service(self):
        pass

    def test_rpc_get_network_services(self):
        pass

    def test_delete_network_service(self):
        pass

    def test_notify_policy_target_added(self):
        pass

    def test_notify_policy_target_removed(self):
        pass

    def test_notify_consumer_ptg_added(self):
        pass

    def test_notify_consumer_ptg_removed(self):
        pass

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
