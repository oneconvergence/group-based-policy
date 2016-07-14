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

import logging
import subprocess

from vyos_session import utils

SUCCESS = True
FAILED = False

logger = logging.getLogger(__name__)
utils.init_logger(logger)


class APIHandler(object):

    def __init__(self):
        pass

    def run_command(self, command):
        proc = subprocess.Popen(command,
                                shell=True,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)

        out, err = proc.communicate()
        if err:
            logger.error("Unable to run command %s,  ERROR- %s" %
                         (command, err))
            return None
        return out

    def configure_rsyslog_as_client(self, config):
        command = ("/opt/vyatta/sbin/vyatta-cfg-cmd-wrapper begin "
                   "/opt/vyatta/sbin/vyatta-cfg-cmd-wrapper set system "
                   "syslog host %s facility all level %s"
                   "/opt/vyatta/sbin/vyatta-cfg-cmd-wrapper commit"
                   "/opt/vyatta/sbin/vyatta-cfg-cmd-wrapper save" % (
                                    config['server_ip'], config['log_level']))

        try:
            self.run_command(command)
            return SUCCESS
        except Exception as ex:
            logger.error("Error while configuring rsyslog as client. %s" % ex)
            return FAILED
