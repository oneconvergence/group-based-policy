import os
import sys
import ast
import json
import time
#import pdb

from oslo_log import log as logging
from neutron.agent.common import config
from neutron.common import config as common_config
from gbpservice.neutron.nsf.core.main import ServiceController
from gbpservice.neutron.nsf.core.main import Event
from gbpservice.neutron.nsf.core.main import EventHandlers
from gbpservice.neutron.nsf.core.main import RpcAgent
from gbpservice.neutron.nsf.core import cfg as core_cfg
#from gbpservice.neutron.nsf.core.main import modules_import
from oslo_config import cfg
from neutron.common import rpc as n_rpc
import oslo_messaging as messaging
import unittest
from mock import patch, PropertyMock, create_autospec

class Test_Process_Model(unittest.TestCase):

        @patch('gbpservice.neutron.nsf.core.main.Queue.put')
	def test_service_create(self, mock_put):
		
    		'''
    		Write the unit test logic here
    		'''
    		service1 = {'id': 'sc2f2b13-e284-44b1-9d9a-2597e216271a',
                		'tenant': '40af8c0695dd49b7a4980bd1b47e1a1b',
                		'servicechain': 'sc2f2b13-e284-44b1-9d9a-2597e2161c',
                		'servicefunction': 'sf2f2b13-e284-44b1-9d9a-2597e216561d',
                		'vip_id': '13948da4-8dd9-44c6-adef-03a6d8063daa',
                		'service_vendor': 'haproxy',
                		'service_type': 'loadbalancer',
                		'ip': '192.168.20.199'
                		}
    		ev = self.sc.event(id='SERVICE_CREATE', data=service1,
                  		binding_key=service1['id'],
                  		key=service1['id'], serialize=True)
                self.sc.rpc_event(ev)
		self.assertIsNotNone(ev.worker_attached)
		mock_put.assert_called_once_with(ev)

	@patch('gbpservice.neutron.nsf.core.main.Queue.put')
	def test_events_with_binding_keys(self, mock_put):
		service1 ={'id': 'sc2f2b13-e284-44b1-9d9a-2597e216271a',
                                'tenant': '40af8c0695dd49b7a4980bd1b47e1a1b',
                                'servicechain': 'sc2f2b13-e284-44b1-9d9a-2597e2161c',
                                'servicefunction': 'sf2f2b13-e284-44b1-9d9a-2597e216561d',
                                'vip_id': '13948da4-8dd9-44c6-adef-03a6d8063daa',
                                'service_vendor': 'haproxy',
                                'service_type': 'loadbalancer',
                                'ip': '192.168.20.199'
                                }
		ev_create = self.sc.event(id='SERVICE_CREATE', data=service1,
                                binding_key=service1['tenant'],
                                key=service1['id'], serialize=True)
		ev_delete = self.sc.event(id='SERVICE_DELETE', data=service1,
                  binding_key=service1['tenant'],
                  key=service1['id'], serialize=True)
		self.sc.rpc_event(ev_create)
	        self.sc.rpc_event(ev_delete)
		self.assertIsNotNone(ev_create.worker_attached)
		self.assertIsNotNone(ev_delete.worker_attached)
		self.assertEqual(ev_create.worker_attached, ev_delete.worker_attached)
		self.assertEqual(mock_put.call_count, 2)
	
	@patch('gbpservice.neutron.nsf.core.main.Queue.put')
        def test_loadbalancing_events(self, mock_put):
		service1 ={'id': 'sc2f2b13-e284-44b1-9d9a-2597e216271a',
                                'tenant': '40af8c0695dd49b7a4980bd1b47e1a1b',
                                'servicechain': 'sc2f2b13-e284-44b1-9d9a-2597e2161c',
                                'servicefunction': 'sf2f2b13-e284-44b1-9d9a-2597e216561d',
                                'vip_id': '13948da4-8dd9-44c6-adef-03a6d8063daa',
                                'service_vendor': 'haproxy',
                                'service_type': 'loadbalancer',
                                'ip': '192.168.20.199'
                                }
		event1 = self.sc.event(id='SERVICE_CREATE', data=service1,
					binding_key=service1['id'],
					key=service1['id'], serialize=True)
		self.sc.rpc_event(event1) 
		count = 0
		for worker in self.sc.workers:
			if event1.worker_attached == worker[0].pid:
				rrid_event1 = count
				break
			count = count + 1
			
		service2 = {'id': 'sc2f2b13-e284-44b1-9d9a-2597e216272a',
                		'tenant': '40af8c0695dd49b7a4980bd1b47e1a2b',
                		'servicechain': 'sc2f2b13-e284-44b1-9d9a-2597e216562c',
                		'servicefunction': 'sf2f2b13-e284-44b1-9d9a-2597e216562d',
                		'mac_address': 'fa:16:3e:3f:93:05',
                		'service_vendor': 'vyos',
                		'service_type': 'firewall',
                		'ip': '192.168.20.197'
               		 }
		event2 = self.sc.event(id='SERVICE_CREATE', data=service2,
					binding_key=service2['id'],
					key=service2['id'], serialize=True)
		self.sc.rpc_event(event2)
		if rrid_event1+1 == len(self.sc.workers):
			self.assertEqual(event2.worker_attached, self.sc.workers[0][0].pid)
		else:	
			self.assertEqual(event2.worker_attached, self.sc.workers[rrid_event1+1][0].pid)
		#self.assertNotEqual(event1.worker_attached, event2.worker_attached)
                self.assertEqual(mock_put.call_count, 2)

	
			
							
	def setUp(self):  #*args, **kwargs):
		#pdb.set_trace()
		#super(Test_Process_Model, self).__init__('test_events_with_binding_keys')
		config.setup_logging()
		cfg.CONF.register_opts(core_cfg.OPTS)
		modules_dir = '/opt/stack/gbp/gbpservice/neutron/nsf/core/test'
    		syspath = sys.path
    		sys.path = [modules_dir] + syspath
    		try:
        		files = os.listdir(modules_dir)
    		except OSError:
        		print "Failed to read files"
        	files = []
                modules = []
    		for fname in files:
        		print (fname)
        		if fname.endswith(".py") and fname != '__init__.py' and fname != 'test_process_model.py':
            			module = __import__(cfg.CONF.modules_dir,
                                	globals(), locals(), [fname[:-3]], -1)
            			modules += [eval('module.%s' % (fname[:-3]))]
            			# modules += [__import__(fname[:-3])]
    		sys.path = syspath
		config.register_interface_driver_opts_helper(cfg.CONF)
		config.register_agent_state_opts_helper(cfg.CONF)
		config.register_root_helper(cfg.CONF)
		self._conf = cfg.CONF
		self._modules = modules
		self.sc = ServiceController(cfg.CONF, modules)
		self.sc.start()
    		

'''if __name__ == '__main__':
	suite = unittest.TestSuite()
	suite.addTest(Test_Process_Model('test_service_create'))
	suite.addTest(Test_Process_Model('test_events_with_binding_keys'))
	unittest.TextTestRunner(verbosity=2).run(suite)	'''				
