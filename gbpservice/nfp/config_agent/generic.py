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

from neutron import context as n_context

from gbpservice.nfp.config_agent.common import *
from gbpservice.nfp.config_agent import RestClientOverUnix as rc

LOG = logging.getLogger(__name__)


def network_function_device_notification(resource, kwargs_list):
    context={u'read_only': False, u'domain': None, u'project_name': None, u'user_id': None, u'show_deleted': False, u'roles': [], u'user_identity': u'', u'project_domain': None, u'tenant_name': None, u'auth_token': None, u'resource_uuid': None, u'project_id': None, u'tenant_id': None, u'is_admin': True, u'user': None, u'request_id': u'', u'user_domain': None, u'timestamp': u'', u'tenant': None, u'user_name': None}

    rpcClient = RPCClient(topics.GC_NFP_PLUGIN_TOPIC)
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


class GcAgent(object):
    RPC_API_VERSION = '1.0'
    _target = target.Target(version=RPC_API_VERSION)

    def __init__(self, conf, sc):
        self._conf = conf
        self._sc = sc
        super(GcAgent, self).__init__()

    def _post(self, context, request_data):
        for ele in request_data['config']:
            ele['kwargs'].update({'context': context.to_dict()})
        try:
            resp, content = rc.post('create_network_function_device_config',
                                    body=request_data)
        except rc.RestClientException as rce:
            LOG.error("create_network_function_device_config -> request failed\
.Reason %s " % (rce))

    def _delete(self, context, request_data):
        for ele in request_data['config']:
            ele['kwargs'].update({'context': context.to_dict()})
        try:
            resp, content = rc.post('delete_network_function_device_config',
                                    body=request_data, delete=True)
        except rc.RestClientException as rce:
            LOG.error(
                "delete_network_function_device_config -> request failed\
.Reason %s " % (rce))

    def create_network_function_device_config(self, context, request_data):
        self._post(context, request_data)

    def delete_network_function_device_config(self, context, request_data):
        self._delete(context, request_data)
