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

from oslo_config import cfg

opts = [
    cfg.StrOpt(
        'visibility_vm_ip_address',
        default=None,
        help=('visibility VM IP address for log forwarding')),
    cfg.IntOpt(
        'visibility_port',
        default=514,
        help=("visibility port to forward logs")),
    cfg.StrOpt(
        'log_level',
        default='info',
        help=('log level for service VMs to forward logs'))]
