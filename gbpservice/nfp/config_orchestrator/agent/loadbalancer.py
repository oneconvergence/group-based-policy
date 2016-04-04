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
from gbpservice.nfp.lib import transport
from neutron_lbaas.db.loadbalancer import loadbalancer_db
from oslo_log import helpers as log_helpers
import oslo_messaging as messaging


"""
RPC handler for Loadbalancer service
"""


class LbAgent(loadbalancer_db.LoadBalancerPluginDb):
    RPC_API_VERSION = '1.0'
    target = messaging.Target(version=RPC_API_VERSION)

    def __init__(self, conf, sc):
        self._conf = conf
        self._sc = sc
        super(LbAgent, self).__init__()

    def _post(self, context, tenant_id, name, **kwargs):

        # Collecting db entry required by configurator.
        db = self._context(context, tenant_id)
        # Addind service_info to neutron context and sending
        # dictionary format to the configurator.
        context_dict = context.to_dict()
        context_dict.update({'service_info': db})
        kwargs.update({'context': context_dict})
        body = common.prepare_request_data(name, kwargs, "loadbalancer")
        transport.send_request_to_configurator(self._conf,
                                               context, body,
                                               "CREATE")

    def _delete(self, context, tenant_id, name, **kwargs):

        # Collecting db entry required by configurator.
        db = self._context(context, tenant_id)
        # Addind service_info to neutron context and sending
        # dictionary format to the configurator.
        context_dict = context.to_dict()
        context_dict.update({'service_info': db})
        kwargs.update({'context': context_dict})
        body = common.prepare_request_data(name, kwargs, "loadbalancer")
        transport.send_request_to_configurator(self._conf,
                                               context, body,
                                               "DELETE")

    @log_helpers.log_method_call
    def create_vip(self, context, vip):
        self._post(context, vip['tenant_id'], 'vip', vip=vip)

    @log_helpers.log_method_call
    def delete_vip(self, context, vip):
        self._delete(context, vip['tenant_id'], 'vip', vip=vip)

    @log_helpers.log_method_call
    def create_pool(self, context, pool, driver_name):
        self._post(
            context, pool['tenant_id'],
            'pool', pool=pool, driver_name=driver_name)

    @log_helpers.log_method_call
    def delete_pool(self, context, pool):
        self._delete(context, pool['tenant_id'], 'pool', pool=pool)

    @log_helpers.log_method_call
    def create_member(self, context, member):
        self._post(context, member['tenant_id'], 'member', member=member)

    @log_helpers.log_method_call
    def delete_member(self, context, member):
        self._delete(
            context, member['tenant_id'], 'member',
            member=member)

    @log_helpers.log_method_call
    def create_pool_health_monitor(self, context, health_monitor, pool_id):
        self._post(context, health_monitor[
            'tenant_id'], 'pool_health_monitor',
            health_monitor=health_monitor, pool_id=pool_id)

    @log_helpers.log_method_call
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
        core_context_dict = common.get_core_context(context,
                                                    filters,
                                                    self._conf.host)
        del core_context_dict['routers']
        return core_context_dict

    def _get_lb_context(self, context, filters):
        args = {'context': context, 'filters': filters}
        db_data = super(LbAgent, self)
        return {'pools': db_data.get_pools(**args),
                'vips': db_data.get_vips(**args),
                'members': db_data.get_members(**args),
                'health_monitors': db_data.get_health_monitors(**args)}
