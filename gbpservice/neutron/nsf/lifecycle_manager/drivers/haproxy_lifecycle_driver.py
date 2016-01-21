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

from gbpservice.neutron.nsf.lifecycle_manager.drivers.LifeCycleDriverBase\
    import GenericLifeCycleDriver


class HaproxyLifeCycleDriver(GenericLifeCycleDriver):
    """Haproxy Service VM Driver for Lifecycle handling of virtual appliances

    Overrides methods from HotplugSupportedLifeCycleDriver class for performing
    things specific to Haproxy service VM
    """
    def __init__(self, supports_device_sharing=True, supports_hotplug=True,
                 max_interfaces=10):
        super(HaproxyLifeCycleDriver, self).__init__(
            supports_device_sharing=supports_device_sharing,
            supports_hotplug=supports_hotplug,
            max_interfaces=max_interfaces)

    def get_devices_to_reuse(self, tenant_id, service_type, service_vendor,
                             ha_type, num_devices):
        filters = {'tenant_id': [tenant_id],
                   'service_vendor': [service_vendor],
                   'interfaces_in_use': ' < max_interfaces'}
        devices = self.get_device_instances_db(filters=filters)
        if devices:
            return devices[0]
        else:
            return None

    def _get_ports_for_device_create(self):
        pass

    def _get_management_port(self):
        pass

    def _is_ha_monitoring_port_required(self):
        return False

    def create_device(self):
        pass

    def setup_traffic_steering(self):
        self.network_handler.setup_traffic_steering()

    def plug_interface(self):
        pass

    def unplug_interface(self):
        pass

    def delete_device(self):
        pass
