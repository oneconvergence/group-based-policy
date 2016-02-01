from neutron.db.vpn import vpn_db
from neutron import manager
from oslo.config import cfg
from oslo import messaging
from neutron.openstack.common import log as logging

from gbpservice.neutron.nsf.config_agent import RestClientOverUnix as rc

LOG = logging.getLogger(__name__)


class VpnAgent(vpn_db.VPNPluginDb, vpn_db.VPNPluginRpcDbMixin):
    RPC_API_VERSION = '1.0'
    target = messaging.Target(version=RPC_API_VERSION)

    def __init__(self, conf, sc):
        self._conf = conf
        self._sc = sc
        self._core_plugin = None
        super(VpnAgentManager, self).__init__()

    @property
    def core_plugin(self):
        if not self._core_plugin:
            self._core_plugin = manager.NeutronManager.get_plugin()
        return self._core_plugin

    def vpnservice_updated(self, context, **kwargs):
        LOG.debug(_("vpnservice_updated from server side"))
        resource = kwargs.get('resource')
        db = self._context(context, resource['tenant_id'])
        context['service_info'] = db
        body = {'kwargs': **kwargs,
                'context': context}
        try:
            resp, content = rc.post('vpn/vpnservice_updated', body=body)
        except:
            LOG.error("vpnservice_updated -> request failed.")

    def _context(self, context, tenant_id):
        if context.is_admin:
            tenant_id = context.tenant_id
        filters = {'tenant_id': tenant_id}
        db = self._get_vpn_context(context, filters)
        db.update(self._get_core_context(context, filters))
        return db

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

        ipsec_site_conns = super(VpnAgentManager, self).\
            get_ipsec_site_connections(
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
        return {'subnets': subnets,
                'routers': routers}
