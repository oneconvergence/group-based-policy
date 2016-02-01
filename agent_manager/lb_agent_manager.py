from oslo.config import cfg

from neutron.agent import rpc as agent_rpc
from neutron.common import constants as n_const
from neutron.common import exceptions as n_exc
from neutron.common import rpc as n_rpc
from neutron.common import topics
from neutron import context
from neutron.openstack.common import importutils
from neutron.openstack.common import log as logging
from neutron.openstack.common import loopingcall
from neutron.openstack.common import periodic_task
from neutron.plugins.common import constants
from sc.services.lb.agent.oc_lb_agent_sm_rpc import LbAgent_SM_Callbacks

from sc.services.lb.agent import agent_api
from sc.services.lb.agent import constants as lb_agent_const
from neutron_lbaas.db.loadbalancer import loadbalancer_db
from neutron_lbaas.services.loadbalancer import agent_scheduler as agent_sc
from neutron.services.loadbalancer.drivers.common import (
    agent_driver_base as adb
)


LOG = logging.getLogger(__name__)

OPTS = [
    cfg.MultiStrOpt(
        'device_driver',
        default=['neutron.services.loadbalancer.drivers'
                 '.haproxy.namespace_driver.HaproxyNSDriver'],
        help=_('Drivers used to manage loadbalancing devices'),
    ),
]

class DeviceNotFoundOnAgent(n_exc.NotFound):
    msg = _('Unknown device with pool_id %(pool_id)s')

class TenantNotFound(exceptions.NeutronException):
    message = _("Cannot Get context as tenant_id is not available")

REQUEST_METHOD = 'http' #can be http,https
SERVER_IP_ADDR = '192.168.2.68'

class LbaasAgentManager(n_rpc.RpcCallback, periodic_task.PeriodicTasks,
                        loadbalancer_db.LoadBalancerPluginDb,
                        agent_sc.LbaasAgentSchedulerDbMixin):

    RPC_API_VERSION = '2.0'
    # history
    #   1.0 Initial version
    #   1.1 Support agent_updated call
    #   2.0 Generic API for agent based drivers
    #       - modify/reload/destroy_pool methods were removed;
    #       - added methods to handle create/update/delete for every lbaas
    #       object individually;

    def __init__(self, conf):
        super(LbaasAgentManager, self).__init__()
        self.conf = conf
        self.context = context.get_admin_context_without_session()
        self._load_drivers()

        self.agent_state = {
            'binary': 'oc-lb-agent',
            'host': conf.host,
            'topic': lb_agent_const.OC_LOADBALANCER_AGENT_TOPIC,
            'configurations': {'device_drivers': self.device_drivers.keys()},
            'agent_type': n_const.AGENT_TYPE_LOADBALANCER,
            'start_flag': True}
        self.admin_state_up = True

        self._setup_state_rpc()
        self.needs_resync = False
        self.pending_resources_sync_done = False
        self.endpoints = [LbAgent_SM_Callbacks(self)]
        self.conn = n_rpc.create_connection(new=True)
        self.conn.create_consumer(
            lb_agent_const.SM_RPC_TOPIC, self.endpoints, fanout=False)
        self.conn.consume_in_threads()
        self._core_plgin = None

    @property
    def core_plugin(self):
        if not self._core_plugin:
            self._core_plugin = manager.NeutronManager.get_plugin()
        return self._core_plugin

    def _load_drivers(self):
        self.device_drivers = {}
        for driver in self.conf.device_driver:
            try:
                driver_inst = importutils.import_object(
                    driver,
                    self.conf,
                )
            except ImportError:
                msg = _('Error importing loadbalancer device driver: %s')
                raise SystemExit(msg % driver)

            driver_name = driver_inst.get_name()
            if driver_name not in self.device_drivers:
                self.device_drivers[driver_name] = driver_inst
            else:
                msg = _('Multiple device drivers with the same name found: %s')
                raise SystemExit(msg % driver_name)

    def _setup_state_rpc(self):
        self.state_rpc = agent_rpc.PluginReportStateAPI(
            topics.LOADBALANCER_PLUGIN)
        report_interval = self.conf.AGENT.report_interval
        if report_interval:
            heartbeat = loopingcall.FixedIntervalLoopingCall(
                self._report_state)
            heartbeat.start(interval=report_interval)

    def _report_state(self):
        try:
            instance_count = len(self.instance_mapping)
            self.agent_state['configurations']['instances'] = instance_count
            self.state_rpc.report_state(self.context,
                                        self.agent_state)
            self.agent_state.pop('start_flag', None)
        except Exception:
            LOG.exception(_("Failed reporting state!"))

    def create_vip(self, context, vip):
        tenant_id = vip['tenant_id']
        data_context = self._get_all_context_for_given_tenant(context, tenant_id)
        context['service_info'] = data_context
        kwargs = {'vip':vip}
        body = {'kwargs': **kwargs,
                'context': context}
        rest_client.send_request(REQUEST_METHOD,
                                 SERVER_IP_ADDR,
                                 'lb/create_vip',
                                 'POST',
                                 headers = 'application/json',
                                 body = body)


    def update_vip(self, context, old_vip, vip):
        tenant_id = old_vip['tenant_id']
        data_context = self._get_all_context_for_given_tenant(context, tenant_id)
        context['service_info'] = data_context
        kwargs = {'old_vip':old_vip, 'vip':vip}
        body = {'kwargs': **kwargs,
                'context': context}
        rest_client.send_request(REQUEST_METHOD,
                                 SERVER_IP_ADDR,
                                 'lb/update_vip',
                                 'PUT',
                                 headers = 'application/json',
                                 body = body)

    def delete_vip(self, context, vip):
        tenant_id = vip['tenant_id']
        data_context = self._get_all_context_for_given_tenant(context, tenant_id)
        context['service_info'] = data_context
        kwargs = {'vip':vip}
        body = {'kwargs': **kwargs,
                'context': context}
        rest_client.send_request(REQUEST_METHOD,
                                 SERVER_IP_ADDR,
                                 'lb/delete_vip',
                                 'DELETE',
                                 headers = 'application/json',
                                 body = body)

    def create_pool(self, context, pool, driver_name):
        tenant_id = pool['tenant_id']
        data_context = self._get_all_context_for_given_tenant(context, tenant_id)
        context['service_info'] = data_context
        kwargs = {'pool':pool, 'driver_name'}
        body = {'kwargs': **kwargs,
                'context': context}
        rest_client.send_request(REQUEST_METHOD,
                                 SERVER_IP_ADDR,
                                 'lb/create_pool',
                                 'POST',
                                 headers = 'application/json',
                                 body = body)

    def update_pool(self, context, old_pool, pool):
        tenant_id = old_pool['tenant_id']
        data_context = self._get_all_context_for_given_tenant(context, tenant_id)
        context['service_info'] = data_context
        kwargs = {'old_pool':old_pool, 'pool':pool}
        body = {'kwargs': **kwargs,
                'context': context}
        rest_client.send_request(REQUEST_METHOD,
                                 SERVER_IP_ADDR,
                                 'lb/update_pool',
                                 'PUT',
                                 headers = 'application/json',
                                 body = body)

    def delete_pool(self, context, pool):
        tenant_id = pool['tenant_id']
        data_context = self._get_all_context_for_given_tenant(context, tenant_id)
        context['service_info'] = data_context
        kwargs = {'pool':pool}
        body = {'kwargs': **kwargs,
                'context': context}
        rest_client.send_request(REQUEST_METHOD,
                                 SERVER_IP_ADDR,
                                 'lb/delete_pool',
                                 'DELETE',
                                 headers = 'application/json',
                                 body = body)

    def create_member(self, context, member):
        tenant_id = member['tenant_id']
        data_context = self._get_all_context_for_given_tenant(context, tenant_id)
        context['service_info'] = data_context
        kwargs = {'member':member}
        body = {'kwargs': **kwargs,
                'context': context}
        rest_client.send_request(REQUEST_METHOD,
                                 SERVER_IP_ADDR,
                                 'lb/create_member',
                                 'POST',
                                 headers = 'application/json',
                                 body = body)

    def update_member(self, context, old_member, member):
        tenant_id = member['tenant_id']
        data_context = self._get_all_context_for_given_tenant(context, tenant_id)
        context['service_info'] = data_context
        kwargs = {'old_member':old_member,'member':member}
        body = {'kwargs': **kwargs,
                'context': context}
        rest_client.send_request(REQUEST_METHOD,
                                 SERVER_IP_ADDR,
                                 'lb/update_member',
                                 'PUT',
                                 headers = 'application/json',
                                 body = body)

    def delete_member(self, context, member):
        tenant_id = member['tenant_id']
        data_context = self._get_all_context_for_given_tenant(context, tenant_id)
        context['service_info'] = data_context
        kwargs = {'member':member}
        body = {'kwargs': **kwargs,
                'context': context}
        rest_client.send_request(REQUEST_METHOD,
                                 SERVER_IP_ADDR,
                                 'lb/delete_member',
                                 'DELETE',
                                 headers = 'application/json',
                                 body = body)

    def create_pool_health_monitor(self, context, health_monitor, pool_id):
        tenant_id = health_monitor['tenant_id']
        data_context = self._get_all_context_for_given_tenant(context, tenant_id)
        context['service_info'] = data_context
        kwargs = {'health_monitor':health_monitor, 'pool_id':pool_id}
        body = {'kwargs': **kwargs,
                'context': context}
        rest_client.send_request(REQUEST_METHOD,
                                 SERVER_IP_ADDR,
                                 'lb/create_pool_health_monitor',
                                 'POST',
                                 headers = 'application/json',
                                 body = body)

    def update_pool_health_monitor(self, context, old_health_monitor,
                                   health_monitor, pool_id):
        tenant_id = old_health_monitor['tenant_id']
        data_context = self._get_all_context_for_given_tenant(context, tenant_id)
        context['service_info'] = data_context
        kwargs = {'old_health_monitor':old_health_monitor,'health_monitor':health_monitor, 'pool_id':pool_id}
        body = {'kwargs': **kwargs,
                'context': context}
        rest_client.send_request(REQUEST_METHOD,
                                 SERVER_IP_ADDR,
                                 'lb/update_pool_health_monitor',
                                 'PUT',
                                 headers = 'application/json',
                                 body = body)

    def delete_pool_health_monitor(self, context, health_monitor, pool_id):
        tenant_id = health_monitor['tenant_id']
        data_context = self._get_all_context_for_given_tenant(context, tenant_id)
        context['service_info'] = data_context
        kwargs = {'health_monitor':health_monitor, 'pool_id':pool_id}
        body = {'kwargs': **kwargs,
                'context': context}
        rest_client.send_request(REQUEST_METHOD,
                                 SERVER_IP_ADDR,
                                 'lb/delete_pool_health_monitor',
                                 'DELETE',
                                 headers = 'application/json',
                                 body = body)

    def _get_core_context(self, context, filters):
        core_plugin = self.core_plugin
        subnets = core_plugin.get_subnets(
                      context,
                      filters)
        ports = core_plugin.get_ports(
                    context,
                    filters)
        '''
        routers = core_plugin.get_routers(
                      context,
                      filters)
        '''
        return {'subnets':subnets,'ports':ports}

    def _get_lb_context(self, context, filters):
        pools = super(LbaasAgentManager, self).\
                   get_pools(context, filters)
        vips = super(LbaasAgentManager, self).\
                   get_vips(context, filters)
        members = super((LbaasAgentManager, self).\
                      get_members(context, filters)
        health_monitors = super((LbaasAgentManager, self).\
                              get_health_monitors(context, filters)
        return {'pools':pools,
                'vips':vips,
                'members':members,
                'health_monitors':health_monitors}

    def _get_all_context_for_given_tenant(self, context, tenant_id=None):
        if context.is_admin :
            tenant_id = context.tenant_id
        if tenant_id == None :
            raise TenantNotFound()
        filters = {'tenant_id':tenant_id}
        data_context = self._get_lb_context(context, filters)
        data_context.update(self._get_core_context(context, filters))
        return data_context

