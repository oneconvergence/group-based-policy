import unittest
import mock

from oslo_log import log as logging


from gbpservice.nfp.modules import configurator
from gbpservice.nfp.configurator.agents import loadbalancer_v1 as lb
from gbpservice.nfp.configurator.drivers.loadbalancer.v1.haproxy.haproxy_lb_driver import HaproxyOnVmDriver
from gbpservice.nfp.configurator.lib import demuxer

from test_input_data import FakeObjects
from test_input_data import FakeEvent


LOG = logging.getLogger(__name__)


class LBaasRpcSenderTest(unittest.TestCase):

    @mock.patch(__name__ + '.FakeObjects.conf')
    @mock.patch(__name__ + '.FakeObjects.sc')
    def _get_configurator_rpc_manager_object(self, sc, conf):
        cm = configurator.ConfiguratorModule(sc)
        dmx = demuxer.ConfiguratorDemuxer()
        rpc_mgr = configurator.ConfiguratorRpcManager(sc, cm, conf, dmx)
        return sc, conf, rpc_mgr

    def test_notifications(self):
        sc, conf, rpc_mgr = self._get_configurator_rpc_manager_object()
        agent = lb.LBaasRpcSender(sc)

        data = "NOTIFICATION_DATA"
        with mock.patch.object(sc, 'new_event', return_value='foo') as (
                mock_new_event), \
                mock.patch.object(sc, 'poll_event') as (mock_poll_event):

            agent._notification(data)

            mock_new_event.assert_called_with(id='NOTIFICATION_EVENT',
                                              key='NOTIFICATION_EVENT',
                                              data=data)
            mock_poll_event.assert_called_with('foo')


class LBaaSRpcManagerTest(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(LBaaSRpcManagerTest, self).__init__(*args, **kwargs)
        self.fo = FakeObjects()
        self.arg_dict_vip = {
            'context': self.fo.context,
            'vip': self.fo._fake_vip_obj(),
            'serialize': True,
            'binding_key': '6350c0fd-07f8-46ff-b797-62acd23760de'}
        self.arg_dict_vip_update = {
            'context': self.fo.context,
            'vip': self.fo._fake_vip_obj(),
            'old_vip': self.fo._fake_vip_obj(),
            'serialize': True,
            'binding_key': '6350c0fd-07f8-46ff-b797-62acd23760de'}
        self.arg_dict_pool = {
            'context': self.fo.context,
            'pool': self.fo._fake_pool_obj(),
            'driver_name': 'loadbalancer',
            'serialize': True,
            'binding_key': '6350c0fd-07f8-46ff-b797-62acd23760de'}
        self.arg_dict_pool_update = {
            'context': self.fo.context,
            'pool': self.fo._fake_pool_obj(),
            'serialize': True,
            'binding_key': '6350c0fd-07f8-46ff-b797-62acd23760de',
            'old_pool': self.fo._fake_pool_obj()}
        self.arg_dict_pool_delete = {
            'context': self.fo.context,
            'pool': self.fo._fake_pool_obj(),
            'serialize': True,
            'binding_key': '6350c0fd-07f8-46ff-b797-62acd23760de'}
        self.arg_dict_member = {
            'context': self.fo.context,
            'member': self.fo._fake_member_obj()[0],
            'serialize': True,
            'binding_key': '6350c0fd-07f8-46ff-b797-62acd23760de'}
        self.arg_dict_member_update = {
            'context': self.fo.context,
            'member': self.fo._fake_member_obj()[0],
            'old_member': self.fo._fake_member_obj()[0],
            'serialize': True,
            'binding_key': '6350c0fd-07f8-46ff-b797-62acd23760de'}
        self.arg_dict_health_monitor = {
            'context': self.fo.context,
            'health_monitor': self.fo._fake_hm_obj()[0],
            'pool_id': self.fo._fake_pool_obj()['id'],
            'serialize': True,
            'binding_key': '6350c0fd-07f8-46ff-b797-62acd23760de'}
        self.arg_dict_health_monitor_update = {
            'context': self.fo.context,
            'health_monitor': self.fo._fake_hm_obj()[0],
            'old_health_monitor': self.fo._fake_hm_obj()[0],
            'pool_id': self.fo._fake_pool_obj()['id'],
            'serialize': True,
            'binding_key': '6350c0fd-07f8-46ff-b797-62acd23760de'}

    @mock.patch(__name__ + '.FakeObjects.conf')
    @mock.patch(__name__ + '.FakeObjects.sc')
    def _get_configurator_rpc_manager_object(self, sc, conf):
        cm = configurator.ConfiguratorModule(sc)
        dmx = demuxer.ConfiguratorDemuxer()
        rpc_mgr = configurator.ConfiguratorRpcManager(sc, cm, conf, dmx)
        return sc, conf, rpc_mgr

    def _get_lbaas_rpc_manager_object(self, conf, sc):
        agent = lb.LBaaSRpcManager(sc, conf)
        return agent, sc

    def _test_controller(self, operation):
        sc, conf, rpc_mgr = self._get_configurator_rpc_manager_object()
        agent, sc = self._get_lbaas_rpc_manager_object(conf, sc)

        method = self.fo.method

        with mock.patch.object(sc, 'new_event', return_value='foo') as (
            mock_sc_new_event), \
            mock.patch.object(sc, 'post_event') as mock_sc_post_event, \
            mock.patch.object(rpc_mgr,
                              '_get_service_agent_instance',
                              return_value=agent):
            if operation == 'CREATE_VIP' or operation == 'DELETE_VIP':
                request_data = self.fo.fake_request_data_vip()
                args = self.arg_dict_vip
            elif operation == 'UPDATE_VIP':
                request_data = self.fo.fake_request_data_vip_update()
                args = self.arg_dict_vip_update
            elif operation == 'CREATE_POOL':
                request_data = self.fo.fake_request_data_create_pool()
                args = self.arg_dict_pool
            elif operation == 'DELETE_POOL':
                request_data = self.fo.fake_request_data_delete_pool()
                args = self.arg_dict_pool_delete
            elif operation == 'UPDATE_POOL':
                request_data = self.fo.fake_request_data_update_pool()
                args = self.arg_dict_pool_update
            elif operation == 'CREATE_MEMBER' or operation == 'DELETE_MEMBER':
                request_data = self.fo.fake_request_data_create_member()
                args = self.arg_dict_member
            elif operation == 'UPDATE_MEMBER':
                request_data = self.fo.fake_request_data_update_member()
                args = self.arg_dict_member_update
            elif operation == 'CREATE_HEALTH_MONITOR' or operation == 'DELETE_HEALTH_MONITOR':
                request_data = self.fo.fake_request_data_create_pool_hm()
                args = self.arg_dict_health_monitor
            elif operation == 'UPDATE_HEALTH_MONITOR':
                request_data = self.fo.fake_request_data_update_pool_hm()
                args = self.arg_dict_health_monitor_update
            #import pdb;pdb.set_trace()
            getattr(rpc_mgr, method[operation])(self.fo.context, request_data)
            mock_sc_new_event.assert_called_with(id=operation, data=args)
            mock_sc_post_event.assert_called_with('foo')

    def test_create_vip_rpc_manager(self):
        self._test_controller('CREATE_VIP')

    def test_delete_vip_rpc_manager(self):
        self._test_controller('DELETE_VIP')

    def test_update_vip_rpc_manager(self):
        self._test_controller('UPDATE_VIP')

    def test_create_pool_rpc_manager(self):
        self._test_controller('CREATE_POOL')

    def test_delete_pool_rpc_manager(self):
        self._test_controller('DELETE_POOL')

    def test_update_pool_rpc_manager(self):
        self._test_controller('UPDATE_POOL')

    def test_create_member_rpc_manager(self):
        self._test_controller('CREATE_MEMBER')

    def test_delete_member_rpc_manager(self):
        self._test_controller('DELETE_MEMBER')

    def test_update_member_rpc_manager(self):
        self._test_controller('UPDATE_MEMBER')

    def test_create_health_monitor_rpc_manager(self):
        self._test_controller('CREATE_HEALTH_MONITOR')
        pass

    def test_delete_health_monitor_rpc_manager(self):
        self._test_controller('DELETE_HEALTH_MONITOR')
        pass

    def test_update_health_monitor_rpc_manager(self):
        self._test_controller('UPDATE_HEALTH_MONITOR')
        pass


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
    def _get_lb_handler_objects(self, sc, drivers, rpcmgr, nqueue):
        agent = lb.LBaaSEventHandler(sc, drivers, rpcmgr, nqueue)
        return agent

    def _test_handle_event(self, rule_list_info=True):
        agent = self._get_lb_handler_objects()
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
            old_vip = self.fo._fake_vip_obj()
            pool = self.fo._fake_pool_obj()
            old_pool = self.fo._fake_pool_obj()
            member = self.fo._fake_member_obj()[0]
            old_member = self.fo._fake_member_obj()[0]
            hm = self.fo._fake_hm_obj()[0]
            old_hm = self.fo._fake_hm_obj()[0]
            pool_id = '6350c0fd-07f8-46ff-b797-62acd23760de'
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
