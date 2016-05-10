#
# One Convergence, Inc. CONFIDENTIAL
# Copyright (c) 2012-2014, One Convergence, Inc., USA
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
#

import json
import optparse
import signal
import sys
import traceback
from urlparse import urlparse, parse_qs
import eventlet.wsgi
import logging
import logging.handlers
import cfg
import haproxy_config_driver

logger = None

class HaproxyAgent():

    def __init__(self):
        try:
            self.haproxy_driver = haproxy_config_driver.HaproxyDriver(logger)
        except Exception, err:
            logger.error("Failed to initialize"
                         " the haproxy configuration driver."
                         " Error: %s" % err)

    def __enter__(self):
        return self

    def __exit__(self, _type, value, traceback):
        try:
            self.haproxy_driver._kill()
        except Exception, err:
            logger.error("Failed to kill the haproxy process."
                         " Haproxy process may not be killed."
                         " Error: %s" % err)

    def return_error(self, err, start_response):
        #BUGBUG: handle this correctly
        status = "500 Internal Server Error"  # HTTP Status
        response_body = str(err.message)
        response_headers = [('Content-type', 'text/plain')]
        start_response(status, response_headers)
        return [response_body]

    def return_not_found(self, parent_resource, resource_id, start_response):
        status = '404 NOT FOUND'
        response_body = str(parent_resource) + ' ' + \
                        str(resource_id) + 'NOT EXISTS'
        response_headers = [('Content-type', 'text/plain')]
        start_response(status, response_headers)
        return [response_body]

    def get_parent_resource(self, url_parts):
        try:
            parent_resource = url_parts[1]
        except ValueError:
            logger.error("No valid parent resource found in url: %s"
                         % ' '.join(url_parts))
        return parent_resource

    def get_resource_id(self, parent_resource, url_parts):
        resource_id = None
        if len(url_parts) == 3:
            resource_id = url_parts[2]
        return resource_id

    def create_method(self, parent_resource, body):
        methodToCall = getattr(self.haproxy_driver,
                               'create_%s' % parent_resource)
        return methodToCall(body)

    def update_method(self, parent_resource, resource_id, body):
        methodToCall = getattr(self.haproxy_driver,
                               'update_%s' % parent_resource)
        return methodToCall(resource_id, body)

    def delete_method(self, parent_resource, resource_id):
        methodToCall = getattr(self.haproxy_driver,
                               'delete_%s' % parent_resource)
        return methodToCall(resource_id)

    def show_method(self, parent_resource, resource_id):
        methodToCall = getattr(self.haproxy_driver,
                               'show_%s' % parent_resource)
        return methodToCall(resource_id)

    def list_method(self, parent_resource):
        methodToCall = getattr(self.haproxy_driver,
                               'list_%ss' % parent_resource)
        return methodToCall()

    def get_stats(self, parent_resource, resource_id):
        methodToCall = getattr(self.haproxy_driver,
                               'get_%s' % parent_resource)
        return methodToCall(resource_id)

    def get_lbstats(self, parent_resource, resource_id):
        methodToCall = getattr(self.haproxy_driver,
                               'get_%s' % parent_resource)
        return methodToCall(resource_id)

    def sync_config(self, parent_resource, resource_id):
        methodToCall = getattr(self.haproxy_driver,
                               '%s_config' % parent_resource)
        return methodToCall(resource_id)

    def setup_ha(self, parent_resource, body):
        methodToCall = getattr(self.haproxy_driver,
                               '%s' % parent_resource)
        return methodToCall(body)

    def rsyslog_client_config(self, body):
        methodToCall = getattr(self.haproxy_driver,
                               'configure_rsyslog_as_client')
        return methodToCall(body)

    def server(self, environ, start_response):
        data = "Haproxy Agent: No resource specified in the URL path"
        result = None
        ## getting URL
        url = environ["PATH_INFO"]
        method = environ["REQUEST_METHOD"]
        params = environ.get("QUERY_STRING", "")

        if url == '/':
            result = data
        else:
            ## getting HTML body
            try:
                length = int(environ.get('CONTENT_LENGTH', '0'))
            except ValueError:
                length = 0
            if length != 0:
                data = environ["wsgi.input"].read(length)
                data = json.loads(data)
            else:
                data = None

            ## parsing URL
            url = urlparse(url)
            params = parse_qs(params)
            url_parts = url.path.split('/')
            parent_resource = self.get_parent_resource(url_parts)
            if parent_resource not in ['frontend', 'backend', 'stats', 'sync',
                     'setup_ha', 'lbstats', 'configure-rsyslog-as-client']:
                err = Exception()
                err.message = "Invalid resource name '%s'" % parent_resource
                return self.return_error(err, start_response)

            if method == 'POST':
                try:
                    if parent_resource == 'sync':
                        result = self.sync_config(parent_resource, data)
                    elif parent_resource == 'setup_ha':
                        result = self.setup_ha(parent_resource, data)
                    elif parent_resource == 'configure-rsyslog-as-client':
                        result = self.rsyslog_client_config(data)
                    else:
                        result = self.create_method(parent_resource, data)
                except Exception, err:
                    logger.error("Failed to create %s. Error :: %s."
                                 " Backtrace: %s"
                                 % (parent_resource, err,
                                    traceback.format_exc()))
                    return self.return_error(err, start_response)
            elif method == 'PUT':
                try:
                    resource_id = self.get_resource_id(parent_resource,
                                                       url_parts)
                    result = self.update_method(parent_resource,
                                                resource_id,
                                                data)
                except Exception, err:
                    logger.error("Failed to update %s. Error :: %s."
                                 " Backtrace:: %s"
                                 % (parent_resource, err,
                                    traceback.format_exc()))
                    return self.return_error(err, start_response)
            elif method == 'GET':
                resource_id = self.get_resource_id(parent_resource, url_parts)
                if resource_id is None:
                    try:
                        result = self.list_method(parent_resource)
                    except Exception, err:
                        logger.error("Failed to list %s. Error :: %s."
                                     " Backtrace:: %s"
                                     % (parent_resource, err,
                                        traceback.format_exc()))
                        return self.return_error(err, start_response)
                else:
                    try:
                        if parent_resource == 'stats':
                            result = self.get_stats(parent_resource, resource_id)
                        elif parent_resource == 'lbstats':
                            result = self.get_lbstats(parent_resource,
                                        resource_id)
                        else:
                            result = self.show_method(parent_resource, resource_id)
                    except KeyError:
                        return self.return_not_found(parent_resource,
                                                     resource_id,
                                                     start_response)
                    except Exception, err:
                        logger.error("Failed to show %s. Error :: %s."
                                     " Backtrace:: %s"
                                     % (parent_resource, err,
                                        traceback.format_exc()))
                        return self.return_error(err, start_response)
            elif method == 'DELETE':
                resource_id = self.get_resource_id(parent_resource, url_parts)
                try:
                    result = self.delete_method(parent_resource, resource_id)
                except KeyError:
                        return self.return_not_found(parent_resource,
                                                     resource_id,
                                                     start_response)
                except Exception, err:
                    logger.error("Failed to delete %s. Error :: %s."
                                 " Backtrace:: %s" % (parent_resource,
                                                      err,
                                                      traceback.format_exc()))
                    return self.return_error(err, start_response)
            else:
                result = "Invalid URL"

        ## response
        status = '200 OK'  # HTTP Status
        response_body = json.dumps(result)
        response_headers = [('Content-type', 'application/json'),
                            ('Content-length', str(len(response_body)))]
        start_response(status, response_headers)
        return [response_body]

    def start(self, application, host, port):
        """
        Run a WSGI server with the given application.
        """
        sock = eventlet.listen((host, port))
        eventlet.wsgi.server(sock, application, log_output=False, debug=False)


def sig_handler(signum, frame):
    if signum in [2, 3, 11, 15]:
        logger.info("Recieved signal: %r. Thus exiting " % signum)
        sys.exit()
    else:
        logger.info("Caught singal: %r. Ignoring " % signum)
        pass


def main(argv):
    global logger

    parser = optparse.OptionParser()
    parser.add_option("-i", "--ip-addr",
                      dest="ipaddr",
                      help="listen host IP address")
    parser.add_option("-p", "--port",
                      dest="port",
                      type='int',
                      help="listen port number")
    parser.add_option("-v", "--verbose",
                      action="store_true",
                      default=False,
                      dest="verbose")
    parser.add_option("-d", "--debug",
                      action="store_true",
                      default=False,
                      dest="debug")
    (options, _) = parser.parse_args()
    if options.ipaddr is None:
        parser.error("Listen IPADDR must be given. See --help")
    elif options.port is None:
        parser.error("Listen PORT must be given. See --help")

    # set logger
    logger = logging.getLogger('HAPROXY_AGENT')
    if options.debug:
        logger.setLevel(logging.DEBUG)
    elif options.verbose:
        logger.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.ERROR)
    handler = logging.FileHandler('/var/log/haproxy_agent.log')
    formatter = logging.Formatter(
        ('%(asctime)s'
         + ' %(levelname)s'
         + ' %s' % 'HAPROXY_AGENT'
         + ' %(module)s %(message)s')
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    formatter = logging.Formatter('haproxy %(name)s %(funcName)s() '
                                  '%(levelname)s %(message)s')
    sys_handler = logging.handlers.SysLogHandler(address=('localhost', 514))
    sys_handler.setFormatter(formatter)
    sys_handler.setLevel(logging.DEBUG)
    logger.addHandler(sys_handler)
    logger.debug("Added syslog handler")

    signal.signal(signal.SIGTERM, sig_handler)
    signal.signal(signal.SIGINT, sig_handler)

    server_ip = cfg.get_interface_to_bind()
    cfg.update_sshd_listen_ip(server_ip)

    with HaproxyAgent() as haproxy_agent:
        haproxy_agent.start(haproxy_agent.server, server_ip, options.port)


if __name__ == '__main__':
    main(sys.argv)
