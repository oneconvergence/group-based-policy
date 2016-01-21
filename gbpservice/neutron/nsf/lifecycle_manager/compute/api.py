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

from gbpservice.neutron.nsf.lifecycle_manager.compute.drivers import (
    nova_driver)

class ComputeAPI(object):
    def __init__(self, compute_platform="NOVA"):
        if compute_platform == "NOVA":
            self.driver = nova_driver.NovaAPIDriver()
        else:
            raise # or assume default ??

    def create(self):
        self.driver.create()

    def delete(self):
        self.driver.delete()

    def plug(self):
        self.driver.plug()

    def unplug(self):
        self.driver.unplug()
