#!/usr/bin/env python
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


class showConfig():

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
            # if not exe.checkcmd(' '.join(args)):
             #   logger.error("%s: given args does not match with existing configs!"%args)
              #  return False
            execstate, output = exe.execmd()
            logger.debug("=====>>>>>> args after executor call = %s" % args)
        except OperationFailed as e:
            logger.error(e.message)
            return False
        if execstate:
            return vparser.decode_string(output)
