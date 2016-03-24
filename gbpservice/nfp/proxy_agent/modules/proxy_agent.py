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

from gbpservice.nfp.core.rpc import RpcAgent
from gbpservice.nfp.lib import log_wrapper as wp
from gbpservice.nfp.proxy_agent.lib import RestClientOverUnix as rc
from gbpservice.nfp.proxy_agent.lib import topics
import json
from oslo_log import log as logging

LOG = logging.getLogger(__name__)
log_info = wp.log_info
log_error = wp.log_error


def rpc_init(config, sc):
    rpcmgr = RpcHandler(config, sc)
    agent = RpcAgent(
        sc,
        host=config.host,
        topic=topics.CONFIG_AGENT_PROXY,
        manager=rpcmgr)
    sc.register_rpc_agents([agent])


def module_init(sc, conf):
    rpc_init(conf, sc)


class RpcHandler(object):
    RPC_API_VERSION = '1.0'

    def __init__(self, conf, sc):
        super(RpcHandler, self).__init__()
        self._conf = conf
        self._sc = sc

    # firewall/lb RPC's
    def create_network_function_config(self, context, body):
        try:
            resp, content = rc.post(
                'create_network_function_config', body=body)
            log_info(LOG,
                "create_network_function_config -> POST \
response: (%s)" % (content))

        except rc.RestClientException as rce:
            log_error(LOG, "create_firewall -> POST \
request failed.Reason: %s" % (rce))

    def delete_network_function_config(self, context, body):
        try:
            resp, content = rc.post('delete_network_function_config',
                                    body=body, delete=True)
            log_info(LOG,
                "delete_network_function_config -> POST \
response: (%s)" % (content))

        except rc.RestClientException as rce:
            log_error(LOG, "delete_firewall -> DELETE request \
failed.Reason: %s" % (rce))

    # generic RPC
    def create_network_function_device_config(self, context, body):
        try:
            log_info(LOG, "%s:%s" % (context, body))
            resp, content = rc.post('create_network_function_device_config',
                                    body=body)
            log_info(LOG,
                "create_network_function_device_config -> POST \
response: (%s)" % (content))

        except rc.RestClientException as rce:
            log_error(LOG, "create_network_function_device_config -> \
request failed.Reason %s " % (rce))

    def delete_network_function_device_config(self, context, body):
        try:
            log_info(LOG, "%s:%s" % (context, body))
            resp, content = rc.post('delete_network_function_device_config',
                                    body=body, delete=True)
            log_info(LOG,
                "delete_network_function_device_config -> POST \
response: (%s)" % (content))

        except rc.RestClientException as rce:
            log_error(LOG,
                "delete_network_function_device_config -> request failed\
.Reason %s " % (rce))

    # Notification RPC by call() method
    def get_notifications(self, context):
        try:
            resp, content = rc.get('get_notifications')
            content = json.loads(content)
            log_info(LOG, "get_notification -> GET response: (%s)" % (content))
            return content
        except rc.RestClientException as rce:
            log_error(LOG, "get_notification -> GET request failed. Reason \
: %s" % (rce))
            return "get_notification -> GET request failed. Reason : %s" % (
                rce)
