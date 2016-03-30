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

from gbpservice.nfp.orchestrator.networking.drivers import (
    gbp_driver)
from gbpservice.nfp.orchestrator.networking.drivers import (
    neutron_driver)


class NetworkingAPI(object):
    def __init__(self, network_platform):
        if network_platform == "GBP":
            self.driver = gbp_driver.GBPDriver()
        elif network_platform == "NEUTRON":
            self.driver = neutron_driver.NeutronDriver()
        else:
            raise  # or assume default ??

    def create_port(self):
        pass

    def delete_port(self):
        pass

    def create_network(self):
        pass

    def delete_network(self):
        pass

    def setup_traffic_steering(self):
        self.driver.setup_traffic_steering()
