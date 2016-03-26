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

import subprocess
from oslo_log import log as logging
LOG = logging.getLogger(__name__)
SUCCESS = 'SUCCESS'
FAILED = 'FAILED'

"""Every service vendor must inherit this class. If any service vendor wants
   to add extra methods for their service, apart from below given, they should
   add method definition here and implement the method in their driver
"""


class BaseDriver(object):
    def __init__(self):
        pass

    def configure_interfaces(self, context, kwargs):
        return SUCCESS

    def clear_interfaces(self, context, kwargs):
        return SUCCESS

    def configure_routes(self, context, kwargs):
        return SUCCESS

    def clear_routes(self, context, kwargs):
        return SUCCESS

    def configure_healthmonitor(self, context, kwargs):
        ip = kwargs.get('mgmt_ip')
        command = 'ping -c5 ' + ip
        return self._check_vm_health(command)

    def clear_healthmonitor(self, context, kwargs):
        return SUCCESS

    def _check_vm_health(self, command):
        """Ping based basic HM support provided by BaseDriver.
           Service provider can override the method implementation
           if they want to support other types.

           :param command - command to execute

           Returns: SUCCESS/FAILED
        """
        LOG.debug("Executing command %s for VM health check" % (command))
        try:
            subprocess.check_output(command, stderr=subprocess.STDOUT,
                                    shell=True)
        except Exception as e:
            LOG.warn("VM health check failed. Command '%s' execution failed."
                     " Reason=%s" % (command, e))
            return FAILED
        LOG.debug("VM Health check successful. Command '%s' executed"
                  " successfully" % (command))
        return SUCCESS
