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

from gbpservice.nfp.core.event import Event
from gbpservice.nfp.config_orchestrator.uservices.visibility import (
    visibility)

def event_init(sc, conf):
    evs = [
        Event(id='VISIBILITY_EVENT',
              handler=visibility.VisibilityEventsHandler(sc, conf)),
        Event(id='SET_FIREWALL_STATUS',
              handler=visibility.VisibilityEventsHandler(sc, conf)),
        Event(id='FIREWALL_DELETED',
              handler=visibility.VisibilityEventsHandler(sc, conf)),
        Event(id='VIP_DELETED',
              handler=visibility.VisibilityEventsHandler(sc, conf)),
        Event(id='UPDATE_STATUS',
              handler=visibility.VisibilityEventsHandler(sc, conf)),
        Event(id='IPSEC_SITE_CONN_DELETED',
              handler=visibility.VisibilityEventsHandler(sc, conf)),
        Event(id='SERVICE_OPERATION_POLL_EVENT',
              handler=visibility.VisibilityEventsHandler(sc, conf)),
        Event(id='SERVICE_CREATED',
              handler=visibility.VisibilityEventsHandler(sc, conf)),
        Event(id='SERVICE_DELETED',
              handler=visibility.VisibilityEventsHandler(sc, conf)),
        Event(id='SERVICE_CREATE_PENDING',
              handler=visibility.VisibilityEventsHandler(sc, conf))]
    return evs


class VisibilityNotificationHandler(object):

    def __init__(self, conf, sc):
        self.conf = conf
        self.sc = sc

    def handle_notification(context, notification_data):
        # Handle Event
        request_data = {'context': context,
                        'notification_data': notification_data
                        }
        event = self.sc.new_event(id='VISIBILITY_EVENT',
                                  key='VISIBILITY_EVENT',
                                  data=request_data)
