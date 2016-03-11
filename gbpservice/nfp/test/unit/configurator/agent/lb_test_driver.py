import unittest
import mock
import json

from oslo_log import log as logging


import loadbalancer_v1 as lb
from gbpservice.nfp.configurator.drivers.loadbalancer.v1.haproxy.haproxy_lb_driver import HaproxyOnVmDriver
from gbpservice.nfp.configurator.drivers.loadbalancer.v1.haproxy import haproxy_rest_client
from test_input_data import FakeObjects

LOG = logging.getLogger(__name__)


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
        self.fo.old_pool = self.fo._fake_pool_obj()
        self.fo.hm = self.fo._fake_hm_obj()
        self.fo.old_hm = self.fo._fake_hm_obj()
        self.fo.member = self.fo._fake_member_obj()
        self.fo.old_member = self.fo._fake_member_obj()
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
    def _get_lb_handler_objects(self, sc, drivers, rpcmgr, nqueue):
        agent = lb.LBaaSEventHandler(sc, drivers, rpcmgr, nqueue)
        return agent

    def _test_lbaasdriver(self, method_name):
        agent = self._get_lb_handler_objects()
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
        pass


if __name__ == '__main__':
    unittest.main()
