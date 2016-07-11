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

import os
import sys

from executor import execUtils as executor
from executor import OperationFailed
from vyos_session.utils import logger
from vyosparser import vyos_parser as vparser

topdir = os.path.dirname(os.path.realpath(__file__)) + "../.."
topdir = os.path.realpath(topdir)
sys.path.insert(0, topdir)


class ServiceError(Exception):
    pass


class ShowConfig(object):

    def formator(self, options):
        args = ['show']
        service = options[0]
        logger.debug("=====>>>>>> args before executor call = %s" % args)
        if service in ['protocols', 'nat', 'interfaces', 'firewall']:
            args.extend(options)
        elif service in ['dns', 'dhcp-server', 'ssh', 'webproxy']:
            options.insert(0, 'service')
            args.extend(options)
        else:
            raise ServiceError('unknown such service!')
        exe = executor(list(args))
        try:
            execstate, output = exe.execmd()
            logger.debug("=====>>>>>> args after executor call = %s" % args)
        except OperationFailed as e:
            logger.error(e.message)
            return False
        if execstate:
            return vparser.decode_string(output)
