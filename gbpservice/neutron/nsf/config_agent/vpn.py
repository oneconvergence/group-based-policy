from neutron_vpnaas.db.vpn import vpn_db
from neutron import manager
from oslo_config import cfg
from oslo_messaging import target
from oslo_log import log as logging

from gbpservice.neutron.nsf.config_agent import RestClientOverUnix as rc
from gbpservice.neutron.nsf.config_agent import topics
from neutron.common import rpc as n_rpc

LOG = logging.getLogger(__name__)

Version = 'v1'


class Vpn(object):
    API_VERSION = '1.0'

    def __init__(self):
        self.topic = topics.VPN_NSF_PLUGIN_TOPIC
        _target = target.Target(topic=self.topic,
                                version=self.API_VERSION)
        n_rpc.init(cfg.CONF)
        self.client = n_rpc.get_client(_target)
        self.cctxt = self.client.prepare(version=self.API_VERSION,
                                         topic=self.topic)

    def update_status(self, **kwargs):
        context = kwargs.get('context')
        del kwargs['context']
        self.cctxt.cast(context, 'update_status',
                        status=kwargs['status'])


class VpnAgent(vpn_db.VPNPluginDb, vpn_db.VPNPluginRpcDbMixin):
    RPC_API_VERSION = '1.0'
    _target = target.Target(version=RPC_API_VERSION)

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

    def _prepare_request_data(self, resource, kwargs):

        request_data = {'info': {
            'version': Version,
            'service_type': 'vpn'
        },

            'config': [{
                'resource': resource,
                'kwargs': kwargs
            }]
        }

        return {'request_data': request_data}

    def _eval_rest_calls(self, reason, body):
        if reason == 'update':
            return rc.put('update_network_function_config', body=body)
        elif reason == 'create':
            return rc.post('create_network_function_config', body=body)
        else:
            return rc.post('delete_network_function_config', body=body,
                           delete=True)

    def vpnservice_updated(self, context, **kwargs):
        resource_data = kwargs.get('resource')
        db = self._context(context, resource_data['tenant_id'])
        context.__setattr__('service_info', db)
        kwargs.update({'context': context})
        resource = resource_data['rsrc_type']
        reason = resource_data['reason']
        body = self._prepare_request_data(resource, kwargs)
        try:
            resp, content = self._eval_rest_calls(reason, body)
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
