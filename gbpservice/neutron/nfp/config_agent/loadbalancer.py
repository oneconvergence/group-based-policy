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
from gbpservice.neutron.nfp.config_agent.common import *
from gbpservice.neutron.nfp.config_agent import RestClientOverUnix as rc

LOG = logging.getLogger(__name__)


def update_status(self, **kwargs):
    rpcClient = RPCClient(topics.LB_NFP_PLUGIN_TOPIC)
    context = kwargs.get('context')
    del kwargs['context']
    rpcClient.cctxt.cast(context, 'update_status',
                         obj_type=kwargs['obj_type'],
                         obj_id=kwargs['obj_id'],
                         status=kwargs['status'])


def update_pool_stats(self, **kwargs):
    rpcClient = RPCClient(topics.LB_NFP_PLUGIN_TOPIC)
    context = kwargs.get('context')
    del kwargs['context']
    rpcClient.cctxt.cast(context, 'update_pool_stats',
                         pool_id=kwargs['pool_id'],
                         stats=kwargs['stats'],
                         host=kwargs['host'])


def pool_destroyed(self, pool_id):
    rpcClient = RPCClient(topics.LB_NFP_PLUGIN_TOPIC)
    context = kwargs.get('context')
    del kwargs['context']
    rpcClient.cctxt.cast(self.context, 'pool_destroyed',
                         pool_id=kwargs['pool_id'])


def pool_deployed(self, **kwargs):
    rpcClient = RPCClient(topics.LB_NFP_PLUGIN_TOPIC)
    context = kwargs.get('context')
    del kwargs['context']
    rpcClient.cctxt.cast(self.context, 'pool_deployed',
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
        try:
            resp, content = rc.post(
                'create_network_function_config', body=body)
        except:
            LOG.error("create_%s -> request failed." % (name))

    def _delete(self, context, tenant_id, name, **kwargs):
        db = self._context(context, tenant_id)
        context_dict = context.to_dict()
        context_dict.update({'service_info': db})
        kwargs.update({'context': context_dict})
        body = prepare_request_data(name, kwargs, "loadbalancer")
        try:
            resp, content = rc.post('delete_network_function_config',
                                    body=body, delete=True)
        except:
            LOG.error("delete_%s -> request failed." % (name))

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

    def create_pool_health_monitor(self, context, hm, pool_id):
        self._post(context, hm[
            'tenant_id'], 'hm',
            hm=hm, pool_id=pool_id)

    def delete_pool_health_monitor(self, context, hm, pool_id):
        self._delete(
            context, hm['tenant_id'], 'hm',
            hm=hm, pool_id=pool_id)

    def _context(self, context, tenant_id):
        if context.is_admin:
            tenant_id = context.tenant_id
        filters = {'tenant_id': tenant_id}
        db = self._get_lb_context(context, filters)
        db.update(self._get_core_context(context, filters))
        return db

    def _get_core_context(self, context, filters):
        args = {'context': context, 'filters': filters}
        core_plugin = self._core_plugin
        return {'subnets': core_plugin.get_subnets(**args),
                'ports': core_plugin.get_ports(**args)}

    def _get_lb_context(self, context, filters):
        args = {'context': context, 'filters': filters}
        db_data = super(LbAgent, self)
        return {'pools': db_data.get_pools(**args),
                'vips': db_data.get_vips(**args),
                'members': db_data.get_members(**args),
                'health_monitors': db_data.get_health_monitors(**args)}
