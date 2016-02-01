from neutron.db.vpn import vpn_db
from neutron import manager
from oslo.config import cfg
from oslo import messaging

from neutron.agent import rpc as agent_rpc
from neutron.common import exceptions
from neutron.services.vpn.common import topics
from neutron import context
from neutron.openstack.common import importutils
from neutron.openstack.common import log as logging
from neutron.openstack.common import loopingcall
from neutron.openstack.common import periodic_task
from neutron.plugins.common import constants
from neutron.services.vpn.common import constants as vpn_const
from neutron.services.vpn import RestClientOverUnix as rest_client

class TenantNotFound(exceptions.NeutronException):
    message = _("Cannot Get context as tenant_id is not available")

LOG = logging.getLogger(__name__)

vpn_agent_opts = [
    cfg.MultiStrOpt(
        'vpn_device_driver',
        default=[],
        help=_("The vpn device drivers Neutron will use")),
]
cfg.CONF.register_opts(vpn_agent_opts, 'vpnagent')

REQUEST_METHOD = 'http' #can be http,https
SERVER_IP_ADDR = '192.168.2.68'

#class VpnAgentManager(periodic_task.PeriodicTasks, vpn_db.VPNPluginDb, vpn_db.VPNPluginRpcDbMixin):
class VpnAgentManager(vpn_db.VPNPluginDb, vpn_db.VPNPluginRpcDbMixin):
    def __init__(self, conf):
        super(VpnAgentManager, self).__init__()

        self.needs_sync = True
        self.conf = conf
        self.context = context.get_admin_context_without_session()
        self.agent_state = {
            'binary': 'oc-vpn-agent',
            'host': conf.host,
            'topic': topics.VPN_AGENT_TOPIC,
            'agent_type': vpn_const.AGENT_TYPE_VPN,
            'start_flag': True}
        self.admin_state_up = True
        self.state_rpc = agent_rpc.PluginReportStateAPI(
            topics.VPN_PLUGIN_TOPIC)
        report_interval = self.conf.AGENT.report_interval
        if report_interval:
            heartbeat = loopingcall.FixedIntervalLoopingCall(
                self._report_state)
            heartbeat.start(interval=report_interval)
        self._core_plugin = None

    def _report_state(self):
        LOG.debug(_("[VPN Agent] Report state task invoked"))
        try:
            self.state_rpc.report_state(self.context, self.agent_state)
            self.agent_state.pop('start_flag', None)
        except Exception:
            LOG.exception(_("[VPN Agent] Failed reporting state!"))


    @property
    def core_plugin(self):
        if not self._core_plugin:
            self._core_plugin = manager.NeutronManager.get_plugin()
        return self._core_plugin

    def vpnservice_updated(self, context, **kwargs):
        LOG.debug(_("vpnservice_updated from server side"))
        resource = kwargs.get('resource')
        data_context = self._get_all_context_for_given_tenant(context, resource['tenant_id'])
        context['service_info'] = data_context
        body = {'kwargs': kwargs,
                'context': context}
        try :
            resp, content = rest_client.post_request(REQUEST_METHOD,
                                                     SERVER_IP_ADDR,
                                                     'vpn/vpnservices_updated',
                                                     body = body)
        except rest_client.RestClientException:
            LOG.error("Request Failed : RestClient Exception Occur")

    def _get_vpn_context(self, context, filters):
        vpnservices = super(VpnAgentManager, self).get_vpnservices(
            context,
            filters)

        ikepolicies = super(VpnAgentManager, self).get_ikepolicies(
            context,
            filters)

        ipsecpolicies = super(VpnAgentManager, self).get_ipsecpolicies(
            context,
            filters)

        ipsec_site_conns = super(VpnAgentManager, self).get_ipsec_site_connections(
            context,
            filters=s_filters)

        ssl_vpn_conns = super(VpnAgentManager, self).get_ssl_vpn_connections(
            context,
            filters=s_filters)

        return {'vpnservices': vpnservices,
                'ikepolicies': ikepolicies,
                'ipsecpolicies': ipsecpolicies,
                'ipsec_site_conns': ipsec_site_conns,
                'ssl_vpn_conns': ssl_vpn_conns}

    def _get_core_context(self, context, filters):
        core_plugin = self.core_plugin
        subnets = core_plugin.get_subnets(
                      context,
                      filters)

        routers = core_plugin.get_routers(
                      context,
                      filters)
        return {'subnets':subnets,
                'routers':routers}


    def _get_all_context_for_given_tenant(self, context, tenant_id):
        if context.is_admin :
            tenant_id = context.tenant_id
        if tenant_id == None :
            raise TenantNotFound()
        filters = {'tenant_id':tenant_id}
        data_context = self._get_vpn_context(context, filters)
        data_context.update(self._get_core_context(context, filters))
        return data_context

