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
from gbpservice.nfp.proxy_agent.lib import topics
from neutron_fwaas.db.firewall import firewall_db
from neutron import context as n_context
from oslo_log import helpers as log_helpers
from oslo_log import log
import oslo_messaging as messaging
from oslo_messaging import target

LOG = log.getLogger(__name__)

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

    @log_helpers.log_method_call
    def create_firewall(self, context, firewall, host):

        # Collecting db entry required by configurator.
        db = self._context(context, firewall['tenant_id'])
        # Addind service_info to neutron context and sending
        # dictionary format to the configurator.
        context_dict = context.to_dict()
        context_dict.update({'service_info': db})
        resource = 'firewall'
        kwargs = {resource: firewall,
                  'host': host,
                  'context': context_dict}
        body = common. prepare_request_data(resource,
                                            kwargs,
                                            "firewall")
        transport.send_request_to_configurator(self._conf,
                                               context, body,
                                               "CREATE")

    @log_helpers.log_method_call
    def delete_firewall(self, context, firewall, host):

        # Collecting db entry required by configurator.
        db = self._context(context, firewall['tenant_id'])
        # Addind service_info to neutron context and sending
        # dictionary format to the configurator.
        context_dict = context.to_dict()
        context_dict.update({'service_info': db})
        resource = 'firewall'
        kwargs = {resource: firewall,
                  'host': host,
                  'context': context_dict}
        body = common.prepare_request_data(resource,
                                           kwargs,
                                           "firewall")
        transport.send_request_to_configurator(self._conf,
                                               context, body,
                                               "DELETE")

    def _context(self, context, tenant_id):
        if context.is_admin:
            tenant_id = context.tenant_id
        filters = {'tenant_id': [tenant_id]}
        db = self._get_firewall_context(context, filters)
        db.update(self._get_core_context(context, filters))
        return db

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

    def firewall_configuration_create_complete(self, context, **kwargs):
        kwargs = kwargs['kwargs']
        rpcClient = transport.RPCClient(topics.FW_NFP_PLUGIN_TOPIC)
        firewall_id = kwargs['firewall_id']
        # firewall = kwargs['firewall']     # kwargs contains whole firewall
                                            # object under key firewall
        status = kwargs['status']
        msg = ("Config Orchestrator received "
                "firewall_configuration_create_complete API, making an "
                "set_firewall_status RPC call for firewall: %s & status "
                " %s" % (firewall_id, status))
        LOG.info(msg)
        # RPC call to plugin to set firewall status
        rpcClient.cctxt.cast(context, 'set_firewall_status',
                             host=kwargs['host'],
                             firewall_id=firewall_id,
                             status=status)

    def firewall_configuration_delete_complete(self, context, **kwargs):
        kwargs = kwargs['kwargs']
        rpcClient = transport.RPCClient(topics.FW_NFP_PLUGIN_TOPIC)
        firewall_id = kwargs['firewall_id']
        # firewall = kwargs['firewall']     # kwargs contains whole firewall
                                            # object under key firewall
        msg = ("Config Orchestrator received "
                "firewall_configuration_delete_complete API, making an "
                "firewall_deleted RPC call for firewall: %s" % (firewall_id))
        LOG.info(msg)
        # RPC call to plugin to update firewall deleted
        rpcClient.cctxt.cast(context, 'firewall_deleted',
                             host=kwargs['host'],
                             firewall_id=firewall_id)

class FwPluginApi(object):

    RPC_API_VERSION = '1.0'
    target = messaging.Target(version=RPC_API_VERSION)

    def __init__(self, conf, sc):
        print 'FwPluginApi'
        self._conf = conf
        self._sc = sc

    def firewall_configuration_create_complete(self, context, **kwargs):
        kwargs = kwargs['kwargs']
        rpcClient = transport.RPCClient(topics.FW_NFP_PLUGIN_TOPIC)
        firewall_id = kwargs['firewall_id']
        status = kwargs['status']
        rpcClient.cctxt.cast(context, 'set_firewall_status',
                             host=kwargs['host'],
                             firewall_id=firewall_id,
                             status=status)

    def firewall_configuration_delete_complete(self, context, **kwargs):
        kwargs = kwargs['kwargs']
        rpcClient = transport.RPCClient(topics.FW_NFP_PLUGIN_TOPIC)
        firewall_id = kwargs['firewall_id']
        rpcClient.cctxt.cast(context, 'firewall_deleted',
                             host=kwargs['host'],
                             firewall_id=firewall_id)
