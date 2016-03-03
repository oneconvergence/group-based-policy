import eventlet
import time
import unittest
import mock
import threading
import sys
import os
from multiprocessing import Process, Queue, Lock

from oslo_config import cfg
from oslo_log import log as logging
import oslo_messaging

from gbpservice.nfp.configurator.agents import firewall as fw

from neutron.agent.common import config
from neutron.common import config as common_config
from neutron.common import rpc as n_rpc

eventlet.monkey_patch()

LOG = logging.getLogger(__name__)

CONFIGURATOR_TOPIC = "configurator"
HOST = 'configurator-dpak-new'


class ConfiguratorRpcClient(object):
    """ Client side of service manager """

    API_VERSION = '1.0'

    def __init__(self, host=HOST, topic=CONFIGURATOR_TOPIC):
        self.host = host
	super(ConfiguratorRpcClient, self).__init__()
        target = oslo_messaging.Target(
                topic=topic,
                version=self.API_VERSION)
	n_rpc.init(cfg.CONF)
        self.client = n_rpc.get_client(target)
	data1 = {'context': {},
		'firewall':    {
                     "admin_state_up": True,
                     "description": "",
                     "firewall_policy_id": "c69933c1-b472-44f9-8226-30dc4ffd454c",
                     "id": "3b0ef8f4-82c7-44d4-a4fb-6177f9a21977",
                     "name": "",
                     "status": "PENDING_CREATE",
                     "router_ids": [
                         "650bfd2f-7766-4a0d-839f-218f33e16998"
                     ],
                     "tenant_id": "45977fa2dbd7482098dd68d0d8970117",
		     "firewall_rule_list": True,
                     'description': {'vm_management_ip': '192.168.20.194'}}, 
		 'host': 'host'}
	self.request_data1 = {
                 'info':   {
                             'version': 'v1',
                             'type': 'firewall'},

                 'config': [
                     {'resource': 'firewall',
                         'kwargs': data1}
                    ]
                }
	data2 = { 'context': {'hi': 'hu'},
		'kwargs': {
		'service_type': 'firewall',
		'request_info': {'id': '1234'},
                'vm_mgmt_ip': '172.24.4.5',
                'mgmt_ip': '172.24.4.5',
                'source_cidrs': ['1.2.3.4/24'],
                'destination_cidr': ['1.2.3.4/24'],
                'gateway_ip': '1.2.3.4',
                'provider_interface_position': '1',
		'rule_info': {
                        'active_provider_mac': '00:0a:95:9d:68:16',
                        'provider_mac': '00:0a:95:9d:68:16',
                        'active_stitching_mac': '00:0a:95:9d:68:25',
                        'stitching_mac': '00:0a:95:9d:68:25',
                        'active_fip': '172.24.4.5',
                        'fip': '172.24.4.5',
                        'service_id': '1df1cd7a-d82e-4bbd-8b26-a1f106075a6b',
                        'tenant_id': '6bb921bb81254b3e90e3d8c71a6d72dc'
               }, 'service_type': 'firewall'}  }
	self.request_data2 = {   
                 'info':   {
                             'version': 'v1'},

                 'config': [
                        {'resource': 'interfaces',
                         'kwargs': data2},
                        {'resource': 'routes',
                         'kwargs': data2}
                    ]
                }


    def test_create_firewall(self):
	cctxt = self.client.prepare(server=self.host)
	print "GNG to call"
        return cctxt.call(self, 'create_network_service_config',
                          request_data=self.request_data1)
	print "Done calling"

    def test_delete_firewall(self):
	cctxt = self.client.prepare(server=self.host)
        return cctxt.call(self, 'delete_network_service_config',
                          request_data=self.request_data1)

    def test_update_firewall(self):
	cctxt = self.client.prepare(server=self.host)
        return cctxt.call(self, 'update_network_service_config',
                          request_data=self.request_data1)

    def configure_interfaces(self):
        cctxt = self.client.prepare(server=self.host)
        return cctxt.call(self, 'create_network_device_config',
			  request_data=self.request_data2)

    def clear_interfaces(self):
        cctxt = self.client.prepare(server=self.host)
        return cctxt.call(self, 'delete_network_device_config',
                          request_data=self.request_data2)

    def configure_source_routes(self):
	self.request_data2['config'][0].update({'resource': 'routes'})
        cctxt = self.client.prepare(server=self.host)
        return cctxt.call(self, 'create_network_device_config',
			  request_data=self.request_data2)

    def delete_source_routes(self):
	self.request_data2['config'][0].update({'resource': 'routes'})
        cctxt = self.client.prepare(server=self.host)
        return cctxt.call(self, 'delete_network_device_config',
			  request_data=self.request_data2)

    def to_dict(self):
	return {}

client = ConfiguratorRpcClient(HOST, CONFIGURATOR_TOPIC)
print client
#client.test_create_firewall()
#client.test_delete_firewall()
#client.test_update_firewall()

client.configure_interfaces()
#client.clear_interfaces()
#client.configure_source_routes()
#client.delete_source_routes()

