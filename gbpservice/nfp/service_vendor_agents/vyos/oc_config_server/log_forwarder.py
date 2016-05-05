# One Convergence, Inc. CONFIDENTIAL
# Copyright (c) 2012-2015, One Convergence, Inc., USA
# All Rights Reserved.
#
# All information contained herein is, and remains the property of
# One Convergence, Inc. and its suppliers, if any. The intellectual and
# technical concepts contained herein are proprietary to One Convergence,
# Inc. and its suppliers.
#
# Dissemination of this information or reproduction of this material is
# strictly forbidden unless prior written permission is obtained from
# One Convergence, Inc., USA

import logging
import subprocess

from vyos_session import utils

OP_SUCCESS = True
OP_FAILED = False

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
        command = """
                /opt/vyatta/sbin/vyatta-cfg-cmd-wrapper begin
                /opt/vyatta/sbin/vyatta-cfg-cmd-wrapper set system syslog host %s facility all level %s
                /opt/vyatta/sbin/vyatta-cfg-cmd-wrapper commit
                /opt/vyatta/sbin/vyatta-cfg-cmd-wrapper save
                """ %(config['server_ip'], config['log_level'])

        try:
            out = self.run_command(command)
            return OP_SUCCESS
        except Exception as ex:
            logger.error("Error while configuring rsyslog as client. %s" % ex)
            return OP_FAILED
