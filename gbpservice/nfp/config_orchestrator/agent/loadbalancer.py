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
import copy

from gbpservice.nfp.common import constants as const
from gbpservice.nfp.config_orchestrator.agent import common
from gbpservice.nfp.config_orchestrator.agent import topics as a_topics
from gbpservice.nfp.core import common as nfp_common
from gbpservice.nfp.lib import transport

from neutron_lbaas.db.loadbalancer import loadbalancer_db

from oslo_log import helpers as log_helpers
from oslo_log import log as oslo_logging
import oslo_messaging as messaging

LOGGER = oslo_logging.getLogger(__name__)
LOG = nfp_common.log

"""
RPC handler for Loadbalancer service
"""


class LbAgent(loadbalancer_db.LoadBalancerPluginDb):
    RPC_API_VERSION = const.LOADBALANCER_RPC_API_VERSION
    target = messaging.Target(version=RPC_API_VERSION)

    def __init__(self, conf, sc):
        super(LbAgent, self).__init__()
        self._conf = conf
        self._sc = sc
        self._db_inst = super(LbAgent, self)

    def _filter_service_info_with_resource(self, lb_db, core_db):
        updated_db = {'subnets': [],
                      'ports': []}
        for pool in lb_db['pools']:
            psubnet_id = pool['subnet_id']
            for subnet in core_db['subnets']:
                if subnet['id'] == psubnet_id:
                    updated_db['subnets'].append(subnet)
        for vip in lb_db['vips']:
            vport_id = vip['port_id']
            for port in core_db['ports']:
                if port['id'] == vport_id:
                    updated_db['ports'].append(port)
        lb_db.update(updated_db)
        return lb_db

    def _get_core_context(self, context, tenant_id):
        filters = {'tenant_id': [tenant_id]}
        core_context_dict = common.get_core_context(context,
                                                    filters,
                                                    self._conf.host)
        del core_context_dict['routers']
        return core_context_dict

    def _get_pools(self, **kwargs):
        context = kwargs.get('context')
        filters = {'tenant_id': [kwargs.get('tenant_id')],
                   'id': [kwargs.get('pool_id')]}
        args = {'context': context, 'filters': filters}
        pools = self._db_inst.get_pools(**args)
        for pool in pools:
            pool['description'] = kwargs.get('description')
        return pools

    def _get_vips(self, **kwargs):
        context = kwargs.get('context')
        filters = {'tenant_id': [kwargs.get('tenant_id')],
                   'pool_id': [kwargs.get('pool_id')]}
        args = {'context': context, 'filters': filters}
        vips = self._db_inst.get_vips(**args)
        for vip in vips:
            vip['description'] = kwargs.get('description')
        return vips

    def _get_members(self, **kwargs):
        context = kwargs.get('context')
        filters = {'tenant_id': [kwargs.get('tenant_id')],
                   'pool_id': [kwargs.get('pool_id')]}
        args = {'context': context, 'filters': filters}
        members = self._db_inst.get_members(**args)
        for member in members:
            member.update({'description': kwargs.get('description')})
        return members

    def _get_health_monitors(self, **kwargs):
        context = kwargs.get('context')
        filters = {'tenant_id': [kwargs.get('tenant_id')],
                   'pool_id': [kwargs.get('pool_id')]}
        args = {'context': context, 'filters': filters}
        health_monitors = self._db_inst.get_health_monitors(**args)
        for health_monitor in health_monitors:
            health_monitor.update({'description': kwargs.get('description')})
        return health_monitors

    def _get_lb_context(self, **kwargs):
        pools = self._get_pools(**kwargs)
        vips = self._get_vips(**kwargs)
        members = self._get_members(**kwargs)
        healthmonitors = self._get_health_monitors(**kwargs)
        return {'pools': pools,
                'vips': vips,
                'members': members,
                'health_monitors': healthmonitors}

    def _context(self, **kwargs):
        context = kwargs.get('context')
        if context.is_admin:
            kwargs['tenant_id'] = context.tenant_id
        lb_db = self._get_lb_context(**kwargs)
        core_db = self._get_core_context(context, kwargs['tenant_id'])
        db = self._filter_service_info_with_resource(lb_db, core_db)
        return db

    def _prepare_resource_context_dicts(self, **kwargs):
        # Prepare context_dict
        context = kwargs.get('context')
        ctx_dict = context.to_dict()
        # Collecting db entry required by configurator.
        # Addind service_info to neutron context and sending
        # dictionary format to the configurator.
        db = self._context(**kwargs)
        rsrc_ctx_dict = copy.deepcopy(ctx_dict)
        rsrc_ctx_dict.update({'service_info': db})
        return ctx_dict, rsrc_ctx_dict

    def _data_wrapper(self, context, tenant_id, name, reason, nf, **kwargs):
        nfp_context = {}
        description = ast.literal_eval((nf['description'].split('\n'))[1])
        if name.lower() == 'pool_health_monitor':
            pool_id = kwargs.get('pool_id')
            kwargs['health_monitor'].update({'description': str(description)})
        elif name.lower() == 'pool':
            pool_id = kwargs['pool'].get('id')
            kwargs['pool']['description'] = str(description)
        elif name.lower() == 'vip':
            pool_id = kwargs['vip'].get('pool_id')
            kwargs['vip']['description'] = str(description)
            nfp_context = {'network_function_id': nf['id'],
                           'vip_id': kwargs['vip']['id']}
        else:
            kwargs[name.lower()].update({'description': str(description)})
            pool_id = kwargs[name.lower()].get('pool_id')

        args = {'tenant_id': tenant_id,
                'pool_id': pool_id,
                'context': context,
                'description': str(description)}
        ctx_dict, rsrc_ctx_dict = self.\
            _prepare_resource_context_dicts(**args)

        nfp_context.update({'neutron_context': ctx_dict,
                            'requester': 'nas_service'})
        resource_type = 'loadbalancer'
        resource = name
        resource_data = {'neutron_context': rsrc_ctx_dict}
        resource_data.update(**kwargs)
        body = common.prepare_request_data(nfp_context, resource,
                                           resource_type, resource_data,
                                           description['service_vendor'])
        return body

    def _post(self, context, tenant_id, name, nf, **kwargs):
        body = self._data_wrapper(context, tenant_id, name,
                                  'CREATE', nf, **kwargs)
        transport.send_request_to_configurator(self._conf,
                                               context, body, "CREATE")

    def _delete(self, context, tenant_id, name, nf, **kwargs):
        body = self._data_wrapper(context, tenant_id, name,
                                  'DELETE', nf, **kwargs)
        transport.send_request_to_configurator(self._conf,
                                               context, body, "DELETE")

    def _get_pool(self, context, pool_id):
        pool = None
        try:
            pool = self._db_inst.get_pool(context, pool_id)
        except Exception as e:
            LOG(LOGGER, 'ERROR', e)
        return pool

    def _fetch_nf_from_resource_desc(self, desc):
        desc_dict = ast.literal_eval(desc)
        nf_id = desc_dict['network_function_id']
        return nf_id

    @log_helpers.log_method_call
    def create_vip(self, context, vip):
        # Fetch nf_id from description of the resource
        nf_id = self._fetch_nf_from_resource_desc(vip["description"])
        nf = common.get_network_function_details(context, nf_id)
        self._post(context, vip['tenant_id'], 'vip', nf, vip=vip)

    @log_helpers.log_method_call
    def delete_vip(self, context, vip):
        # Fetch nf_id from description of the resource
        nf_id = self._fetch_nf_from_resource_desc(vip["description"])
        nf = common.get_network_function_details(context, nf_id)
        self._delete(context, vip['tenant_id'], 'vip', nf, vip=vip)

    @log_helpers.log_method_call
    def create_pool(self, context, pool, driver_name):
        # Fetch nf_id from description of the resource
        nf_id = self._fetch_nf_from_resource_desc(pool["description"])
        nf = common.get_network_function_details(context, nf_id)
        self._post(
            context, pool['tenant_id'],
            'pool', nf, pool=pool, driver_name=driver_name)

    @log_helpers.log_method_call
    def delete_pool(self, context, pool):
        # Fetch nf_id from description of the resource
        nf_id = self._fetch_nf_from_resource_desc(pool["description"])
        nf = common.get_network_function_details(context, nf_id)
        self._delete(context, pool['tenant_id'], 'pool', nf, pool=pool)

    @log_helpers.log_method_call
    def create_member(self, context, member):
        # Fetch pool from pool_id
        pool = self._get_pool(context, member['pool_id'])
        # Fetch nf_id from description of the resource
        nf_id = self._fetch_nf_from_resource_desc(pool["description"])
        nf = common.get_network_function_details(context, nf_id)
        self._post(context, member['tenant_id'], 'member', nf, member=member)

    @log_helpers.log_method_call
    def delete_member(self, context, member):
        # Fetch pool from pool_id
        pool = self._get_pool(context, member['pool_id'])
        # Fetch nf_id from description of the resource
        nf_id = self._fetch_nf_from_resource_desc(pool["description"])
        nf = common.get_network_function_details(context, nf_id)
        self._delete(
            context, member['tenant_id'], 'member',
            nf, member=member)

    @log_helpers.log_method_call
    def create_pool_health_monitor(self, context, health_monitor, pool_id):
        # Fetch pool from pool_id
        pool = self._get_pool(context, pool_id)
        # Fetch nf_id from description of the resource
        nf_id = self._fetch_nf_from_resource_desc(pool["description"])
        nf = common.get_network_function_details(context, nf_id)
        self._post(context, health_monitor[
            'tenant_id'], 'pool_health_monitor',
            nf, health_monitor=health_monitor, pool_id=pool_id)

    @log_helpers.log_method_call
    def delete_pool_health_monitor(self, context, health_monitor, pool_id):
        # Fetch pool from pool_id
        pool = self._get_pool(context, pool_id)
        # Fetch nf_id from description of the resource
        nf_id = self._fetch_nf_from_resource_desc(pool["description"])
        nf = common.get_network_function_details(context, nf_id)
        self._delete(
            context, health_monitor['tenant_id'], 'pool_health_monitor',
            nf, health_monitor=health_monitor, pool_id=pool_id)


class LoadbalancerNotifier(object):

    def __init__(self, conf, sc):
        self._sc = sc
        self._conf = conf

    def _prepare_request_data(self, context, nf_id,
                              resource_id, vip_id,
                              service_type):
        request_data = None
        try:
            request_data = common.get_network_function_map(
                context, nf_id)
            # Adding Service Type #
            request_data.update({"service_type": service_type,
                                 "vip_id": vip_id,
                                 "neutron_resource_id": resource_id,
                                 "LogMetaID": nf_id})
        except Exception as e:
            LOG(LOGGER, 'ERROR', '%s' % (e))
            return request_data
        return request_data

    def _trigger_service_event(self, context, event_type, event_id,
                               request_data):
        event_data = {'resource': None,
                      'context': context.to_dict()}
        event_data['resource'] = {'eventtype': event_type,
                                  'eventid': event_id,
                                  'eventdata': request_data}
        ev = self._sc.new_event(id=event_id,
                                key=event_id, data=event_data)
        self._sc.post_event(ev)

    def update_status(self, context, notification_data):
        notification = notification_data['notification'][0]
        notification_info = notification_data['info']
        resource_data = notification['data']
        obj_type = resource_data['obj_type']
        obj_id = resource_data['obj_id']
        status = resource_data['status']
        service_type = notification_info['service_type']
        msg = ("NCO received LB's update_status API, making an update_status "
               "RPC call to plugin for %s: %s with status %s" % (
                   obj_type, obj_id, status))
        LOG(LOGGER, 'INFO', "%s" % (msg))

        # RPC call to plugin to update status of the resource
        rpcClient = transport.RPCClient(a_topics.LB_NFP_PLUGIN_TOPIC)
        rpcClient.cctxt = rpcClient.client.prepare(
            version=const.LOADBALANCER_RPC_API_VERSION)
        rpcClient.cctxt.cast(context, 'update_status',
                             obj_type=obj_type,
                             obj_id=obj_id,
                             status=status)

        if obj_type.lower() == 'vip':
            nf_id = notification_info['context']['network_function_id']
            vip_id = notification_info['context']['vip_id']

            # sending notification to visibility
            event_data = {'context': context.to_dict(),
                          'nf_id': nf_id,
                          'vip_id': vip_id,
                          'service_type': service_type,
                          'resource_id': vip_id
                          }
            ev = self._sc.new_event(id='SERVICE_CREATE_PENDING',
                                    key='SERVICE_CREATE_PENDING',
                                    data=event_data, max_times=24)
            self._sc.poll_event(ev)

    def update_pool_stats(self, context, notification_data):
        notification = notification_data['notification'][0]
        resource_data = notification['data']
        pool_id = resource_data['pool_id']
        stats = resource_data['stats']
        host = resource_data['host']

        msg = ("NCO received LB's update_pool_stats API, making an "
               "update_pool_stats RPC call to plugin for updating"
               "pool: %s stats" % (pool_id))
        LOG(LOGGER, 'INFO', '%s' % (msg))

        # RPC call to plugin to update stats of pool
        rpcClient = transport.RPCClient(a_topics.LB_NFP_PLUGIN_TOPIC)
        rpcClient.cctxt = rpcClient.client.prepare(
            version=const.LOADBALANCER_RPC_API_VERSION)
        rpcClient.cctxt.cast(context, 'update_pool_stats',
                             pool_id=pool_id,
                             stats=stats,
                             host=host)

    def vip_deleted(self, context, notification_data):
        notification_info = notification_data['info']
        nf_id = notification_info['context']['network_function_id']
        vip_id = notification_info['context']['vip_id']
        resource_id = notification_info['context']['vip_id']
        service_type = notification_info['service_type']
        request_data = self._prepare_request_data(context,
                                                  nf_id,
                                                  resource_id,
                                                  vip_id,
                                                  service_type)
        log_msg = ("%s : %s " % (request_data, nf_id))
        LOG(LOGGER, 'INFO', "%s" % (log_msg))

        # Sending An Event for visiblity
        self._trigger_service_event(context, 'SERVICE', 'SERVICE_DELETED',
                                    request_data)
