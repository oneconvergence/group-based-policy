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

from gbpservice.neutron.nsf.lifecycle_manager.compute import api as compute_api
from gbpservice.neutron.nsf.lifecycle_manager.networking import (
    api as networking_api)


class GenericLifeCycleDriver(object):
    """Generic Driver class for Lifecycle handling of virtual appliances

    Does not support sharing of virtual appliance for different chains
    Does not support hotplugging interface to devices
    Launches the VM with all the management and data ports and a new VM
    is launched for each Network Service Instance
    """
    def __init__(self, supports_device_sharing=False, supports_hotplug=False,
                 max_interfaces=5):
        self.supports_device_sharing = supports_device_sharing
        self.supports_hotplug = supports_hotplug
        # Try to move the following handlers to Device LCM manager rather than
        # having here in the driver
        self.compute_handler = compute_api.ComputeAPI()
        self.network_handler = networking_api.NetworkingAPI()
        self.maximum_interfaces = max_interfaces

    def is_device_sharing_supported(self):
        return self.supports_device_sharing

    def get_devices_to_reuse(self):
        return None

    def _get_ports_for_device_create(self):
        pass

    def _get_management_port(self):
        pass

    def _is_ha_monitoring_port_required(self):
        return False

    def create_device(self):
        pass  # Use Network and Compute drivers to do things

    def setup_traffic_steering(self):
        # One driver should not call another driver
        self.network_handler.setup_traffic_steering()

    def plug_interface(self):
        pass

    def unplug_interface(self):
        pass

    def configure_interface(self):
        pass

    def configure_routes(self):
        pass

    def delete_device(self):
        pass
