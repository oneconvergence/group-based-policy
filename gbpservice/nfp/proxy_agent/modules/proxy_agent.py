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
import os
import sys
import ast
import json
import time

from oslo_log import log as logging
import oslo_messaging as messaging
from gbpservice.nfp.core.main import Controller
from gbpservice.nfp.core.main import Event
from gbpservice.nfp.core.rpc import RpcAgent

from neutron.common import rpc as n_rpc
from neutron import context as n_context

from gbpservice.nfp.proxy_agent.lib import topics
from gbpservice.nfp.proxy_agent.lib import RestClientOverUnix as rc

from neutron import context as ctx


LOG = logging.getLogger(__name__)


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
            LOG.info(
                "create_network_function_config -> POST response: (%s)" % (content))

        except rc.RestClientException as rce:
            LOG.error("create_firewall -> POST request failed.Reason: %s" % (
                rce))

    def delete_network_function_config(self, context, body):
        try:
            resp, content = rc.post('delete_network_function_config',
                                    body=body, delete=True)
            LOG.info(
                "delete_network_function_config -> POST response: (%s)" % (content))

        except rc.RestClientException as rce:
            LOG.error("delete_firewall -> DELETE request failed.Reason: %s" % (
                rce))

    # generic RPC
    def create_network_function_device_config(self, context, body):
        try:
            LOG.info("%s:%s" % (context, body))
            resp, content = rc.post('create_network_function_device_config',
                                    body=body)
            LOG.info(
                "create_network_function_device_config -> POST response: (%s)" % (content))

        except rc.RestClientException as rce:
            LOG.error("create_network_function_device_config -> request failed\
.Reason %s " % (rce))

    def delete_network_function_device_config(self, context, body):
        try:
            LOG.info("%s:%s" % (context, body))
            resp, content = rc.post('delete_network_function_device_config',
                                    body=body, delete=True)
            LOG.info(
                "delete_network_function_device_config -> POST response: (%s)" % (content))

        except rc.RestClientException as rce:
            LOG.error(
                "delete_network_function_device_config -> request failed\
.Reason %s " % (rce))

    # Notification RPC by call() method
    def get_notifications(self, context):
        try:
            resp, content = rc.get('get_notifications')
            content = json.loads(content)
            LOG.info("get_notification -> GET response: (%s)" % (content))
            return content
        except rc.RestClientException as rce:
            LOG.error("get_notification -> GET request failed. Reason : %s" % (
                rce))
            return "get_notification -> GET request failed. Reason : %s" % (
                rce)
