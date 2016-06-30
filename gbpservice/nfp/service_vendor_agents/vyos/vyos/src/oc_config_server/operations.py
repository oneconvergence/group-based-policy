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

#!/usr/bin/env python

import sys
import os
import logging
topdir = os.path.dirname(os.path.realpath(__file__)) + "../.."
topdir = os.path.realpath(topdir)
sys.path.insert(0, topdir)
from execformat.executor import execUtils, OperationFailed
from vyos_session import utils

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
