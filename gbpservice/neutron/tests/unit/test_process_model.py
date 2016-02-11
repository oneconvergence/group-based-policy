import os
import sys
import ast
import json
import time
from oslo_log import log as logging
from neutron.agent.common import config
from neutron.common import config as common_config
from gbpservice.neutron.nsf.core.main import ServiceController
from gbpservice.neutron.nsf.core.main import Event
from gbpservice.neutron.nsf.core.main import EventHandlers
from gbpservice.neutron.nsf.core.main import RpcAgent
from gbpservice.neutron.nsf.core.main import Serializer 
from gbpservice.neutron.nsf.core import cfg as core_cfg
from oslo_config import cfg
from neutron.common import rpc as n_rpc
import oslo_messaging as messaging
import unittest
from mock import patch, Mock
import psutil
import multiprocessing as multiprocessing


class Test_Process_Model(unittest.TestCase):

	@patch('gbpservice.neutron.nsf.core.main.Queue.put')
	def test_service_create(self, mock_put):
<<<<<<< HEAD
		ev = self.sc.event(
			id='SERVICE_CREATE', data=self.service1,
			binding_key=self.service1['id'],
			key=self.service1['id'], serialize=True
		)
		self.sc.rpc_event(ev)
=======
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
>>>>>>> 10dff656b7152182382d91b67fea3ecdc82a681d
		self.assertIsNotNone(ev.worker_attached)
		mock_put.assert_called_once_with(ev)

	@patch('gbpservice.neutron.nsf.core.main.Queue.put')
	def test_events_with_binding_keys(self, mock_put):
<<<<<<< HEAD
		ev_create = self.sc.event(
			id='SERVICE_CREATE', data=self.service1,
			binding_key=self.service1['tenant'],
			key=self.service1['id'], serialize=True
		)
		ev_delete = self.sc.event(
			id='SERVICE_DELETE', data=self.service1,
			binding_key=self.service1['tenant'],
			key=self.service1['id'], serialize=True
		)
		self.sc.rpc_event(ev_create)
		self.sc.rpc_event(ev_delete)
=======
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
>>>>>>> 10dff656b7152182382d91b67fea3ecdc82a681d
		self.assertIsNotNone(ev_create.worker_attached)
		self.assertIsNotNone(ev_delete.worker_attached)
		self.assertEqual(ev_create.worker_attached, ev_delete.worker_attached)
		self.assertEqual(mock_put.call_count, 2)
	
	@patch('gbpservice.neutron.nsf.core.main.Queue.put')
<<<<<<< HEAD
	def test_loadbalancing_events(self, mock_put):
		event1 = self.sc.event(
			id='SERVICE_CREATE', data=self.service1,
			binding_key=self.service1['id'],
			key=self.service1['id'], serialize=True
		)
=======
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
>>>>>>> 10dff656b7152182382d91b67fea3ecdc82a681d
		self.sc.rpc_event(event1) 
		count = 0
		for worker in self.sc.workers:
			if event1.worker_attached == worker[0].pid:
				rrid_event1 = count
				break
			count = count + 1
<<<<<<< HEAD
		
		event2 = self.sc.event(
			id='SERVICE_CREATE', data=self.service2,
			binding_key=self.service2['id'],
			key=self.service2['id'], serialize=True
		)
		self.sc.rpc_event(event2)
		if rrid_event1 + 1 == len(self.sc.workers):
			self.assertEqual(event2.worker_attached, self.sc.workers[0][0].pid)
		else:	
			self.assertEqual(
				event2.worker_attached, 
				self.sc.workers[rrid_event1 + 1][0].pid
			)
		self.assertEqual(mock_put.call_count, 2)
		
	@patch('gbpservice.neutron.nsf.core.main.Serializer.serialize')
	def test_serialize_events_serialize_false(self, mock_serialize):
		event1 = self.mock_event(
			id='SERVICE_CREATE', data=self.service1,
			binding_key=self.service1['id'],
			key=self.service1['id'], serialize=False, 
			worker_attached=self.sc.workers[0][0].pid
		)
		serialized_event1 = self.sc.serialize(event1)
		self.assertEqual(mock_serialize.call_count, 0)
		self.assertEqual(serialized_event1, event1)
	
	@patch('gbpservice.neutron.nsf.core.main.Serializer.serialize')
	def test_serialize_events_serialze_true(self, mock_serialize):
		event1 = self.mock_event(
			id='SERVICE_CREATE', data=self.service1,
			binding_key=self.service1['id'],
			key=self.service1['id'], serialize=True, 
			worker_attached=self.sc.workers[0][0].pid
		)
		mock_serialize.return_value = True
		serialized_event1 = self.sc.serialize(event1)
		mock_serialize.assert_called_once_with(event1)
		self.assertEqual(serialized_event1, None)
		mock_serialize.return_value = False
		serialized_event1 = self.sc.serialize(event1)
		self.assertEqual(serialized_event1, event1) 

	@patch('gbpservice.neutron.nsf.core.main.Serializer')    
	def test_serializer_serialize(self, mocked_serializer):
		event1 = self.mock_event(
			id='SERVICE_CREATE', data=self.service1,
			binding_key=self.service1['id'],
			key=self.service1['id'], serialize=True,
			worker_attached=self.sc.workers[0][0].pid
		)
		mocked_serializer_map = Mock()
		mocked_serializer._serializer_map = mocked_serializer_map
		mocked_serializer_map = {}
		self.assertEqual(self.serializer.serialize(event1), False)
		mocked_serializer_map = self.create_serializer_map(
			self.sc.workers[0][0].pid, 
			self.service1['id']
		)
		self.assertEqual(self.serializer.serialize(event1), True)

	def test_worker_process_initilized(self):
		no_of_processes = 0
		for proc in psutil.process_iter():
			for worker in self.sc.workers:
				if proc.pid == worker[0].pid:
					no_of_processes = no_of_processes + 1
				if no_of_processes == len(self.sc.workers):
					break
		self.assertEqual(no_of_processes, len(self.sc.workers))

	def create_serializer_map(self, worker_attached, binding_key):
		serializer_map = {}
		serializer_map[worker_attached] = {}
		mapp = serializer_map[worker_attached]
		mapp[binding_key] = {'in_use': True, 'queue': []}
		return serializer_map	

	def mock_event(self, **kwargs):
		event = self.sc.event(**kwargs)
		event.poll_event = \
			kwargs.get('poll_event') if 'poll_event' in kwargs else None
		event.worker_attached = \
			kwargs.get('worker_attached') if 'worker_attached' in kwargs else None
		event.last_run = kwargs.get('last_run') if 'last_run' in kwargs else None
		event.max_times = kwargs.get('max_times') if 'max_times' in kwargs else -1
		return event
=======
			
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
                self.assertEqual(mock_put.call_count, 2)

		
	@patch('gbpservice.neutron.nsf.core.main.Serializer.serialize')
	def test_serialize_events_serialize_false(self, mock_serialize):
		 service1 ={'id': 'sc2f2b13-e284-44b1-9d9a-2597e216271a',
                                'tenant': '40af8c0695dd49b7a4980bd1b47e1a1b',
                                'servicechain': 'sc2f2b13-e284-44b1-9d9a-2597e2161c',
                                'servicefunction': 'sf2f2b13-e284-44b1-9d9a-2597e216561d',
                                'vip_id': '13948da4-8dd9-44c6-adef-03a6d8063daa',
                                'service_vendor': 'haproxy',
                                'service_type': 'loadbalancer',
                                'ip': '192.168.20.199'
                                }
                 event1 = self.mock_event(id='SERVICE_CREATE', data=service1,
                                        binding_key=service1['id'],
                                        key=service1['id'], serialize=False, 
					worker_attached = self.sc.workers[0][0].pid)
		 serialized_event1 = self.sc.serialize(event1)
		 self.assertEqual(mock_serialize.call_count, 0)
		 self.assertEqual(serialized_event1, event1)
	
	@patch('gbpservice.neutron.nsf.core.main.Serializer.serialize')
	def test_serialize_events_serialze_true(self, mock_serialize):
            service1 ={'id': 'sc2f2b13-e284-44b1-9d9a-2597e216271a',
                                'tenant': '40af8c0695dd49b7a4980bd1b47e1a1b',
                                'servicechain': 'sc2f2b13-e284-44b1-9d9a-2597e2161c',
                                'servicefunction': 'sf2f2b13-e284-44b1-9d9a-2597e216561d',
                                'vip_id': '13948da4-8dd9-44c6-adef-03a6d8063daa',
                                'service_vendor': 'haproxy',
                                'service_type': 'loadbalancer',
                                'ip': '192.168.20.199'
                                }
	    event1 = self.mock_event(id='SERVICE_CREATE', data=service1,
                                        binding_key=service1['id'],
                                        key=service1['id'], serialize=True, 
					worker_attached = self.sc.workers[0][0].pid)
	    
	    mock_serialize.return_value = True
	    serialized_event1 = self.sc.serialize(event1)
	    mock_serialize.assert_called_once_with(event1)
	    self.assertEqual(serialized_event1, None)
	    mock_serialize.return_value = False
            serialized_event1 = self.sc.serialize(event1)
	    self.assertEqual(serialized_event1, event1)
        
	 
	@patch('gbpservice.neutron.nsf.core.main.Serializer')    
	def test_serializer_serialize(self, mocked_serializer):
	    service1 ={'id': 'sc2f2b13-e284-44b1-9d9a-2597e216271a',
                                'tenant': '40af8c0695dd49b7a4980bd1b47e1a1b',
                                'servicechain': 'sc2f2b13-e284-44b1-9d9a-2597e2161c',
                                'servicefunction': 'sf2f2b13-e284-44b1-9d9a-2597e216561d',
                                'vip_id': '13948da4-8dd9-44c6-adef-03a6d8063daa',
                                'service_vendor': 'haproxy',
                                'service_type': 'loadbalancer',
                                'ip': '192.168.20.199'
                                }
            event1 = self.mock_event(id='SERVICE_CREATE', data=service1,
                                        binding_key=service1['id'],
                                        key=service1['id'], serialize=True,
                                        worker_attached = self.sc.workers[0][0].pid)
	    mocked_serializer_map = Mock()
	    mocked_serializer._serializer_map = mocked_serializer_map
	    mocked_serializer_map = {}
            self.assertEqual(self.serializer.serialize(event1) , False)
            #mock_append.assert_called_once_with(event1)
            #mapp = mocked_serializer_map[event1.worker_attached]
	    #self.assertTrue(event1 in mapp[event1.binding_key]['queue'])
	    
	    mocked_serializer_map = self.create_serializer_map(self.sc.workers[0][0].pid, service1['id'])
            self.assertEqual(self.serializer.serialize(event1) , True)
	
	def test_worker_process_initilized(self):
            no_of_processes = 0
            for proc in psutil.process_iter():
	        for worker in self.sc.workers:
		    if proc.pid == worker[0].pid:
			no_of_processes = no_of_processes+1
			if no_of_processes == len(self.sc.workers):
                            break;
            self.assertEqual(no_of_processes, len(self.sc.workers))
	    
		
	

	def create_serializer_map(self, worker_attached, binding_key):
	    serializer_map = {}
            serializer_map[worker_attached] = {}
            mapp = serializer_map[worker_attached]
            mapp[binding_key] = {'in_use': True, 'queue': []}
            return serializer_map
	    	

	def mock_event(self, **kwargs):
            event = self.sc.event(**kwargs)
	    event.poll_event = kwargs.get(
            'poll_event') if 'poll_event' in kwargs else None
	    event.worker_attached = kwargs.get(
            'worker_attached') if 'worker_attached' in kwargs else None
	    event.last_run = kwargs.get(
            'last_run') if 'last_run' in kwargs else None
	    event.max_times = kwargs.get(
            'max_times') if 'max_times' in kwargs else -1
	    return event
			
>>>>>>> 10dff656b7152182382d91b67fea3ecdc82a681d
							
	def setUp(self):  
		config.setup_logging()
		cfg.CONF.register_opts(core_cfg.OPTS)
<<<<<<< HEAD
		modules = []
		config.register_interface_driver_opts_helper(cfg.CONF)
		config.register_agent_state_opts_helper(cfg.CONF)
		config.register_root_helper(cfg.CONF)
		self.service1 = {
			'id': 'sc2f2b13-e284-44b1-9d9a-2597e216271a',
			'tenant': '40af8c0695dd49b7a4980bd1b47e1a1b',
			'servicechain': 'sc2f2b13-e284-44b1-9d9a-2597e2161c',
			'servicefunction': 'sf2f2b13-e284-44b1-9d9a-2597e216561d',
			'vip_id': '13948da4-8dd9-44c6-adef-03a6d8063daa',
			'service_vendor': 'haproxy',
			'service_type': 'loadbalancer',
			'ip': '192.168.20.199'
		}
		self.service2 = {
			'id': 'sc2f2b13-e284-44b1-9d9a-2597e216272a',
			'tenant': '40af8c0695dd49b7a4980bd1b47e1a2b',
			'servicechain': 'sc2f2b13-e284-44b1-9d9a-2597e216562c',
			'servicefunction': 'sf2f2b13-e284-44b1-9d9a-2597e216562d',
			'mac_address': 'fa:16:3e:3f:93:05',
			'service_vendor': 'vyos',
			'service_type': 'firewall',
			'ip': '192.168.20.197'
		}

=======
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
>>>>>>> 10dff656b7152182382d91b67fea3ecdc82a681d
		self._conf = cfg.CONF
		self._modules = modules
		self.sc = ServiceController(cfg.CONF, modules)
		self.serializer = Serializer(self.sc)
<<<<<<< HEAD
		self.sc.start()	
=======
		self.sc.start()
    		
>>>>>>> 10dff656b7152182382d91b67fea3ecdc82a681d

#if __name__ == '__main__':
	#suite = unittest.TestSuite()
	#suite.addTest(Test_Process_Model('test_service_create'))
	#suite.addTest(Test_Process_Model('test_events_with_binding_keys'))
	#suite.addTest(Test_Process_Model('test_loadbalancing_events'))
	#suite.addTest(Test_Process_Model('test_serialize_events_serialize_false'))
	#suite.addTest(Test_Process_Model('test_serialize_events_serialze_true'))
	#suite.addTest(Test_Process_Model('test_serializer_serialize'))
<<<<<<< HEAD
	#suite.addTest(Test_Process_Model('test_worker_process_initilized'))
	#suite.addTest(Test_Process_Model('test_loadbalancing_events_without_bindingkeys'))
	unittest.TextTestRunner(verbosity=2).run(suite)					
=======
        #suite.addTest(Test_Process_Model('test_worker_process_initilized'))
	#unittest.TextTestRunner(verbosity=2).run(suite)					
>>>>>>> 10dff656b7152182382d91b67fea3ecdc82a681d
