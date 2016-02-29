import json
import subprocess

from neutron.common import rpc as n_rpc
from neutron.agent.common import config
from oslo_config import cfg
import oslo_messaging
from pecan import expose, request
from pecan import rest

import constants


class Controller(rest.RestController):

    """controller class for handling all the curl request"""

    def __init__(self, module_name):
        self.host = subprocess.check_output('hostname', shell=True).rstrip()
        self.rpcclient = RPCClient(topic=constants.TOPIC, host=self.host)
        self.module_name = module_name
        super(Controller, self).__init__()

    @expose(method='GET', content_type='application/json')
    def get(self):
        try:
            return self._get_notifications()
        except Exception as e:
            return json.dumps({'err_msg': e.args})

    @expose(method='POST', content_type='application/json')
    def post(self, **body):
        try:
            body = None
            if request.is_body_readable:
                body = request.json_body
            if self.module_name == "create_network_function_device_config":
                return self._create_network_function_device_config(body)
            elif self.module_name == "create_network_function_config":
                return self._create_network_function_config(body)
            elif self.module_name == "delete_network_function_device_config":
                return self._delete_network_function_device_config(body)
            elif self.module_name == "delete_network_function_config":
                return self._delete_network_function_config(body)
            else:
                raise Exception('Invalid Request')
        except Exception as e:
            return json.dumps({'err_msg': e.args})

    @expose(method='PUT', content_type='application/json')
    def put(self, **body):
        try:
            body = None
            if request.is_body_readable:
                body = request.json_body

            if self.module_name == "update_network_function_device_config":
                return self._update_network_function_device_config(body)
            elif self.module_name == "update_network_function_config":
                return self._update_network_function_config(body)
            else:
                raise Exception('Invalid Request')
        except Exception as e:
            return json.dumps({'err_msg': e.args})

    def _get_notifications(self):
        try:
            return json.dumps(
                self.rpcclient.get_notifications())
        except Exception as e:
            return json.dumps({'err_msg': e.args})

    def _create_network_function_device_config(self, body):
        request_data = body
        try:
            return json.dumps(
                self.rpcclient.create_network_function_device_config(request_data))
        except Exception as e:
            return json.dumps({'err_msg': e.args})

    def _create_network_function_config(self, body):
        request_data = body
        try:
            return json.dumps(
                self.rpcclient.create_network_function_config(request_data))
        except Exception as e:
            return json.dumps({'err_msg': e.args})

    def _update_network_function_device_config(self, body):
        request_data = body
        try:
            return json.dumps(
                self.rpcclient.update_network_function_device_config(request_data))
        except Exception as e:
            return json.dumps({'err_msg': e.args})

    def _update_network_function_config(self, body):
        request_data = body
        try:
            return json.dumps(
                self.rpcclient.update_network_function_config(request_data))
        except Exception as e:
            return json.dumps({'err_msg': e.args})

    def _delete_network_function_device_config(self, body):
        request_data = body
        try:
            return json.dumps(
                self.rpcclient.delete_network_function_device_config(request_data))
        except Exception as e:
            return json.dumps({'err_msg': e.args})

    def _delete_network_function_config(self, body):
        request_data = body
        try:
            return json.dumps(
                self.rpcclient.delete_network_function_config(request_data))
        except Exception as e:
            return json.dumps({'err_msg': e.args})


class RPCClient(object):

    """send RPC call/cast on behalf of controller class
    according to the curl request"""
    API_VERSION = '1.0'

    def __init__(self, topic, host):

        self.topic = topic
        self.host = host
        target = oslo_messaging.Target(
            topic=self.topic,
            version=self.API_VERSION)
        n_rpc.init(cfg.CONF)
        self.client = n_rpc.get_client(target)

    def get_notifications(self):

        cctxt = self.client.prepare(server=self.host)
        return cctxt.call(self, 'get_notifications')

    def create_network_function_device_config(self, request_data):

        cctxt = self.client.prepare(server=self.host)
        return cctxt.cast(self, 'create_network_function_device_config',
                          request_data=request_data)

    def create_network_function_config(self, request_data):

        cctxt = self.client.prepare(server=self.host)
        return cctxt.cast(self, 'create_network_function_config',
                          request_data=request_data)

    def update_network_function_device_config(self, request_data):

        cctxt = self.client.prepare(server=self.host)
        return cctxt.cast(self, 'update_network_function_device_config',
                          request_data=request_data)

    def update_network_function_config(self, request_data):

        cctxt = self.client.prepare(server=self.host)
        return cctxt.cast(self, 'update_network_function_config',
                          request_data=request_data)

    def delete_network_function_device_config(self, request_data):

        cctxt = self.client.prepare(server=self.host)
        return cctxt.cast(self, 'delete_network_function_device_config',
                          request_data=request_data)

    def delete_network_function_config(self, request_data):

        cctxt = self.client.prepare(server=self.host)
        return cctxt.cast(self, 'delete_network_function_config',
                          request_data=request_data)

    def to_dict(self):

        return {}
