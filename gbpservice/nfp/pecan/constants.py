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


base_vm = 'base_vm'
base_controller = 'base_controller'
controller = 'controller'


controllers = {
    base_controller: 'gbpservice.nfp.base_configurator.controllers',
    base_vm: ('gbpservice.tests.contrib.nfp_service'
              '.reference_configurator.controllers'
              ),
    controller: 'gbpservice.contrib.nfp.configurator.controller'
}

modes = [base_controller, base_vm, controller]
