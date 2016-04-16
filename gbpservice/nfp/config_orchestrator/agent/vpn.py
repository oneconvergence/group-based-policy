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

from gbpservice.nfp.config_orchestrator.agent import common
from gbpservice.nfp.config_orchestrator.agent import topics as a_topics
from gbpservice.nfp.lib import transport
from neutron_vpnaas.db.vpn import vpn_db
from oslo_log import helpers as log_helpers
from oslo_log import log
import oslo_messaging as messaging

LOG = log.getLogger(__name__)


"""
RPC handler for VPN service
"""


class VpnAgent(vpn_db.VPNPluginDb, vpn_db.VPNPluginRpcDbMixin):
    RPC_API_VERSION = '1.0'
    target = messaging.Target(version=RPC_API_VERSION)

    def __init__(self, conf, sc):
        self._conf = conf
        self._sc = sc
        super(VpnAgent, self).__init__()

    @log_helpers.log_method_call
    def vpnservice_updated(self, context, **kwargs):

        resource_data = kwargs.get('resource')
        # Collecting db entry required by configurator.
        db = self._context(context, resource_data['tenant_id'])
        # Addind service_info to neutron context and sending
        # dictionary format to the configurator.
        context_dict = context.to_dict()
        context_dict.update({'service_info': db})
        kwargs.update({'context': context_dict})
        resource = kwargs.get('rsrc_type')
        reason = kwargs.get('reason')
        body = common.prepare_request_data(resource, kwargs, "vpn")
        transport.send_request_to_configurator(self._conf,
                                               context, body,
                                               reason)

    def _context(self, context, tenant_id):
        if context.is_admin:
            tenant_id = context.tenant_id
        filters = {'tenant_id': [tenant_id]}
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
        core_context_dict = common.get_core_context(context,
                                                    filters,
                                                    self._conf.host)
        del core_context_dict['ports']
        return core_context_dict

    # TODO(ashu): Need to fix once vpn code gets merged in mitaka branch
    @log_helpers.log_method_call
    def update_status(self, context, **kwargs):
        kwargs = kwargs['kwargs']
        rpcClient = transport.RPCClient(a_topics.VPN_NFP_PLUGIN_TOPIC)
        # msg = ("NCO received VPN's update_status API,"
        #       "making an update_status RPC call to plugin for %s object"
        #       "with status %s" % (kwargs['obj_id'], kwargs['status']))
        # LOG.info(msg)
        rpcClient.cctxt.cast(context, 'update_status', status=kwargs)

    # TODO(ashu): Need to fix once vpn code gets merged in mitaka branch
    @log_helpers.log_method_call
    def ipsec_site_connection_deleted(self, context, resource_id):
        rpcClient = transport.RPCClient(a_topics.VPN_NFP_PLUGIN_TOPIC)
        # msg = ("NCO received VPN's ipsec_site_conn_deleted API,"
        #       "making an ipsec_site_conn_deleted RPC call to plugin for "
        #       "%s object" % (kwargs['obj_id']))
        # LOG.info(msg)
        rpcClient.cctxt.cast(context, 'ipsec_site_connection_deleted', id=resource_id)
