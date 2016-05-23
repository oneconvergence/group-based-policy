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

import exceptions
import zlib

from gbpservice.nfp.core import common as nfp_common
from gbpservice.nfp.core import log as nfp_logging
import httplib
import httplib2

from oslo_serialization import jsonutils

import six.moves.urllib.parse as urlparse
import socket

LOG = nfp_logging.getLogger(__name__)


class RestClientException(exceptions.Exception):

    """ RestClient Exception """


class UnixHTTPConnection(httplib.HTTPConnection):

    """Connection class for HTTP over UNIX domain socket."""

    def __init__(self, host, port=None, strict=None, timeout=None,
                 proxy_info=None):
        httplib.HTTPConnection.__init__(self, host, port, strict)
        self.timeout = timeout
        self.socket_path = '/tmp/uds_socket'

    def connect(self):
        """Method used to connect socket server."""
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        if self.timeout:
            self.sock.settimeout(self.timeout)
        try:
            self.sock.connect(self.socket_path)
        except socket.error as exc:
            raise RestClientException(
                "Caught exception socket.error : %s" % exc)


class UnixRestClient(object):

    def _http_request(self, url, method_type, headers=None, body=None):
        try:
            h = httplib2.Http()
            resp, content = h.request(
                url,
                method=method_type,
                headers=headers,
                body=body,
                connection_type=UnixHTTPConnection)
            return resp, content

        except httplib2.ServerNotFoundError:
            raise RestClientException("Server Not Found")

        except exceptions.Exception as e:
            raise RestClientException("httplib response error %s" % (e))

    def send_request(self, path, method_type, request_method='http',
                     server_addr='127.0.0.1',
                     headers=None, body=None):
        """Implementation for common interface for all unix crud requests.
        Return:Http Response
        """
        # prepares path, body, url for sending unix request.
        if method_type.upper() != 'GET':
            body = jsonutils.dumps(body)
            body = zlib.compress(body)

        path = '/v1/nfp/' + path
        url = urlparse.urlunsplit((
            request_method,
            server_addr,
            path,
            None,
            ''))

        try:
            resp, content = self._http_request(url, method_type,
                                               headers=headers, body=body)
            if content != '':
                content = zlib.decompress(content)
            LOG.info("%s:%s" % (resp, content))
        except RestClientException as rce:
            LOG.error("ERROR : %s" % (rce))
            raise rce

        success_code = [200, 201, 202, 204]
        # Evaluate responses into success and failures.
        # Raise exception for failure cases which needs
        # to be handled by caller.
        if success_code.__contains__(resp.status):
            return resp, content
        elif resp.status == 400:
            raise RestClientException("HTTPBadRequest: %s" % resp.reason)
        elif resp.status == 401:
            raise RestClientException("HTTPUnauthorized: %s" % resp.reason)
        elif resp.status == 403:
            raise RestClientException("HTTPForbidden: %s" % resp.reason)
        elif resp.status == 404:
            raise RestClientException("HttpNotFound: %s" % resp.reason)
        elif resp.status == 405:
            raise RestClientException(
                "HTTPMethodNotAllowed: %s" % resp.reason)
        elif resp.status == 406:
            raise RestClientException("HTTPNotAcceptable: %s" % resp.reason)
        elif resp.status == 408:
            raise RestClientException("HTTPRequestTimeout: %s" % resp.reason)
        elif resp.status == 409:
            raise RestClientException("HTTPConflict: %s" % resp.reason)
        elif resp.status == 415:
            raise RestClientException(
                "HTTPUnsupportedMediaType: %s" % resp.reason)
        elif resp.status == 417:
            raise RestClientException(
                "HTTPExpectationFailed: %s" % resp.reason)
        elif resp.status == 500:
            raise RestClientException("HTTPServerError: %s" % resp.reason)
        else:
            raise Exception('Unhandled Exception code: %s %s' % (resp.status,
                                                                 resp.reason))


def get(path):
    """Implements get method for unix restclient
    Return:Http Response
    """
    return UnixRestClient().send_request(path, 'GET')


def put(path, body):
    """Implements put method for unix restclient
    Return:Http Response
    """
    headers = {'content-type': 'application/octet-stream'}
    return UnixRestClient().\
        send_request(path, 'PUT', headers=headers, body=body)


def post(path, body, delete=False):
    """Implements post method for unix restclient
    Return:Http Response
    """
    # Method-Type added here,as DELETE/CREATE
    # both case are handled by post as delete also needs
    # to send data to the rest-unix-server.
    headers = {'content-type': 'application/octet-stream'}
    if delete:
        headers.update({'method-type': 'DELETE'})
    else:
        headers.update({'method-type': 'CREATE'})
    return UnixRestClient().\
        send_request(path, 'POST', headers=headers, body=body)
