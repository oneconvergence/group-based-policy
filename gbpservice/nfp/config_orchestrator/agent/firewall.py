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

from gbpservice.nfp.config_orchestrator.agent import common
from gbpservice.nfp.config_orchestrator.agent import topics as a_topics
from gbpservice.nfp.core import common as nfp_common
from gbpservice.nfp.lib import transport

from neutron_fwaas.db.firewall import firewall_db

from oslo_log import helpers as log_helpers
from oslo_log import log as oslo_logging
import oslo_messaging as messaging

LOGGER = oslo_logging.getLogger(__name__)
LOG = nfp_common.log

"""
RPC handler for Firwrall service
"""


class FwAgent(firewall_db.Firewall_db_mixin):

    RPC_API_VERSION = '1.0'
    target = messaging.Target(version=RPC_API_VERSION)

    def __init__(self, conf, sc):
        super(FwAgent, self).__init__()
        self._conf = conf
        self._sc = sc
        self._db_inst = super(FwAgent, self)

    def _get_firewalls(self, context, tenant_id,
                       firewall_policy_id, description):
        filters = {'tenant_id': [tenant_id],
                   'firewall_policy_id': [firewall_policy_id]}
        args = {'context': context, 'filters': filters}
        firewalls = self._db_inst.get_firewalls(**args)
        for firewall in firewalls:
            firewall['description'] = description
        return firewalls

    def _get_firewall_policies(self, context, tenant_id,
                               firewall_policy_id, description):
        filters = {'tenant_id': [tenant_id],
                   'id': [firewall_policy_id]}
        args = {'context': context, 'filters': filters}
        firewall_policies = self._db_inst.get_firewall_policies(**args)
        return firewall_policies

    def _get_firewall_rules(self, context, tenant_id,
                            firewall_policy_id, description):
        filters = {'tenant_id': [tenant_id],
                   'firewall_policy_id': [firewall_policy_id]}
        args = {'context': context, 'filters': filters}
        firewall_rules = self._db_inst.get_firewall_rules(**args)
        return firewall_rules

    def _get_firewall_context(self, **kwargs):
        firewalls = self._get_firewalls(**kwargs)
        firewall_policies = self._get_firewall_policies(**kwargs)
        firewall_rules = self._get_firewall_rules(**kwargs)
        return {'firewalls': firewalls,
                'firewall_policies': firewall_policies,
                'firewall_rules': firewall_rules}

    def _get_core_context(self, context, filters):
        return common.get_core_context(context,
                                       filters,
                                       self._conf.host)

    def _context(self, **kwargs):
        context = kwargs.get('context')
        if context.is_admin:
            kwargs['tenant_id'] = context.tenant_id
        db = self._get_firewall_context(**kwargs)
        # Commenting below as ports, subnets and routers data not need
        # by firewall with present configurator

        # db.update(self._get_core_context(context, filters))
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

    def _data_wrapper(self, context, firewall, host, nf, reason):
        # Hardcoding the position for fetching data since we are owning
        # its positional change
        description = ast.literal_eval((nf['description'].split('\n'))[1])
        fw_mac = description['provider_ptg_info'][0]
        firewall.update({'description': str(description)})
        kwargs = {'context': context,
                  'firewall_policy_id': firewall[
                      'firewall_policy_id'],
                  'description': str(description),
                  'tenant_id': firewall['tenant_id']}

        ctx_dict, rsrc_ctx_dict = self.\
            _prepare_resource_context_dicts(**kwargs)
        nfp_context = {'network_function_id': nf['id'],
                       'neutron_context': ctx_dict,
                       'fw_mac': fw_mac,
                       'requester': 'nas_service'}
        resource = resource_type = 'firewall'
        resource_data = {resource: firewall,
                         'host': host,
                         'neutron_context': rsrc_ctx_dict}
        body = common.prepare_request_data(nfp_context, resource,
                                           resource_type, resource_data,
                                           description['service_vendor'])
        return body

    def _fetch_nf_from_resource_desc(self, desc):
        desc_dict = ast.literal_eval(desc)
        nf_id = desc_dict['network_function_id']
        return nf_id

    @log_helpers.log_method_call
    def create_firewall(self, context, firewall, host):
        # Fetch nf_id from description of the resource
        nf_id = self._fetch_nf_from_resource_desc(firewall["description"])
        nf = common.get_network_function_details(context, nf_id)
        body = self._data_wrapper(context, firewall, host, nf, 'CREATE')
        transport.send_request_to_configurator(self._conf,
                                               context, body, "CREATE")

    @log_helpers.log_method_call
    def delete_firewall(self, context, firewall, host):
        # Fetch nf_id from description of the resource
        nf_id = self._fetch_nf_from_resource_desc(firewall["description"])
        nf = common.get_network_function_details(context, nf_id)
        body = self._data_wrapper(context, firewall, host, nf, 'DELETE')
        transport.send_request_to_configurator(self._conf,
                                               context, body, "DELETE")


class FirewallNotifier(object):

    def __init__(self, conf, sc):
        self._sc = sc
        self._conf = conf

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

    def _prepare_request_data(self, context,
                              nf_id,  resource_id,
                              fw_mac, service_type):
        request_data = None
        try:
            request_data = common.get_network_function_map(
                context, nf_id)
            # Adding Service Type #
            request_data.update({"service_type": service_type,
                                 "fw_mac": fw_mac,
                                 "neutron_resource_id": resource_id})
        except Exception as e:
            LOG(LOGGER, 'ERROR', '%s' % (e))
            return request_data
        return request_data

    def set_firewall_status(self, context, notification_data):
        notification = notification_data['notification'][0]
        notification_info = notification_data['info']
        resource_data = notification['data']
        firewall_id = resource_data['firewall_id']
        status = resource_data['status']
        nf_id = notification_info['context']['network_function_id']
        fw_mac = notification_info['context']['fw_mac']
        service_type = notification_info['service_type']
        msg = ("Config Orchestrator received "
               "firewall_configuration_create_complete API, making an "
               "set_firewall_status RPC call for firewall: %s & status "
               " %s" % (firewall_id, status))
        LOG(LOGGER, 'INFO', '%s' % (msg))

        # RPC call to plugin to set firewall status
        rpcClient = transport.RPCClient(a_topics.FW_NFP_PLUGIN_TOPIC)
        rpcClient.cctxt.cast(context, 'set_firewall_status',
                             host=resource_data['host'],
                             firewall_id=firewall_id,
                             status=status)

        # Sending An Event for visiblity #
        event_data = {'context': context.to_dict(),
                      'nf_id': nf_id,
                      'fw_mac': fw_mac,
                      'service_type': service_type,
                      'resource_id': firewall_id,
                      }
        ev = self._sc.new_event(id='SERVICE_CREATE_PENDING',
                                key='SERVICE_CREATE_PENDING',
                                data=event_data, max_times=24)
        self._sc.poll_event(ev)

    def firewall_deleted(self, context, notification_data):
        notification = notification_data['notification'][0]
        notification_info = notification_data['info']
        resource_data = notification['data']
        firewall_id = resource_data['firewall_id']
        nf_id = notification_info['context']['network_function_id']
        fw_mac = notification_info['context']['fw_mac']
        service_type = notification_info['service_type']
        resource_id = firewall_id

        msg = ("Config Orchestrator received "
               "firewall_configuration_delete_complete API, making an "
               "firewall_deleted RPC call for firewall: %s" % (firewall_id))
        LOG(LOGGER, 'INFO', '%s' % (msg))

        # RPC call to plugin to update firewall deleted
        rpcClient = transport.RPCClient(a_topics.FW_NFP_PLUGIN_TOPIC)
        rpcClient.cctxt.cast(context, 'firewall_deleted',
                             host=resource_data['host'],
                             firewall_id=firewall_id)

        # Sending An Event for visiblity #
        request_data = self._prepare_request_data(context, nf_id,
                                                  resource_id,
                                                  fw_mac, service_type)
        LOG(LOGGER, 'INFO', "%s : %s " % (request_data, nf_id))
        self._trigger_service_event(context, 'SERVICE', 'SERVICE_DELETED',
                                    request_data)
