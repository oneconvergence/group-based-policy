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
from gbpservice.nfp.config_orchestrator.agent.firewall\
    import FirewallNotifier
from gbpservice.nfp.config_orchestrator.agent.loadbalancer\
    import LoadbalancerNotifier
from gbpservice.nfp.config_orchestrator.agent.loadbalancerv2\
    import LoadbalancerV2Notifier
from gbpservice.nfp.config_orchestrator.agent.vpn import VpnNotifier
from gbpservice.nfp.core import common as nfp_common

from oslo_log import log as oslo_logging
import oslo_messaging as messaging

import sys
import traceback

LOGGER = oslo_logging.getLogger(__name__)
LOG = nfp_common.log

ServicetypeToHandlerMap = {'firewall': FirewallNotifier,
                           'loadbalancer': LoadbalancerNotifier,
                           'loadbalancerv2': LoadbalancerV2Notifier,
                           'vpn': VpnNotifier}


class NotificationAgent(object):
    RPC_API_VERSION = '1.0'
    target = messaging.Target(version=RPC_API_VERSION)

    def __init__(self, conf, sc):
        super(NotificationAgent, self).__init__()
        self._conf = conf
        self._sc = sc

    def network_function_notification(self, context, notification_data):
        try:
            resource_data = notification_data['notification'][0]['data']
            handler = ServicetypeToHandlerMap[notification_data[
                'info']['service_type']](self._conf, self._sc)
            method = getattr(handler, resource_data['notification_type'])
            # Need to decide on the name of the key
            method(context, notification_data)

        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            LOG(LOGGER, 'ERROR',
                "Generic exception (%s) while handling message (%s) : %s" % (
                    e,
                    notification_data,
                    traceback.format_exception(
                        exc_type, exc_value,
                        exc_traceback)))
