from neutron_vpnaas.db.vpn import vpn_db
from neutron import manager
from oslo_config import cfg
from oslo_messaging import target
from oslo_log import log as logging

from gbpservice.neutron.nsf.config_agent import RestClientOverUnix as rc
from gbpservice.neutron.nsf.config_agent import topics
from neutron.common import rpc as n_rpc

LOG = logging.getLogger(__name__)


class Vpn(object):
    API_VERSION = '1.0'

    def __init__(self, host):
        self.topic = topics.VPN_NSF_PLUGIN_TOPIC
        target = target.Target(topic=self.topic,
                               version=self.API_VERSION)
        self.client = n_rpc.get_client(target)
        self.cctxt = self.client.prepare(version=self.API_VERSION,
                                         topic=self.topic)

    def report_state(self, **kwargs):
        context = kwargs.get('context')
        del kwargs['context']
        cctxt.cast(context, 'report_state',
                   **kwargs)

    def update_status(self, **kwargs):
        context = kwargs.get('context')
        del kwargs['context']
        cctxt.cast(context, 'update_status',
                   **kwargs)

    def ipsec_site_conn_deleted(self, **kwargs):
        context = kwargs.get('context')
        del kwargs['context']
        cctxt.cast(context, 'ipsec_site_conn_deleted',
                   **kwargs)


class VpnAgent(vpn_db.VPNPluginDb, vpn_db.VPNPluginRpcDbMixin):
    RPC_API_VERSION = '1.0'
    target = target.Target(version=RPC_API_VERSION)

    def __init__(self, conf, sc):
        self._conf = conf
        self._sc = sc
        super(VpnAgent, self).__init__()

    @property
    def core_plugin(self):
        try:
            return self._core_plugin
        except AttributeError:
            self._core_plugin = manager.NeutronManager.get_plugin()
            return self._core_plugin

    def vpnservice_updated(self, context, **kwargs):

        resource = kwargs.get('resource')
        db = self._context(context, resource['tenant_id'])
        context.__setattr__('service_info', db)
        kwargs.update({'context': context})
        body = {'kwargs': kwargs}
        try:
            resp, content = rc.put('vpn', body=body)
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
        vpnservices = super(VpnAgent, self).get_vpnservices(
            context,
            filters)

        ikepolicies = super(VpnAgent, self).get_ikepolicies(
            context,
            filters)

        ipsecpolicies = super(VpnAgent, self).get_ipsecpolicies(
            context,
            filters)

        ipsec_site_conns = super(VpnAgent, self).\
            get_ipsec_site_connections(
                context,
                filters=filters)

        return {'vpnservices': vpnservices,
                'ikepolicies': ikepolicies,
                'ipsecpolicies': ipsecpolicies,
                'ipsec_site_conns': ipsec_site_conns}

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
