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

from neutron import context
from oslo_config import cfg
from oslo_log import log as logging

from gbpservice.nfp.configurator.drivers.base import base_driver
from gbpservice.nfp.configurator.lib import config_script_constants as const

LOG = logging.getLogger(__name__)

""" ConfigScript as a service driver for handling config script
service configuration requests.

We initialize service type in this class because agent loads
class object only for those driver classes that have service type
initialized. Also, only this driver class is exposed to the agent.

"""


class ConfigScriptDriver(base_driver.BaseDriver):
    service_type = const.SERVICE_TYPE

    def __init__(self):
        self.timeout = cfg.CONF.rest_timeout
        self.host = cfg.CONF.host
        self.context = context.get_admin_context_without_session()

    def create_heat(self, context, script, host):
        return const.UNHANDLED

    def create_ansible(self, context, script, host):
        return const.UNHANDLED

    def create_config_init(self, context, script, host):
        return const.UNHANDLED
