#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from neutron_vpnaas.db.vpn import vpn_db
from gbpservice.neutron.nfp.config_agent.common import *
from gbpservice.neutron.nfp.config_agent import RestClientOverUnix as rc

LOG = logging.getLogger(__name__)


def update_status(self, **kwargs):
    rpcClient = RPCClient(topics.VPN_NFP_PLUGIN_TOPIC)
    context = kwargs.get('context')
    del kwargs['context']
    rpcClient.cctxt.cast(context, 'update_status',
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
        context_dict = context.to_dict()
        context_dict.update({'service_info': db})
        kwargs.update({'context': context_dict})
        resource = resource_data['rsrc_type']
        reason = resource_data['reason']
        body = prepare_request_data(resource, kwargs, "vpn")
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
        args = {'context': context, 'filters': filters}
        db_data = super(VpnAgent, self)
        return {'vpnservices': db_data.get_vpnservices(**args),
                'ikepolicies': db_data.get_ikepolicies(**args),
                'ipsecpolicies': db_data.get_ipsecpolicies(**args),
                'ipsec_site_conns': db_data.get_ipsec_site_connections(**args)}

    def _get_core_context(self, context, filters):
        args = {'context': context, 'filters': filters}
        core_plugin = self.core_plugin
        return {'subnets': core_plugin.get_subnets(**args),
                'routers': core_plugin.get_routers(**args)}
