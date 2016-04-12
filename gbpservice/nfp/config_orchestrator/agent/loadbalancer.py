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
import ast
from gbpservice.nfp.common import constants as const
from gbpservice.nfp.config_orchestrator.agent import common
from gbpservice.nfp.config_orchestrator.agent import topics as a_topics
from gbpservice.nfp.lib import transport
from neutron_lbaas.db.loadbalancer import loadbalancer_db
from oslo_log import helpers as log_helpers
import oslo_messaging as messaging
from oslo_log import log

LOG = log.getLogger(__name__)


"""
RPC handler for Loadbalancer service
"""


class LbAgent(loadbalancer_db.LoadBalancerPluginDb):
    RPC_API_VERSION = const.LOADBALANCER_RPC_API_VERSION
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

    def _prepare_request_data(self, context, vip):
        request_data = None
        try:
            if vip is not None:
                vip_desc = ast.literal_eval(vip['description'])
                request_data = common.get_network_function_map(
                    context, vip_desc['network_function_id'])
                # Adding Service Type #
                request_data.update({"service_type": "loadbalancer",
                                     "vip_id": vip['id']})
        except Exception as e:
            LOG.error(e)
            return request_data
        return request_data

    @log_helpers.log_method_call
    def update_status(self, context, **kwargs):
        kwargs = kwargs['kwargs']
        rpcClient = transport.RPCClient(a_topics.LB_NFP_PLUGIN_TOPIC)
        rpcClient.cctxt = rpcClient.client.prepare(
            version=const.LOADBALANCER_RPC_API_VERSION)
        msg = ("NCO received LB's update_status API, making an update_status "
               "RPC call to plugin for %s: %s with status %s" % (
                   kwargs['obj_type'], kwargs['obj_id'],
                   kwargs['status']))
        LOG.info(msg)
        rpcClient.cctxt.cast(context, 'update_status',
                             obj_type=kwargs['obj_type'],
                             obj_id=kwargs['obj_id'],
                             status=kwargs['status'])
        if kwargs['obj_type'] == 'vip':
            vip = kwargs['vip']
            request_data = self._prepare_request_data(context, vip)
            LOG.info("%s : %s " % (request_data, vip))
            # Sending An Event for visiblity #
            data = {'resource': None,
                    'context': context}
            data['resource'] = {'eventtype': 'SERVICE',
                                'eventid': 'SERVICE_CREATED',
                                'eventdata': request_data}
            ev = self._sc.new_event(id='SERVICE_CREATE',
                                    key='SERVICE_CREATE', data=data)
            self._sc.post_event(ev)

    @log_helpers.log_method_call
    def update_pool_stats(self, context, **kwargs):
        kwargs = kwargs['kwargs']
        rpcClient = transport.RPCClient(a_topics.LB_NFP_PLUGIN_TOPIC)
        rpcClient.cctxt = rpcClient.client.prepare(
            version=const.LOADBALANCER_RPC_API_VERSION)
        msg = ("NCO received LB's update_pool_stats API, making an "
               "update_pool_stats RPC call to plugin for updating"
               "pool: %s stats" % (kwargs['obj_id']))
        LOG.info(msg)
        rpcClient.cctxt.cast(context, 'update_pool_stats',
                             pool_id=kwargs['pool_id'],
                             stats=kwargs['stats'],
                             host=kwargs['host'])

    @log_helpers.log_method_call
    def vip_deleted(self, context, **kwargs):
        LOG.info(kwargs)
        kwargs = kwargs['kwargs']
        vip = kwargs['vip']
        request_data = self._prepare_request_data(context, vip)
        LOG.info("%s : %s " % (request_data, vip))
        # Sending An Event for visiblity #
        data = {'resource': None,
                'context': context}
        data['resource'] = {'eventtype': 'SERVICE',
                            'eventid': 'SERVICE_DELETED',
                            'eventdata': request_data}
        ev = self._sc.new_event(id='SERVICE_DELETE',
                                key='SERVICE_DELETE', data=data)
        self._sc.post_event(ev)
