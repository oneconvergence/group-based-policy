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

import httplib2
import httplib
import socket
import exceptions
from oslo_config import cfg
import six.moves.urllib.parse as urlparse
import json
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


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
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        if self.timeout:
            self.sock.settimeout(self.timeout)
        try:
            self.sock.connect(self.socket_path)
        except socket.error, exc:
            raise RestClientException(
                "Caught exception socket.error : %s" % exc)


class UnixRestClient():

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
        path = '/v1/nfp/' + path
        body = json.dumps(body)
        url = urlparse.urlunsplit((
            request_method,
            server_addr,
            path,
            None,
            ''))
        try:
            resp, content = self._http_request(url, method_type,
                                               headers=headers, body=body)
            LOG.info("%s:%s" % (resp, content))
        except RestClientException as rce:
            LOG.info("ERROR : %s" % (rce))
            raise rce

        success_code = [200, 201, 202, 204]
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
            raise Exception(_('Unhandled Exception code: %s %s') %
                            (resp.status, resp.reason))


def get(path):
    headers = {'content-type': 'application/json'}
    return UnixRestClient().send_request(path, 'GET', headers=headers)


def put(path, body):
    headers = {'content-type': 'application/json'}
    return UnixRestClient().\
        send_request(path, 'PUT', headers=headers, body=body)


def post(path, body, delete=False):
    headers = {'content-type': 'application/json'}
    if delete:
        headers.update({'method-type': 'DELETE'})
    else:
        headers.update({'method-type': 'CREATE'})
    return UnixRestClient().\
        send_request(path, 'POST', headers=headers, body=body)
