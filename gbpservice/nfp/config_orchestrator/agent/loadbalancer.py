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

from neutron_lbaas.db.loadbalancer import loadbalancer_db
from neutron_lbaas.db.loadbalancer import loadbalancer_db
from gbpservice.nfp.config_orchestrator.agent import topics as a_topics
from gbpservice.nfp.config_orchestrator.agent.common import *
from gbpservice.nfp.lib.transport import *

LOG = logging.getLogger(__name__)


def update_status(**kwargs):
    rpcClient = RPCClient(a_topics.LB_NFP_PLUGIN_TOPIC)
    context = kwargs.get('context')
    rpc_ctx = n_context.Context.from_dict(context)
    del kwargs['context']
    rpcClient.cctxt.cast(rpc_ctx, 'update_status',
                         obj_type=kwargs['obj_type'],
                         obj_id=kwargs['obj_id'],
                         status=kwargs['status'])


def update_pool_stats(**kwargs):
    rpcClient = RPCClient(a_topics.LB_NFP_PLUGIN_TOPIC)
    context = kwargs.get('context')
    rpc_ctx = n_context.Context.from_dict(context)
    del kwargs['context']
    rpcClient.cctxt.cast(rpc_ctx, 'update_pool_stats',
                         pool_id=kwargs['pool_id'],
                         stats=kwargs['stats'],
                         host=kwargs['host'])


def pool_destroyed(**kwargs):
    rpcClient = RPCClient(a_topics.LB_NFP_PLUGIN_TOPIC)
    context = kwargs.get('context')
    rpc_ctx = n_context.Context.from_dict(context)
    del kwargs['context']
    rpcClient.cctxt.cast(rpc_ctx, 'pool_destroyed',
                         pool_id=kwargs['pool_id'])


def pool_deployed(**kwargs):
    rpcClient = RPCClient(a_topics.LB_NFP_PLUGIN_TOPIC)
    context = kwargs.get('context')
    rpc_ctx = n_context.Context.from_dict(context)
    del kwargs['context']
    rpcClient.cctxt.cast(rpc_ctx, 'pool_deployed',
                         pool_id=kwargs['pool_id'])


class LbAgent(loadbalancer_db.LoadBalancerPluginDb):
    RPC_API_VERSION = '1.0'
    _target = target.Target(version=RPC_API_VERSION)

    def __init__(self, conf, sc):
        self._conf = conf
        self._sc = sc
        super(LbAgent, self).__init__()

    def _post(self, context, tenant_id, name, **kwargs):
        db = self._context(context, tenant_id)
        context_dict = context.to_dict()
        context_dict.update({'service_info': db})
        kwargs.update({'context': context_dict})
        body = prepare_request_data(name, kwargs, "loadbalancer")
        send_request_to_configurator(self._conf, context, body, "CREATE")

    def _delete(self, context, tenant_id, name, **kwargs):
        db = self._context(context, tenant_id)
        context_dict = context.to_dict()
        context_dict.update({'service_info': db})
        kwargs.update({'context': context_dict})
        body = prepare_request_data(name, kwargs, "loadbalancer")
        send_request_to_configurator(self._conf, context, body, "DELETE")

    def create_vip(self, context, vip):
        self._post(context, vip['tenant_id'], 'vip', vip=vip)

    def delete_vip(self, context, vip):
        self._delete(context, vip['tenant_id'], 'vip', vip=vip)

    def create_pool(self, context, pool, driver_name):
        self._post(
            context, pool['tenant_id'],
            'pool', pool=pool, driver_name=driver_name)

    def delete_pool(self, context, pool):
        self._delete(context, pool['tenant_id'], 'pool', pool=pool)

    def create_member(self, context, member):
        self._post(context, member['tenant_id'], 'member', member=member)

    def delete_member(self, context, member):
        self._delete(
            context, member['tenant_id'], 'member',
            member=member)

    def create_pool_health_monitor(self, context, health_monitor, pool_id):
        self._post(context, health_monitor[
            'tenant_id'], 'pool_health_monitor',
            health_monitor=health_monitor, pool_id=pool_id)

    def delete_pool_health_monitor(self, context, health_monitor, pool_id):
        self._delete(
            context, health_monitor['tenant_id'], 'pool_health_monitor',
            health_monitor=health_monitor, pool_id=pool_id)

    def _context(self, context, tenant_id):
        if context.is_admin:
            tenant_id = context.tenant_id
        filters = {'tenant_id': [tenant_id]}
        db = self._get_lb_context(context, filters)
        db.update(self._get_core_context(context, filters))
        return db

    def _get_core_context(self, context, filters):
        core_context_dict = get_core_context(context, filters, self._conf.host)
        del core_context_dict['routers']
        return core_context_dict

    def _get_lb_context(self, context, filters):
        args = {'context': context, 'filters': filters}
        db_data = super(LbAgent, self)
        return {'pools': db_data.get_pools(**args),
                'vips': db_data.get_vips(**args),
                'members': db_data.get_members(**args),
                'health_monitors': db_data.get_health_monitors(**args)}
