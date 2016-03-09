import requests
import unittest
import mock
import json

from oslo_config import cfg
from oslo_log import log as logging
import oslo_messaging

from neutron.common import rpc as n_rpc

from gbpservice.nfp.modules import configurator as cfgr
import loadbalancer_v1 as lb
from gbpservice.nfp.configurator.agents import generic_config as gc
from gbpservice.nfp.configurator.drivers.loadbalancer.v1.haproxy.haproxy_lb_driver import HaproxyOnVmDriver
#from gbpservice.neutron.nsf.configurator.agents.vyos_fw_driver import FwGenericConfigDriver
from gbpservice.nfp.configurator.lib import demuxer as demuxer_lib
from gbpservice.nfp.configurator.drivers.loadbalancer.v1.haproxy \
    import(haproxy_rest_client)


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
    url = 'http://172.24.4.5:8888'

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
                    "pool": self._fake_pool_obj(),
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

    def _fake_old_pool_obj(self):

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
                "provider": "haproxy"
                }
        return pool

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

    def _fake_member_obj(self):
        member = [{
            "admin_state_up": True,
            "status": "ACTIVE",
            "status_description": None,
            "weight": 1,
            "address": "42.0.0.11",
            "tenant_id": "f6b09b7a590642d8ac6de73df0ab0686",
            "protocol_port": 80,
            "id": "4910851f-4af7-4592-ad04-08b508c6fa21",
            "pool_id": "6350c0fd-07f8-46ff-b797-62acd23760de"}]
        return member

    def _fake_old_member_obj(self):
        member = [{
            "admin_state_up": True,
            "status": "ACTIVE",
            "status_description": None,
            "weight": 1,
            "address": "42.0.0.11",
            "tenant_id": "f6b09b7a590642d8ac6de73df0ab0686",
            "protocol_port": 80,
            "id": "4910851f-4af7-4592-ad04-08b508c6fa21",
            "pool_id": "6350c0fd-07f8-46ff-b797-62acd23760de"}]
        return member

    def _fake_hm_obj(self):
        hm = [{
            "admin_state_up": True,
            "tenant_id": "f6b09b7a590642d8ac6de73df0ab0686",
            "delay": 10,
            "max_retries": 3,
            "timeout": 10,
            "pools": [],
            "type": "PING",
                    "id": "c30d8a88-c719-4b93-aa64-c58efb397d86"
        }]
        return hm

    def _fake_old_hm_obj(self):
        hm = [{
            "admin_state_up": True,
            "tenant_id": "f6b09b7a590642d8ac6de73df0ab0686",
            "delay": 10,
            "max_retries": 3,
            "timeout": 10,
            "pools": [],
            "type": "PING",
                    "id": "c30d8a88-c719-4b93-aa64-c58efb397d86"
        }]
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


class FakeEvent(object):

    def __init__(self):
        fo = FakeObjects()
        kwargs = fo._fake_kwargs()
        self.data = {
            'context': {'notification_data': {},
                        'resource': 'context_resource'},
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


class LbaasDriverTestCase(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(LbaasDriverTestCase, self).__init__(*args, **kwargs)
        self.fo = FakeObjects()
        self.driver = HaproxyOnVmDriver()
        self.resp = mock.Mock()
        self.fake_resp_dict = {'status': True,
                               'config_success': True,
                               'delete_success': True}
        self.fo.vip = self.fo._fake_vip_obj()
        self.fo.old_vip = self.fo._fake_vip_obj()
        self.fo.pool = self.fo._fake_pool_obj()
        self.fo.old_pool = self.fo._fake_old_pool_obj()
        self.fo.hm = self.fo._fake_hm_obj()
        self.fo.old_hm = self.fo._fake_old_hm_obj()
        self.fo.member = self.fo._fake_member_obj()
        self.fo.old_member = self.fo._fake_old_member_obj()
        self.vip = json.dumps(self.fo.vip)
        self.pool_id = '6350c0fd-07f8-46ff-b797-62acd23760de'
        self.resp = mock.Mock()
        self.resp.status_code = 200
        self.resp_create = {'service': 'asc'}
        self.get_resource = {
            'server': {
                'resource': [],
                'srvr:4910851f-4af7-4592-ad04-08b508c6fa21': []},
            'timeout': {}}

    @mock.patch(__name__ + '.FakeObjects.nqueue')
    @mock.patch(__name__ + '.FakeObjects.rpcmgr')
    @mock.patch(__name__ + '.FakeObjects.drivers')
    @mock.patch(__name__ + '.FakeObjects.sc')
    def _get_LbHandler_objects(self, sc, drivers, rpcmgr, nqueue):
        agent = lb.LBaaSEventHandler(sc, drivers, rpcmgr, nqueue)
        return agent

    def _test_lbaasdriver(self, method_name):
        agent = self._get_LbHandler_objects()
        driver = HaproxyOnVmDriver(agent.plugin_rpc)
        rest_client = haproxy_rest_client.HttpRequests(
            '192.168.100.149', '1234')
        logical_device_return_value = {
            'vip': self.fo.vip,
            'old_vip': self.fo.old_vip,
            'pool': self.fo.pool,
            'healthmonitors': self.fo.hm,
            'members': self.fo.member}
        with mock.patch.object(
                agent.plugin_rpc, 'get_logical_device', return_value=logical_device_return_value) as (
                mock_get_logical_device),\
                mock.patch.object(
                driver, '_get_rest_client', return_value=rest_client) as (mock_rest_client),\
                mock.patch.object(
            rest_client.pool, 'request', return_value=self.resp) as (mock_request),\
                mock.patch.object(
                rest_client, 'get_resource', return_value=self.get_resource) as (mock_get_resource):

            mock_request.status_code = 200
            if method_name == 'DELETE_VIP':
                driver.delete_vip(self.fo.vip, self.fo.context)
                mock_request.assert_called_with(
                    'DELETE',
                    data=None,
                    headers={
                        'Content-Type': 'application/json'},
                    timeout=30,
                    url='http://192.168.100.149:1234/backend/bck:6350c0fd-07f8-46ff-b797-62acd23760de')
            elif method_name == 'CREATE_VIP':
                driver.create_vip(self.fo.vip, self.fo.context)
                mock_request.assert_called_with(
                    'POST',
                    data='{"frnt:7a755739-1bbb-4211-9130-b6c82d9169a5": {"provider_interface_mac": "aa:bb:cc:dd:ee:ff", "bind": "42.0.0.14:22", "default_backend": "bck:6350c0fd-07f8-46ff-b797-62acd23760de", "option": {"tcplog": true}, "mode": "tcp"}}',
                    headers={
                        'Content-Type': 'application/json'},
                    timeout=30,
                    url='http://192.168.100.149:1234/frontend')
                mock_get_resource.assert_called_with(
                    'backend/bck:6350c0fd-07f8-46ff-b797-62acd23760de')
            elif method_name == 'UPDATE_VIP':
                driver.update_vip(
                    self.fo.old_vip,
                    self.fo.vip,
                    self.fo.context)
                mock_request.assert_called_with(
                    'PUT',
                    data='{"provider_interface_mac": "aa:bb:cc:dd:ee:ff", "bind": "42.0.0.14:22", "default_backend": "bck:6350c0fd-07f8-46ff-b797-62acd23760de", "option": {"tcplog": true}, "mode": "tcp"}',
                    headers={
                        'Content-Type': 'application/json'},
                    timeout=30,
                    url='http://192.168.100.149:1234/frontend/frnt:7a755739-1bbb-4211-9130-b6c82d9169a5')
            elif method_name == 'CREATE_POOL':
                driver.create_pool(self.fo.pool, self.fo.context)
            elif method_name == 'DELETE_POOL':
                driver.delete_pool(self.fo.pool, self.fo.context)
            elif method_name == 'UPDATE_POOL':
                driver.update_pool(
                    self.fo.old_pool,
                    self.fo.pool,
                    self.fo.context)
                mock_request.assert_called_with(
                    'PUT',
                    data='{"server": {"srvr:4910851f-4af7-4592-ad04-08b508c6fa21": ["42.0.0.11:80", "weight 1", "check inter 10s fall 3"]}, "balance": "roundrobin", "mode": "tcp", "timeout": {"check": "10s"}, "option": {}}',
                    headers={
                        'Content-Type': 'application/json'},
                    timeout=30,
                    url='http://192.168.100.149:1234/backend/bck:6350c0fd-07f8-46ff-b797-62acd23760de')
            elif method_name == 'CREATE_MEMBER':
                driver.create_member(self.fo.member[0], self.fo.context)
                mock_request.assert_called_with(
                    'PUT',
                    data='{"timeout": {}, "server": {"srvr:4910851f-4af7-4592-ad04-08b508c6fa21": ["42.0.0.11:80", "weight 1", "check inter 10s fall 3"], "resource": []}}',
                    headers={
                        'Content-Type': 'application/json'},
                    timeout=30,
                    url='http://192.168.100.149:1234/backend/bck:6350c0fd-07f8-46ff-b797-62acd23760de')
            elif method_name == 'DELETE_MEMBER':
                driver.delete_member(self.fo.member[0], self.fo.context)
                mock_request.assert_called_with(
                    'PUT',
                    data='{"timeout": {}, "server": {"resource": []}}',
                    headers={
                        'Content-Type': 'application/json'},
                    timeout=30,
                    url='http://192.168.100.149:1234/backend/bck:6350c0fd-07f8-46ff-b797-62acd23760de')
            elif method_name == 'UPDATE_MEMBER':
                driver.update_member(
                    self.fo.old_member[0],
                    self.fo.member[0],
                    self.fo.context)
                mock_request.assert_called_with(
                    'PUT',
                    data='{"timeout": {}, "server": {"srvr:4910851f-4af7-4592-ad04-08b508c6fa21": ["42.0.0.11:80", "weight 1", "check inter 10s fall 3"], "resource": []}}',
                    headers={
                        'Content-Type': 'application/json'},
                    timeout=30,
                    url='http://192.168.100.149:1234/backend/bck:6350c0fd-07f8-46ff-b797-62acd23760de')
            elif method_name == 'CREATE_POOL_HEALTH_MONITOR':
                driver.create_pool_health_monitor(
                    self.fo.hm[0], self.pool_id, self.fo.context)
                mock_request.assert_called_with(
                    'PUT',
                    data='{"timeout": {"check": "10s"}, "server": {"srvr:4910851f-4af7-4592-ad04-08b508c6fa21": [], "resource": []}}',
                    headers={
                        'Content-Type': 'application/json'},
                    timeout=30,
                    url='http://192.168.100.149:1234/backend/bck:6350c0fd-07f8-46ff-b797-62acd23760de')
            elif method_name == 'DELETE_POOL_HEALTH_MONITOR':
                driver.delete_pool_health_monitor(
                    self.fo.hm[0], self.pool_id, self.fo.context)
                mock_request.assert_called_with(
                    'PUT',
                    data='{"timeout": {}, "server": {"srvr:4910851f-4af7-4592-ad04-08b508c6fa21": [], "resource": []}}',
                    headers={
                        'Content-Type': 'application/json'},
                    timeout=30,
                    url='http://192.168.100.149:1234/backend/bck:6350c0fd-07f8-46ff-b797-62acd23760de')
            elif method_name == 'UPDATE_POOL_HEALTH_MONITOR':
                driver.update_pool_health_monitor(
                    self.fo.old_hm[0], self.fo.hm[0], self.pool_id, self.fo.context)
                mock_request.assert_called_with(
                    'PUT',
                    data='{"timeout": {"check": "10s"}, "server": {"srvr:4910851f-4af7-4592-ad04-08b508c6fa21": [], "resource": []}}',
                    headers={
                        'Content-Type': 'application/json'},
                    timeout=30,
                    url='http://192.168.100.149:1234/backend/bck:6350c0fd-07f8-46ff-b797-62acd23760de')

    def test_vip_create_lbaasdriver(self):
        self._test_lbaasdriver('CREATE_VIP')
        pass

    def test_vip_delete_lbaasdriver(self):
        self._test_lbaasdriver('DELETE_VIP')
        pass

    def test_vip_update_lbaasdriver(self):
        self._test_lbaasdriver('UPDATE_VIP')
        pass

    def test_pool_create_lbaasdriver(self):
        self._test_lbaasdriver('CREATE_POOL')
        pass

    def test_pool_delete_lbaasdriver(self):
        self._test_lbaasdriver('DELETE_POOL')
        pass

    def test_pool_update_lbaasdriver(self):
        self._test_lbaasdriver('UPDATE_POOL')
        pass

    def test_member_create_lbaasdriver(self):
        self._test_lbaasdriver('CREATE_MEMBER')
        pass

    def test_member_delete_lbaasdriver(self):
        self._test_lbaasdriver('DELETE_MEMBER')
        pass

    def test_member_update_lbaasdriver(self):
        self._test_lbaasdriver('UPDATE_MEMBER')
        pass

    def test_pool_health_monitor_create_lbaasdriver(self):
        self._test_lbaasdriver('CREATE_POOL_HEALTH_MONITOR')
        pass

    def test_pool_health_monitor_delete_lbaasdriver(self):
        self._test_lbaasdriver('DELETE_POOL_HEALTH_MONITOR')
        pass

    def test_pool_health_monitor_update_lbaasdriver(self):
        self._test_lbaasdriver('UPDATE_POOL_HEALTH_MONITOR')
        # pass


if __name__ == '__main__':
    unittest.main()

