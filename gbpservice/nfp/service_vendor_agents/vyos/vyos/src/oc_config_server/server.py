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

import signal
import logging
import sys
from vyos_session.utils import init_logger


logger = logging.getlogger(__name__)
init_logger(logger)


class OCVyOSServer(object):

    def __init__(self):
        pass


def handler(signum, frame):
    if signum in [2, 3, 11, 15]:
        logger.info(" Recieved signal: %r. Thus exiting " % signum)
        sys.exit()
    else:
        logger.info(" Caught singal: %r. Ignoring " % signum)


def main(argv):
    vyos_server = OCVyOSServer()
    host = ''
    port = 0
    if len(argv) != 5:
        print "server.py -h <host> -p <port>"
        sys.exit(2)

    # Review - OSM: We should accept -h -p in any order.
    if argv[1] == '-h':
        host = argv[2]
    if argv[3] == '-p':
        port = int(argv[4])
    signal.signal(signal.SIGTERM, handler)
    signal.signal(signal.SIGINT, handler)
    vyos_server.start(vyos_server.server, host, port)


if __name__ == '__main__':
    main(sys.argv)
