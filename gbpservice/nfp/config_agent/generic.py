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

from gbpservice.nfp.config_agent.common import *
from gbpservice.nfp.config_agent import RestClientOverUnix as rc
from gbpservice.nfp.core import poll as core_pt
LOG = logging.getLogger(__name__)


def network_function_device_notification(resource, kwargs_list, sc):
    notification_data = {}
    notification_data.\
        update({'resource': resource,
                'kwargs': kwargs_list})
    data = notification_data
    ev = sc.new_event(id='NF_DEVICE_NOTIFICATION',
                      data=data,
                      key='NF_DEVICE_NOTIFICATION')
    sc.post_event(ev)


class GcAgent(core_pt.PollEventDesc):

    def __init__(self, sc):
        self._sc = sc

    def handle_event(self, ev):
        data = ev.data
        if ev.id == 'NF_DEVICE_CONFIG_CREATE':
            self.create_network_function_device_config(
                data['context'], data['request_data'])
        elif ev.id == 'NF_DEVICE_CONFIG_DELETE':
            self.delete_network_function_device_config(
                data['context'], data['request_data'])

    def create_network_function_device_config(self, context, request_data):
        for ele in request_data['config']:
            ele['kwargs'].update({'context': context.to_dict()})
        rpcClient = RPCClient(topics.CONFIG_AGENT_PROXY)
        rpcClient.cctxt.cast(context,
                             'create_network_function_device_config',
                             body=request_data)

    def delete_network_function_device_config(self, context, request_data):
        for ele in request_data['config']:
            ele['kwargs'].update({'context': context.to_dict()})
        rpcClient = RPCClient(topics.CONFIG_AGENT_PROXY)
        rpcClient.cctxt.cast(context,
                             'delete_network_function_device_config',
                             body=request_data)
