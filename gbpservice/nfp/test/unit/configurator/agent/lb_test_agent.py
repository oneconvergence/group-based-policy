import unittest
import mock

from oslo_log import log as logging


from gbpservice.nfp.modules import configurator as cfgr
from gbpservice.nfp.configurator.agents import loadbalancer_v1 as lb
from gbpservice.nfp.configurator.agents import generic_config as gc
from gbpservice.nfp.configurator.drivers.loadbalancer.v1.haproxy.haproxy_lb_driver import HaproxyOnVmDriver
from gbpservice.nfp.configurator.lib import demuxer as demuxer_lib


LOG = logging.getLogger(__name__)


class FakeObjects(object):

    sc = 'sc'
    empty_dict = {}
    context = {'notification_data': {},
               'resource': 'context_resource'}
    lb = 'lb'
    host = 'host'
    conf = 'conf'
    kwargs = 'kwargs'
    rpcmgr = 'rpcmgr'
    nqueue = 'nqueue'
    drivers = 'drivers'
    vip_context = {'notification_data': {}, 'resource': 'vip'}

    def fake_request_data_vip(self):
        request_data = {
            "info": {
                "version": 1,
                "service_type": 'loadbalancer'
            },
            "config": [{
                "resource": "vip",
                "kwargs": {
                    "context": self.context,
                    "vip": self._fake_vip_obj()
                }}]}
        return request_data

    def fake_request_data_vip_update(self):
        request_data = {
            "info": {
                "version": 1,
                "service_type": 'loadbalancer'
            },
            "config": [{
                "resource": "vip",
                "kwargs": {
                    "context": self.context,
                    "vip": self._fake_vip_obj(),
                    "old_vip": self._fake_old_vip_obj()
                }}]}
        return request_data

    def fake_request_data_create_pool(self):
        request_data = {
            "info": {
                "version": 1,
                "service_type": 'loadbalancer'
            },
            "config": [{
                "resource": "pool",
                "kwargs": {
                    "context": self.context,
                    "pool": self._fake_pool_obj(),
                    "driver_name": "ha_proxy"
                }}]}
        return request_data

    def fake_request_data_delete_pool(self):
        request_data = {
            "info": {
                "version": 1,
                "service_type": 'loadbalancer'
            },
            "config": [{
                "resource": "pool",
                "kwargs": {
                    "context": self.context,
                    "pool": self._fake_pool_obj()
                }}]}
        return request_data

    def fake_request_data_update_pool(self):
        request_data = {
            "info": {
                "version": 1,
                "service_type": 'loadbalancer'
            },
            "config": [{
                "resource": "pool",
                "kwargs": {
                    "context": self.context,
                    "pool": self._fake_pool_obj(),
                    "old_pool": 'old_pool'
                }}]}
        return request_data

    def fake_request_data_create_member(self):
        request_data = {
            "info": {
                "version": 1,
                "service_type": 'loadbalancer'
            },
            "config": [{
                "resource": "member",
                "kwargs": {
                    "context": self.context,
                    "member": self._fake_member_obj(),
                }}]}
        return request_data

    def fake_request_data_create_hm(self):
        request_data = {
            "info": {
                "version": 1,
                "service_type": 'loadbalancer'
            },
            "config": [{
                "resource": "pool_health_monitor",
                "kwargs": {
                    "context": self.context,
                    "health_monitor": self._fake_hm_obj(),
                    "pool_id": "pool_id"
                }}]}
        return request_data

    def fake_request_data_update_hm(self):
        request_data = {
            "info": {
                "version": 1,
                "service_type": 'loadbalancer'
            },
            "config": [{
                "resource": "pool_health_monitor",
                "kwargs": {
                    "context": self.context,
                    "health_monitor": self._fake_hm_obj(),
                    "pool_id": "pool_id",
                    "old_health_monitor": "old_health_monitor"
                }}]}
        return request_data

    def fake_request_data_update_member(self):
        request_data = {
            "info": {
                "version": 1,
                "service_type": 'loadbalancer'
            },
            "config": [{
                "resource": "member",
                "kwargs": {
                    "context": self.context,
                    "member": self._fake_member_obj(),
                    "old_member": "old_member"
                }}]}
        return request_data

    def _fake_vip_obj(self):
        vip = {"status": "ACTIVE",
               "protocol": "TCP",
               "description": {"floating_ip": "192.168.100.149",
                               "provider_interface_mac":
                               "aa:bb:cc:dd:ee:ff"},
               "address": "42.0.0.14",
               "protocol_port": 22,
               "port_id": "cfd9fcc0-c27b-478b-985e-8dd73f2c16e8",
               "id": "7a755739-1bbb-4211-9130-b6c82d9169a5",
               "status_description": None,
               "name": "lb-vip",
               "admin_state_up": True,
               "subnet_id": "b31cdafe-bdf3-4c19-b768-34d623d77d6c",
               "tenant_id": "f6b09b7a590642d8ac6de73df0ab0686",
               "connection_limit": -1,
               "pool_id": "6350c0fd-07f8-46ff-b797-62acd23760de",
               "session_persistence": None}
        return vip

    def _fake_old_vip_obj(self):
        old_vip = {"status": "ACTIVE",
                   "protocol": "TCP",
                   "description": {"floating_ip": "192.168.100.149",
                                   "provider_interface_mac":
                                   "aa:bb:cc:dd:ee:ff"},
                   "address": "42.0.0.14",
                   "protocol_port": 22,
                   "port_id": "cfd9fcc0-c27b-478b-985e-8dd73f2c16e8",
                   "id": "7a755739-1bbb-4211-9130-b6c82d9169a5",
                   "status_description": None,
                   "name": "lb-vip",
                   "admin_state_up": True,
                   "subnet_id": "b31cdafe-bdf3-4c19-b768-34d623d77d6c",
                   "tenant_id": "f6b09b7a590642d8ac6de73df0ab0686",
                   "connection_limit": -1,
                   "pool_id": "6350c0fd-07f8-46ff-b797-62acd23760de",
                   "session_persistence": None}
        return old_vip

    def _fake_pool_obj(self):
        pool = {"status": "ACTIVE",
                "lb_method": "ROUND_ROBIN",
                "protocol": "TCP",
                "description": "",
                "health_monitors": [],
                "members":
                    [
                        "4910851f-4af7-4592-ad04-08b508c6fa21",
                        "76d2a5fc-b39f-4419-9f33-3b21cf16fe47"
                ],
                "status_description": None,
                "id": "6350c0fd-07f8-46ff-b797-62acd23760de",
                "vip_id": "7a755739-1bbb-4211-9130-b6c82d9169a5",
                "name": "lb-pool",
                    "admin_state_up": True,
                    "subnet_id": "b31cdafe-bdf3-4c19-b768-34d623d77d6c",
                    "tenant_id": "f6b09b7a590642d8ac6de73df0ab0686",
                    "health_monitors_status": [],
                    "provider": "haproxy"}
        return pool

    def _fake_member_obj(self):
        member = {
            "admin_state_up": True,
            "status": "ACTIVE",
            "status_description": None,
            "weight": 1,
            "address": "42.0.0.11",
            "tenant_id": "f6b09b7a590642d8ac6de73df0ab0686",
            "protocol_port": 80,
            "id": "4910851f-4af7-4592-ad04-08b508c6fa21",
            "pool_id": "6350c0fd-07f8-46ff-b797-62acd23760de"}
        return member

    def _fake_hm_obj(self):
        hm = {
            "admin_state_up": True,
            "tenant_id": "f6b09b7a590642d8ac6de73df0ab0686",
            "delay": 10,
            "max_retries": 3,
            "timeout": 10,
            "pools": [],
            "type": "PING",
                    "id": "c30d8a88-c719-4b93-aa64-c58efb397d86"
        }
        return hm

    def _fake_kwargs(self):
        kwargs = {'service_type': 'loadbalancer',
                  'vm_mgmt_ip': '172.24.4.5',
                  'mgmt_ip': '172.24.4.5',
                  'source_cidrs': ['1.2.3.4/24'],
                  'destination_cidr': ['1.2.3.4/24'],
                  'gateway_ip': '1.2.3.4',
                  'provider_interface_position': '1',
                  'request_info': 'some_id',
                  'rule_info': {
                      'active_provider_mac': '00:0a:95:9d:68:16',
                      'provider_mac': '00:0a:95:9d:68:16',
                      'active_stitching_mac': '00:0a:95:9d:68:25',
                      'stitching_mac': '00:0a:95:9d:68:25',
                      'active_fip': '172.24.4.5',
                      'fip': '172.24.4.5',
                      'service_id': '1df1cd7a-d82e-4bbd-8b26-a1f106075a6b',
                      'tenant_id': '6bb921bb81254b3e90e3d8c71a6d72dc'},
                  'context': {'notification_data': 'hello'}
                  }
        return kwargs


class ControllerTestCase(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(ControllerTestCase, self).__init__(*args, **kwargs)
        self.lb = FakeObjects()

    @mock.patch(__name__ + '.FakeObjects.conf')
    @mock.patch(__name__ + '.FakeObjects.sc')
    def _get_ConfiguratorRpcManager_object(self, sc, conf):
        cm = cfgr.ConfiguratorModule(sc)
        demuxer = demuxer_lib.ConfiguratorDemuxer()
        rpc_mgr = cfgr.ConfiguratorRpcManager(sc, cm, conf, demuxer)
        return sc, conf, rpc_mgr

    def _get_GenericConfigRpcManager_object(self, conf, sc):
        agent = gc.GenericConfigRpcManager(sc, conf)
        return agent, sc

    @mock.patch(__name__ + '.FakeObjects.nqueue')
    @mock.patch(__name__ + '.FakeObjects.drivers')
    def _get_GenericConfigEventHandler_object(
            self, sc, rpcmgr, drivers, nqueue):
        agent = gc.GenericConfigEventHandler(sc, drivers, rpcmgr, nqueue)
        return agent

    def _get_LBaasRpcManager_object(self, conf, sc):
        agent = lb.LBaaSRpcManager(sc, conf)
        return agent, sc

    def _test_vip_event_creation(self, operation):
        sc, conf, rpc_mgr = self._get_ConfiguratorRpcManager_object()
        agent, sc = self._get_LBaasRpcManager_object(conf, sc)

        arg_dict = {'context': self.lb.context,
                    'vip': self.lb._fake_vip_obj(),
                    'serialize': True,
                    'binding_key': '6350c0fd-07f8-46ff-b797-62acd23760de'
                    }
        arg_dict_update = {'context': self.lb.context,
                    'vip': self.lb._fake_vip_obj(),
                    'old_vip': self.lb._fake_old_vip_obj(),
                    'serialize': True,
                    'binding_key': '6350c0fd-07f8-46ff-b797-62acd23760de'
                    }
        method = {'CREATE_VIP': 'create_network_device_config',
                  'DELETE_VIP': 'delete_network_device_config',
                  'UPDATE_VIP': 'update_network_device_config'
                  }
        with mock.patch.object(sc, 'new_event', return_value='foo') as (
            mock_sc_new_event), \
            mock.patch.object(sc, 'post_event') as mock_sc_post_event, \
            mock.patch.object(rpc_mgr,
                              '_get_service_agent_instance',
                              return_value=agent):
            if method[operation] == 'create_network_device_config' or method[operation]=='delete_network_device_config':
                request_data = self.lb.fake_request_data_vip()
                args = arg_dict
            elif method[operation] == 'update_network_device_config':
                request_data = self.lb.fake_request_data_vip_update()
                args = arg_dict_update
                
            getattr(rpc_mgr, method[operation])(self.lb.context, request_data)
            mock_sc_new_event.assert_called_with(id=operation, data=args)
            mock_sc_post_event.assert_called_with('foo')
    def test_create_vip_rpc_manager(self):
        self._test_vip_event_creation('CREATE_VIP')

    def test_delete_vip_rpc_manager(self):
        self._test_vip_event_creation('DELETE_VIP')

    def test_update_vip_rpc_manager(self):
        self._test_vip_event_creation('UPDATE_VIP')
        
    def _test_pool_event_creation(self, operation):
        sc, conf, rpc_mgr = self._get_ConfiguratorRpcManager_object()
        agent, sc = self._get_LBaasRpcManager_object(conf, sc)

        arg_dict = {'context': self.lb.context,
                    'pool': self.lb._fake_pool_obj(),
                    'driver_name': 'ha_proxy',
                    'serialize': True,
                    'binding_key': '6350c0fd-07f8-46ff-b797-62acd23760de'
                    }
        arg_dict_update = {'context': self.lb.context,
                    'pool': self.lb._fake_pool_obj(),
                    'serialize': True,
                    'binding_key': '6350c0fd-07f8-46ff-b797-62acd23760de',
                    'old_pool': 'old_pool'
                    }
        arg_dict_delete = {'context': self.lb.context,
                    'pool': self.lb._fake_pool_obj(),
                    'serialize': True,
                    'binding_key': '6350c0fd-07f8-46ff-b797-62acd23760de'
                    }
        method = {'CREATE_POOL': 'create_network_device_config',
                  'DELETE_POOL': 'delete_network_device_config',
                  'UPDATE_POOL': 'update_network_device_config'
                  }
        with mock.patch.object(sc, 'new_event', return_value='foo') as (
            mock_sc_new_event), \
            mock.patch.object(sc, 'post_event') as mock_sc_post_event, \
            mock.patch.object(rpc_mgr,
                              '_get_service_agent_instance',
                              return_value=agent):
            if method[operation] == 'create_network_device_config':
                request_data = self.lb.fake_request_data_create_pool()
                args = arg_dict
            elif method[operation]=='delete_network_device_config':
                request_data = self.lb.fake_request_data_delete_pool()
                args = arg_dict_delete  
            elif method[operation] == 'update_network_device_config':
                request_data = self.lb.fake_request_data_update_pool()
                args = arg_dict_update
                
            getattr(rpc_mgr, method[operation])(self.lb.context, request_data)
            mock_sc_new_event.assert_called_with(id=operation, data=args)
            mock_sc_post_event.assert_called_with('foo')
    
    
    
    def test_create_pool_rpc_manager(self):
        self._test_pool_event_creation('CREATE_POOL')

    def test_delete_pool_rpc_manager(self):
        self._test_pool_event_creation('DELETE_POOL')

    def test_update_pool_rpc_manager(self):
        self._test_pool_event_creation('UPDATE_POOL')
        
        
        
    def _test_member_event_creation(self, operation):
        sc, conf, rpc_mgr = self._get_ConfiguratorRpcManager_object()
        agent, sc = self._get_LBaasRpcManager_object(conf, sc)

        arg_dict = {'context': self.lb.context,
                    'member': self.lb._fake_member_obj(),
                    'serialize': True,
                    'binding_key': '6350c0fd-07f8-46ff-b797-62acd23760de'
                    }
        arg_dict_update = {'context': self.lb.context,
                    'member': self.lb._fake_member_obj(),
                    'old_member': 'old_member',
                    'serialize': True,
                    'binding_key': '6350c0fd-07f8-46ff-b797-62acd23760de'
                    }
        
        method = {'CREATE_MEMBER': 'create_network_device_config',
                  'DELETE_MEMBER': 'delete_network_device_config',
                  'UPDATE_MEMBER': 'update_network_device_config'
                  }
        with mock.patch.object(sc, 'new_event', return_value='foo') as (
            mock_sc_new_event), \
            mock.patch.object(sc, 'post_event') as mock_sc_post_event, \
            mock.patch.object(rpc_mgr,
                              '_get_service_agent_instance',
                              return_value=agent):
            if method[operation] == 'create_network_device_config':
                request_data = self.lb.fake_request_data_create_member()
                args = arg_dict
            elif method[operation]=='delete_network_device_config':
                request_data = self.lb.fake_request_data_create_member()
                args = arg_dict  
            elif method[operation] == 'update_network_device_config':
                request_data = self.lb.fake_request_data_update_member()
                args = arg_dict_update
                
            getattr(rpc_mgr, method[operation])(self.lb.context, request_data)
            mock_sc_new_event.assert_called_with(id=operation, data=args)
            mock_sc_post_event.assert_called_with('foo')
    
    
    
    def test_create_member_rpc_manager(self):
        self._test_member_event_creation('CREATE_MEMBER')

    def test_delete_member_rpc_manager(self):
        self._test_member_event_creation('DELETE_MEMBER')

    def test_update_member_rpc_manager(self):
        self._test_member_event_creation('UPDATE_MEMBER')
        
    def _test_health_monitor_event_creation(self, operation):
        sc, conf, rpc_mgr = self._get_ConfiguratorRpcManager_object()
        agent, sc = self._get_LBaasRpcManager_object(conf, sc)

        arg_dict = {'context': self.lb.context,
                    'health_monitor': self.lb._fake_hm_obj(),
                    'pool_id': 'pool_id',
                    'serialize': True,
                    'binding_key': 'pool_id'
                    }
        arg_dict_update = {'context': self.lb.context,
                    'health_monitor': self.lb._fake_hm_obj(),
                    'old_health_monitor': 'old_health_monitor',
                    'pool_id': 'pool_id',
                    'serialize': True,
                    'binding_key': 'pool_id'
                    }
        
        method = {'CREATE_HEALTH_MONITOR': 'create_network_device_config',
                  'DELETE_HEALTH_MONITOR': 'delete_network_device_config',
                  'UPDATE_HEALTH_MONITOR': 'update_network_device_config'
                  }
        with mock.patch.object(sc, 'new_event', return_value='foo') as (
            mock_sc_new_event), \
            mock.patch.object(sc, 'post_event') as mock_sc_post_event, \
            mock.patch.object(rpc_mgr,
                              '_get_service_agent_instance',
                              return_value=agent):
            if method[operation] == 'create_network_device_config':
                request_data = self.lb.fake_request_data_create_hm()
                args = arg_dict
            elif method[operation]=='delete_network_device_config':
                request_data = self.lb.fake_request_data_create_hm()
                args = arg_dict  
            elif method[operation] == 'update_network_device_config':
                request_data = self.lb.fake_request_data_update_hm()
                args = arg_dict_update
                
            getattr(rpc_mgr, method[operation])(self.lb.context, request_data)
            #mock_sc_new_event.assert_called_with(id=operation, data=args)
            #cmock_sc_post_event.assert_called_with('foo')
    
    
    
    def test_create_health_monitor_rpc_manager(self):
        self._test_health_monitor_event_creation('CREATE_HEALTH_MONITOR')

    def test_delete_health_monitor_rpc_manager(self):
        self._test_health_monitor_event_creation('DELETE_HEALTH_MONITOR')

    def test_update_health_monitor_rpc_manager(self):
        self._test_health_monitor_event_creation('UPDATE_HEALTH_MONITOR')        
        
        
        
    

    
class FakeEvent(object):

    def __init__(self):
        fo = FakeObjects()
        kwargs = fo._fake_kwargs()
        self.data = {
            'context': {'notification_data': {},
                        'resource': 'vip'},
            'vip': fo._fake_vip_obj(),
            'old_vip': fo._fake_old_vip_obj(),
            'pool': fo._fake_pool_obj(),
            'old_pool': 'oldpool',
            'member': fo._fake_member_obj(),
            'old_member': 'oldmember',
            'health_monitor': fo._fake_hm_obj(),
            'old_health_monitor': 'oldhm',
            'pool_id': '6350c0fd-07f8-46ff-b797-62acd23760de',
            'driver_name': 'haproxy',
            'host': fo.host,
            'kwargs': kwargs,
        }
        self.id = 'dummy'


class LBaasHandlerTestCase(unittest.TestCase):
    ''' Generic Config Handler for Firewall module '''

    def __init__(self, *args, **kwargs):
        super(LBaasHandlerTestCase, self).__init__(*args, **kwargs)
        self.fo = FakeObjects()
        self.ev = FakeEvent()

    @mock.patch(__name__ + '.FakeObjects.nqueue')
    @mock.patch(__name__ + '.FakeObjects.rpcmgr')
    @mock.patch(__name__ + '.FakeObjects.drivers')
    @mock.patch(__name__ + '.FakeObjects.sc')
    def _get_LbHandler_objects(self, sc, drivers, rpcmgr, nqueue):
        agent = lb.LBaaSEventHandler(sc, drivers, rpcmgr, nqueue)
        return agent

    def _test_handle_event(self, rule_list_info=True):
        agent = self._get_LbHandler_objects()
        driver = HaproxyOnVmDriver()

        with mock.patch.object(
                agent.plugin_rpc, 'get_logical_device') as (
                mock_get_logical_device), \
                mock.patch.object(
                    agent.plugin_rpc, 'update_status') as (mock_update_status), \
                mock.patch.object(
                    agent.plugin_rpc, 'update_pool_stats') as (mock_update_pool_stats),\
                mock.patch.object(agent, '_get_driver', return_value=driver), \
                mock.patch.object(
                driver, 'create_vip') as mock_create_vip,\
                mock.patch.object(
                driver, 'delete_vip') as mock_delete_vip,\
                mock.patch.object(
                driver, 'update_vip') as mock_update_vip,\
                mock.patch.object(
                driver, 'create_pool') as mock_create_pool,\
                mock.patch.object(
                driver, 'delete_pool') as mock_delete_pool,\
                mock.patch.object(
                driver, 'update_pool') as mock_update_pool,\
                mock.patch.object(
                driver, 'create_member') as mock_create_member,\
                mock.patch.object(
                driver, 'delete_member') as mock_delete_member,\
                mock.patch.object(
                driver, 'update_member') as mock_update_member,\
                mock.patch.object(
                driver, 'create_pool_health_monitor') as mock_create_poolhm,\
                mock.patch.object(
                driver, 'delete_pool_health_monitor') as mock_delete_poolhm,\
                mock.patch.object(
                driver, 'update_pool_health_monitor') as mock_update_poolhm, \
                mock.patch.object(
                agent, 'drivers', return_value='haproxy') as test:

            vip = self.fo._fake_vip_obj()
            old_vip = self.fo._fake_old_vip_obj()
            pool = self.fo._fake_pool_obj()
            old_pool = 'old_pool'
            member = self.fo._fake_member_obj()
            old_member = 'oldmember'
            hm = self.fo._fake_hm_obj()
            old_hm = 'oldhm'
            pool_id = '6350c0fd-07f8-46ff-b797-62acd23760de'
            #import pdb;pdb.set_trace()
            agent.handle_event(self.ev)
            if self.ev.id == 'CREATE_VIP':
                mock_create_vip.assert_called_with(vip, self.fo.vip_context)
            elif self.ev.id == 'DELETE_VIP':
                mock_delete_vip.assert_called_with(vip, self.fo.context)
            elif self.ev.id == 'UPDATE_VIP':
                mock_update_vip.assert_called_with(
                    old_vip, vip, self.fo.context)
            elif self.ev.id == 'CREATE_POOL':
                mock_create_pool.assert_called_with(pool, self.fo.context)
            elif self.ev.id == 'DELETE_POOL':
                mock_delete_pool.assert_called_with(pool, self.fo.context)
            elif self.ev.id == 'UPDATE_POOL':
                mock_update_pool.assert_called_with(
                    old_pool, pool, self.fo.context)
            elif self.ev.id == 'CREATE_MEMBER':
                mock_create_member.assert_called_with(member, self.fo.context)
            elif self.ev.id == 'DELETE_MEMBER':
                mock_delete_member.assert_called_with(member, self.fo.context)
            elif self.ev.id == 'UPDATE_MEMBER':
                mock_update_member.assert_called_with(
                    old_member, member, self.fo.context)
            elif self.ev.id == 'CREATE_POOL_HEALTH_MONITOR':
                mock_create_poolhm.assert_called_with(
                    hm, pool_id, self.fo.context)
            elif self.ev.id == 'DELETE_POOL_HEALTH_MONITOR':
                mock_delete_poolhm.assert_called_with(
                    hm, pool_id, self.fo.context)
            elif self.ev.id == 'UPDATE_POOL_HEALTH_MONITOR':
                mock_update_poolhm.assert_called_with(
                    old_hm, hm, pool_id, self.fo.context)

    def test_create_vip_event_handler(self):
        self.ev.id = 'CREATE_VIP'
        self._test_handle_event()

    def test_delete_vip_event_handler(self):
        self.ev.id = 'DELETE_VIP'
        self._test_handle_event()

    def test_update_vip_event_handler(self):
        self.ev.id = 'UPDATE_VIP'
        self._test_handle_event()

    def test_create_pool_event_handler(self):
        self.ev.id = 'CREATE_POOL'
        # self._test_handle_event()

    def test_delete_pool_event_handler(self):
        self.ev.id = 'DELETE_POOL'
        # self._test_handle_event()

    def test_update_pool_event_handler(self):
        self.ev.id = 'UPDATE_POOL'
        # self._test_handle_event()

    def test_create_member_event_handler(self):
        self.ev.id = 'CREATE_MEMBER'
        self._test_handle_event()

    def test_delete_member_event_handler(self):
        self.ev.id = 'DELETE_MEMBER'
        self._test_handle_event()

    def test_update_member_event_handler(self):
        self.ev.id = 'UPDATE_MEMBER'
        self._test_handle_event()

    def test_create_pool_hm_event_handler(self):
        self.ev.id = 'CREATE_POOL_HEALTH_MONITOR'
        self._test_handle_event()

    def test_delete_pool_hm_event_handler(self):
        self.ev.id = 'DELETE_POOL_HEALTH_MONITOR'
        self._test_handle_event()

    def test_update_pool_hm_event_handler(self):
        self.ev.id = 'UPDATE_POOL_HEALTH_MONITOR'
        self._test_handle_event()


if __name__ == '__main__':
    unittest.main()

