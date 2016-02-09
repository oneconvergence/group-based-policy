import os
import sys
import httplib2
import httplib
import six
import six.moves.urllib.parse as urlparse
import socket
import exceptions


class UnixDomainHTTPConnection(httplib.HTTPConnection):

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
        self.sock.connect(self.socket_path)


class RestClientException(exceptions.Exception):

    def __init__(self, message):
        self.message = message


class SendRequest():

    def _http_request(url, method_type, headers=None, body=None):
        h = httplib2.Http()
        resp, content = h.request(
            url,
            method=method_type,
            headers=headers,
            body=body,
            connection_type=UnixDomainHTTPConnection)
        return resp, content

    def send_request(path, method_type, request_method='http',
                     server_addr='127.0.0.1',
                     headers=None, body=None):
        path = '/v1/'+ path
        url = urlparse.urlunsplit((
            request_method,
            server_addr,  # a dummy value to make the request proper
            path,
            None,
            ''))
        try:
            resp, content = _http_request(url, method_type,
                                          headers=headers, body=body)
        except httplib2.ServerNotFoundError:
            raise RestClientException("Server Not Found")

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
        elif resp_code.status == 405:
            raise RestClientException(
                "HTTPMethodNotAllowed: %s" % resp.reason)
        elif resp_code.status == 406:
            raise RestClientException("HTTPNotAcceptable: %s" % resp.reason)
        elif resp_code.status == 408:
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
    return SendRequest.send_request(path, 'GET')

#PUT & DELETE Both are handled by put method#
def put(path, body, delete=False):
    headers={'content-type':'application/json'}
    if delete:
        headers.update({'method-type':'DELETE'})
    else:
        headers.update({'method-type':'UPDATE'})

    return SendRequest.send_request(path, 'PUT',
                                    headers=headers, body=body)


def post(path, body):
    headers={'content-type':'application/json'}
    return SendRequest.send_request(path, 'POST',
                                    headers=headers, body=body)
