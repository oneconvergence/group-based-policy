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
        self._conf = conf
        self._sc = sc
        super(FwAgent, self).__init__()

    def _get_firewall_context(self, context, filters):
        args = {'context': context, 'filters': filters}
        db_data = super(FwAgent, self)
        return {'firewalls': db_data.get_firewalls(**args),
                'firewall_policies': db_data.get_firewall_policies(**args),
                'firewall_rules': db_data.get_firewall_rules(**args)}

    def _get_core_context(self, context, filters):
        return common.get_core_context(context,
                                       filters,
                                       self._conf.host)

    def _context(self, context, tenant_id):
        if context.is_admin:
            tenant_id = context.tenant_id
        filters = {'tenant_id': [tenant_id]}
        db = self._get_firewall_context(context, filters)
        # Commenting below as ports,subnets and routers data not need
        # by firewall with present configurator
        # db.update(self._get_core_context(context, filters))
        return db

    def _prepare_resource_context_dicts(self, context, tenant_id):
        # Prepare context_dict
        ctx_dict = context.to_dict()
        # Collecting db entry required by configurator.
        # Addind service_info to neutron context and sending
        # dictionary format to the configurator.
        db = self._context(context, tenant_id)
        rsrc_ctx_dict = copy.deepcopy(ctx_dict)
        rsrc_ctx_dict.update({'service_info': db})
        return ctx_dict, rsrc_ctx_dict

    def _data_wrapper(self, context, firewall, host, reason):
        # Fetch nf_id from description of the resource
        firewall_desc = ast.literal_eval(firewall['description'])
        fw_mac = firewall_desc['provider_ptg_info'][0]
        nf_id = firewall_desc['network_function_id']
        ctx_dict, rsrc_ctx_dict = self._prepare_resource_context_dicts(
            context, firewall['tenant_id'])
        nfp_context = {'network_function_id': nf_id,
                       'neutron_context': ctx_dict,
                       'fw_mac': fw_mac,
                       'requester': 'nas_service'}
        resource = resource_type = 'firewall'
        resource_data = {resource: firewall,
                         'host': host,
                         'neutron_context': rsrc_ctx_dict}
        body = common.prepare_request_data(nfp_context, resource,
                                           resource_type, resource_data)
        return body

    @log_helpers.log_method_call
    def create_firewall(self, context, firewall, host):
        body = self._data_wrapper(context, firewall, host, 'CREATE')
        transport.send_request_to_configurator(self._conf,
                                               context, body, "CREATE")

    @log_helpers.log_method_call
    def delete_firewall(self, context, firewall, host):
        body = self._data_wrapper(context, firewall, host, 'DELETE')
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

    def _prepare_request_data(self, context, nf_id, fw_mac, service_type):
        request_data = None
        try:
            request_data = common.get_network_function_map(
                context, nf_id)
            # Adding Service Type #
            request_data.update({"service_type": service_type,
                                 "fw_mac": fw_mac})
        except Exception:
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
        request_data = self._prepare_request_data(context, nf_id,
                                                  fw_mac, service_type)
        LOG(LOGGER, 'INFO', "%s : %s" % (request_data, nf_id))
        self._trigger_service_event(context, 'SERVICE', 'SERVICE_CREATED',
                                    request_data)

    def firewall_deleted(self, context, notification_data):
        notification = notification_data['notification'][0]
        notification_info = notification_data['info']
        resource_data = notification['data']
        firewall_id = resource_data['firewall_id']
        nf_id = notification_info['context']['network_function_id']
        fw_mac = notification_info['context']['fw_mac']
        service_type = notification_info['service_type']

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
                                                  fw_mac, service_type)
        LOG(LOGGER, 'INFO', "%s : %s " % (request_data, nf_id))
        self._trigger_service_event(context, 'SERVICE', 'SERVICE_DELETED',
                                    request_data)
