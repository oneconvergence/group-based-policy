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

from gbpservice.nfp.common import constants as const
from gbpservice.nfp.lib.transport import RPCClient
from gbpservice.nfp.proxy_agent.lib import topics as a_topics
from neutron import context as n_context

"""Common class for handling notification"""


class NotificationHandler(object):

    def _get_dummy_context(self):
        context = {
            u'read_only': False,
            u'domain': None,
            u'project_name': None,
            u'user_id': None,
            u'show_deleted': False,
            u'roles': [],
            u'user_identity': u'',
            u'project_domain': None,
            u'tenant_name': None,
            u'auth_token': None,
            u'resource_uuid': None,
            u'project_id': None,
            u'tenant_id': None,
            u'is_admin': True,
            u'user': None,
            u'request_id': u'',
            u'user_domain': None,
            u'timestamp': u'',
            u'tenant': None,
            u'user_name': None}
        return context

    def firewall_configuration_create_complete(self, resource, **kwargs):
        rpcClient = RPCClient(a_topics.FW_NFP_CONFIGAGENT_TOPIC)
        context = kwargs.get('context')
        rpc_ctx = n_context.Context.from_dict(context)
        del kwargs['context']
        rpcClient.cctxt.cast(rpc_ctx,
                             'firewall_configuration_create_complete',
                             kwargs=kwargs)

    def firewall_configuration_delete_complete(self, resource, **kwargs):
        rpcClient = RPCClient(a_topics.FW_NFP_CONFIGAGENT_TOPIC)
        context = kwargs.get('context')
        rpc_ctx = n_context.Context.from_dict(context)
        del kwargs['context']
        rpcClient.cctxt.cast(rpc_ctx,
                             'firewall_configuration_delete_complete',
                             kwargs=kwargs)

    def update_status(self, resource, **kwargs):
        if resource == 'vpn':
            self._update_status_vpn(**kwargs)
        else:
            self._update_status_lb(**kwargs)

    def ipsec_site_connection_deleted(self, resource, **kwargs):
        rpcClient = RPCClient(a_topics.VPN_NFP_CONFIGAGENT_TOPIC)
        context = kwargs.get('context')
        rpc_ctx = n_context.Context.from_dict(context)
        del kwargs['context']
        rpcClient.cctxt.cast(rpc_ctx, 'ipsec_site_connection_deleted',
                             resource_id=kwargs['resource_id'])


    def _update_status_vpn(self, **kwargs):
        rpcClient = RPCClient(a_topics.VPN_NFP_CONFIGAGENT_TOPIC)
        context = kwargs.get('context')
        rpc_ctx = n_context.Context.from_dict(context)
        del kwargs['context']
        rpcClient.cctxt.cast(rpc_ctx, 'update_status',
                             kwargs=kwargs)

    def _update_status_lb(self, **kwargs):
        rpcClient = RPCClient(a_topics.LB_NFP_CONFIGAGENT_TOPIC)
        rpcClient.cctxt = rpcClient.client.prepare(
            version=const.LOADBALANCER_RPC_API_VERSION)
        context = kwargs.get('context')
        rpc_ctx = n_context.Context.from_dict(context)
        del kwargs['context']
        rpcClient.cctxt.cast(rpc_ctx, 'update_status', kwargs=kwargs)

    def update_pool_stats(self, resource, **kwargs):
        rpcClient = RPCClient(a_topics.LB_NFP_CONFIGAGENT_TOPIC)
        rpcClient.cctxt = rpcClient.client.prepare(
            version=const.LOADBALANCER_RPC_API_VERSION)
        context = kwargs.get('context')
        rpc_ctx = n_context.Context.from_dict(context)
        del kwargs['context']
        rpcClient.cctxt.cast(rpc_ctx, 'update_pool_stats', kwargs=kwargs)

    def pool_destroyed(self, resource, **kwargs):
        rpcClient = RPCClient(a_topics.LB_NFP_PLUGIN_TOPIC)
        rpcClient.cctxt = rpcClient.client.prepare(
            version=const.LOADBALANCER_RPC_API_VERSION)
        context = kwargs.get('context')
        rpc_ctx = n_context.Context.from_dict(context)
        del kwargs['context']
        rpcClient.cctxt.cast(rpc_ctx, 'pool_destroyed',
                             pool_id=kwargs['pool_id'])

    def pool_deployed(self, resource, **kwargs):
        rpcClient = RPCClient(a_topics.LB_NFP_PLUGIN_TOPIC)
        rpcClient.cctxt = rpcClient.client.prepare(
            version=const.LOADBALANCER_RPC_API_VERSION)
        context = kwargs.get('context')
        rpc_ctx = n_context.Context.from_dict(context)
        del kwargs['context']
        rpcClient.cctxt.cast(rpc_ctx, 'pool_deployed',
                             pool_id=kwargs['pool_id'])

    def ipsec_site_conn_deleted(self, resource, **kwargs):
        rpcClient = RPCClient(a_topics.VPN_NFP_CONFIGAGENT_TOPIC)
        context = kwargs.get('context')
        rpc_ctx = n_context.Context.from_dict(context)
        del kwargs['context']
        rpcClient.cctxt.cast(rpc_ctx, 'ipsec_site_conn_deleted',
                             kwargs=kwargs)

    def vip_deleted(self, resource, **kwargs):
        rpcClient = RPCClient(a_topics.LB_NFP_CONFIGAGENT_TOPIC)
        rpcClient.cctxt = rpcClient.client.prepare(
            version=const.LOADBALANCER_RPC_API_VERSION)
        context = kwargs.get('context')
        rpc_ctx = n_context.Context.from_dict(context)
        del kwargs['context']
        rpcClient.cctxt.cast(rpc_ctx, 'vip_deleted', kwargs=kwargs)

    def network_function_device_notification(self, resource,
                                             kwargs_list, device=True):
        context = self._get_dummy_context()
        topic = [
            a_topics.SERVICE_ORCHESTRATOR_TOPIC,
            a_topics.DEVICE_ORCHESTRATOR_TOPIC][device]
        rpcClient = RPCClient(topic)
        for ele in kwargs_list:
            if 'context' in ele:
                context = ele['context']
                break
        notification_data = {}
        notification_data.\
            update({'resource': resource,
                    'kwargs': kwargs_list})
        rpc_ctx = n_context.Context.from_dict(context)
        rpcClient.cctxt.cast(rpc_ctx, 'network_function_device_notification',
                             notification_data=notification_data)
