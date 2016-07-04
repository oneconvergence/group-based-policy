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
import os
import sys

from execformat.executor import execUtils
from execformat.executor import OperationFailed
from vyos_session import utils

topdir = os.path.dirname(os.path.realpath(__file__)) + "../.."
topdir = os.path.realpath(topdir)
sys.path.insert(0, topdir)

logger = logging.getLogger(__name__)
utils.init_logger(logger)


class configOpts(object):

    def __init__(self):
        pass

    def set_1(self, args):
        exe = execUtils(list(args))
        exe.execmd()

    def delete_1(self, args):
        exe = execUtils(list(args))
        exe.execmd()

    def show(self, args):
        exe = execUtils(list(args))
        res, output = exe.execmd(nonsession=True)
        return res, output

    def set(self, args):
        args.insert(0, 'set')
        exe = execUtils(list(args))
        try:
            exe.execmd()
            return True
        except OperationFailed as e:
            logger.error(e.message)
            return False

    def delete(self, args):
        args.insert(0, 'delete')
        exe = execUtils(list(args))
        try:
            exe.execmd()
            return True
        except OperationFailed as e:
            logger.error(e.message)
            return False
