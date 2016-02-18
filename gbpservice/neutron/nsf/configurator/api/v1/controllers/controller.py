import pecan
import configparser
import sys
import json
from pecan import rest
from pecan import expose, response, request, abort, conf

import eventlet
import time
import threading
import sys
import os
from multiprocessing import Process, Queue, Lock
from oslo_config import cfg
import oslo_messaging
from neutron.agent.common import config
from neutron.common import config as common_config
from neutron.common import rpc as n_rpc

import constants


class Controller(rest.RestController):

    """controller class for handling all the curl request"""
    
    def __init__(self, module_name):
        self.rpcclient = RPCClient(topic=constants.TOPIC, host='hostname')
        self.module_name = module_name
        super(Controller, self).__init__()

    @expose(method='GET', content_type='application/json')
    def get(self, **body):
        try:
            body = None
            if request.is_body_readable:
                body = request.json_body

            return self.get_notifications(body)
        except Exception as e:
            return json.dumps({'err_msg': e.message})

    @expose(method='POST', content_type='application/json')
    def post(self, **body):
        import pdb
        pdb.set_trace()
        try:
            body = None
            if request.is_body_readable:
                body = request.json_body
            if self.module_name == "device_config":
                return self._create_network_device_config(body)
            else:
                return self._create_network_service_config(body)
        except Exception as e:
            return json.dumps({'err_msg': e.message})

    @expose(method='PUT', content_type='application/json')
    def put(self, **body):
        try:
            body = None
            if request.is_body_readable:
                body = request.json_body

            header = request.headers
            method = header.get('Method-type')
            if method == 'UPDATE':
                if self.module_name == "device_config":
                    return self._update_network_device_config(body)
                else:
                    return self._update_network_service_config(body)
            else:
                if self.module_name == "device_config":
                    return self._delete_network_device_config(body)
                else:
                    return self._delete_network_service_config(body)
        except Exception as e:
            return json.dumps({'err_msg': e.message})

    def _create_network_device_config(self, body):
        request_data = body.get("request_data")
        try:
            return json.dumps(
                self.rpcclient.create_network_device_config(request_data))
        except Exception as e:
            return json.dumps({'err_msg': e.message})

    def _create_network_function_config(self, body):
        request_data = body.get("request_data")
        try:
            return json.dumps(
                self.rpcclient.create_network_service_config(request_data))
        except Exception as e:
            return json.dumps({'err_msg': e.message})

    def _update_network_device_config(self, body):
        request_data = body.get("request_data")
        try:
            return json.dumps(
                self.rpcclient.update_network_device_config(request_data))
        except Exception as e:
            return json.dumps({'err_msg': e.message})

    def _update_network_service_config(self, body):
        request_data = body.get("request_data")
        try:
            return json.dumps(
                self.rpcclient.update_network_service_config(request_data))
        except Exception as e:
            return json.dumps({'err_msg': e.message})

    def _delete_network_device_config(self, body):
        request_data = body.get("request_data")
        try:
            return json.dumps(
                self.rpcclient.delete_network_device_config(request_data))
        except Exception as e:
            return json.dumps({'err_msg': e.message})

    def _delete_network_service_config(self, body):
        request_data = body.get("request_data")
        try:
            return json.dumps(
                self.rpcclient.delete_network_service_config(request_data))
        except Exception as e:
            return json.dumps({'err_msg': e.message})


class RPCClient(object):

    """send RPC call/cast on behalf of controller class according to the curl request"""
    API_VERSION = '1.0'

    def __init__(self, topic, host):

        self.topic = topic
        self.host = host
        target = oslo_messaging.Target(
            topic=self.topic,
            version=self.API_VERSION)
        n_rpc.init(cfg.CONF)
        self.client = n_rpc.get_client(target)

    def create_network_device_config(self, request_data):
        context = request_data['config'][0]['kwargs']['context']
        del request_data['config'][0]['kwargs']['context']
        cctxt = self.client.prepare(server=self.host)
        return cctxt.cast(context, 'create_network_device_config',
                          request_data=request_data)

    def create_network_service_config(self, request_data):
        context = request_data['config'][0]['kwargs']['context']
        del request_data['config'][0]['kwargs']['context']
        cctxt = self.client.prepare(server=self.host)
        return cctxt.cast(context, 'create_network_service_config',
                          request_data=request_data)

    def update_network_device_config(self, request_data):
        context = request_data['config'][0]['kwargs']['context']
        del request_data['config'][0]['kwargs']['context']
        cctxt = self.client.prepare(server=self.host)
        return cctxt.cast(context, 'update_network_device_config',
                          request_data=request_data)

    def update_network_service_config(self, request_data):
        context = request_data['config'][0]['kwargs']['context']
        del request_data['config'][0]['kwargs']['context']
        cctxt = self.client.prepare(server=self.host)
        return cctxt.cast(context, 'update_network_service_config',
                          request_data=request_data)

    def delete_network_device_config(self, request_data):
        context = request_data['config'][0]['kwargs']['context']
        del request_data['config'][0]['kwargs']['context']
        cctxt = self.client.prepare(server=self.host)
        return cctxt.cast(context, 'delete_network_device_config',
                          request_data=request_data)

    def delete_network_service_config(self, request_data):
        context = request_data['config'][0]['kwargs']['context']
        del request_data['config'][0]['kwargs']['context']
        cctxt = self.client.prepare(server=self.host)
        return cctxt.cast(context, 'delete_network_service_config',
                          request_data=request_data)
