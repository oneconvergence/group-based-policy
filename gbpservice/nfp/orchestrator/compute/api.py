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

from gbpservice.nfp.orchestrator.compute.drivers import (
    nova_driver)


class ComputeAPI(object):
    # TODO: Get the compute platform either from config, or from the
    # service profile
    def __init__(self, compute_platform="NOVA"):
        if compute_platform == "NOVA":
            self.driver = nova_driver.NovaAPIDriver()
        else:
            raise  # or assume default ??

    def create_instance(self):
        self.driver.create_instance()

    def delete_instance(self):
        self.driver.delete_instance()

    def attach_interface(self):
        self.driver.attach_interface()

    def detach_interface(self):
        self.driver.detach_interface()

    def get_instance(self):
        self.driver.get_instance()
