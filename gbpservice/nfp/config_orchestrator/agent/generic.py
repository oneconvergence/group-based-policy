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
from gbpservice.nfp.config_orchestrator.agent import topics as a_topics
from gbpservice.nfp.config_orchestrator.agent.common import *
from gbpservice.nfp.lib.transport import *
LOG = logging.getLogger(__name__)


def network_function_device_notification(resource, kwargs_list):
    context = get_dummy_context()
    rpcClient = RPCClient(a_topics.GC_NFP_PLUGIN_TOPIC)
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
