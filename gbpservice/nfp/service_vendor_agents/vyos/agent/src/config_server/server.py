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
import signal
import sys

from vyos_session.utils import init_logger

logger = logging.getlogger(__name__)
init_logger(logger)


class VyOSServer(object):

    def __init__(self):
        pass


def handler(signum, frame):
    if signum in [2, 3, 11, 15]:
        logger.info(" Recieved signal: %r. Thus exiting " % signum)
        sys.exit()
    else:
        logger.info(" Caught singal: %r. Ignoring " % signum)


def main(argv):
    vyos_server = VyOSServer()
    host = ''
    port = 0
    if len(argv) != 5:
        logger.info("server.py -h <host> -p <port>")
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
