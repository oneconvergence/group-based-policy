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

from gbpservice.nfp.core import common as core_common
from gbpservice.nfp.core import poll as core_pt
import gbpservice.nfp.lib.transport as transport
from gbpservice.nfp.proxy_agent.notifications import handler as nh

from oslo_log import log as logging

log_info = core_common.log_info
log_error = core_common.log_error

LOG = logging.getLogger(__name__)


class PullNotification(core_pt.PollEventDesc):

    def __init__(self, sc, conf):
        self._sc = sc
        self._conf = conf

    def handle_event(self, ev):
        self._sc.poll_event(ev)

    def _method_handler(self, notification):
        mod = nh.NotificationHandler()
        mod_method = getattr(mod, notification['method'])
        reciever = notification['receiver']
        if reciever == 'device_orchestrator' or reciever == 'orchestrator':
            mod_method(notification['resource'],
                       notification['kwargs'])

        elif reciever == 'service_orchestrator':
            mod_method(notification['resource'],
                       notification['kwargs'],
                       device=False)
        else:
            mod_method(notification['resource'], **notification['kwargs'])

    @core_pt.poll_event_desc(event='PULL_NOTIFICATIONS', spacing=1)
    def pull_notifications(self, ev):
        notifications = transport.get_response_from_configurator(self._conf)
        '''
        response_data = [
            {'receiver': <neutron/device_orchestrator/service_orchestrator>,
             'resource': <firewall/vpn/loadbalancer/orchestrator>,
             'method': <notification method name>,
             'kwargs': <notification method arguments>
        },
        ]
        '''
        if not isinstance(notifications, list):
            log_error(LOG, "Notfications not list, %s" % (notifications))

        else:
            for notification in notifications:
                if not notification:
                    log_info(LOG, "Receiver Response: Empty")
                    continue
                try:
                    self._method_handler(notification)
                except AttributeError:
                    log_error(LOG, "AttributeError while handling message" % (
                        notification))
                except Exception as e:
                    log_error(LOG, "Generic exception (%s) \
                       while handling message (%s)" % (e, notification))
