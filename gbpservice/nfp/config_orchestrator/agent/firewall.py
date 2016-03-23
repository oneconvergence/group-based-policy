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

from neutron_fwaas.db.firewall import firewall_db
from gbpservice.nfp.config_orchestrator.agent.common import *
from gbpservice.nfp.config_orchestrator.agent import topics as a_topics
from neutron import context as n_context
from gbpservice.nfp.lib.transport import *

LOG = logging.getLogger(__name__)


def set_firewall_status(**kwargs):
    rpcClient = RPCClient(a_topics.FW_NFP_PLUGIN_TOPIC)
    context = kwargs.get('context')
    rpc_ctx = n_context.Context.from_dict(context)
    del kwargs['context']
    rpcClient.cctxt.cast(rpc_ctx, 'set_firewall_status',
                         host=kwargs['host'],
                         firewall_id=kwargs['firewall_id'],
                         status=kwargs['status'])


def firewall_deleted(**kwargs):
    rpcClient = RPCClient(a_topics.FW_NFP_PLUGIN_TOPIC)
    context = kwargs.get('context')
    rpc_ctx = n_context.Context.from_dict(context)
    del kwargs['context']
    rpcClient.cctxt.cast(rpc_ctx, 'firewall_deleted',
                         host=kwargs['host'],
                         firewall_id=kwargs['firewall_id'])


class FwAgent(firewall_db.Firewall_db_mixin):

    RPC_API_VERSION = '1.0'
    _target = target.Target(version=RPC_API_VERSION)

    def __init__(self, conf, sc):
        self._conf = conf
        self._sc = sc
        super(FwAgent, self).__init__()

    def create_firewall(self, context, firewall, host):

        db = self._context(context, firewall['tenant_id'])
        context_dict = context.to_dict()
        context_dict.update({'service_info': db})
        resource = 'firewall'
        kwargs = {resource: firewall,
                  'host': host,
                  'context': context_dict}
        body = prepare_request_data(resource, kwargs, "firewall")
        send_request_to_configurator(self._conf, context, body, "CREATE")

    def delete_firewall(self, context, firewall, host):
        db = self._context(context, firewall['tenant_id'])
        context_dict = context.to_dict()
        context_dict.update({'service_info': db})
        resource = 'firewall'
        kwargs = {resource: firewall, 'host': host, 'context': context_dict}
        body = prepare_request_data(resource, kwargs, "firewall")
        send_request_to_configurator(self._conf, context, body, "DELETE")

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
        return get_core_context(context, filters, self._conf.host)
