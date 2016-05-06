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

from gbpservice.nfp.core import common as nfp_common
from gbpservice.nfp.core import poll as core_pt
import gbpservice.nfp.lib.transport as transport

from oslo_log import log as oslo_logging


LOGGER = oslo_logging.getLogger(__name__)
LOG = nfp_common.log

"""Periodic Class to service events for visiblity."""


class OTCServiceEventsHandler(core_pt.PollEventDesc):

    def __init__(self, sc, conf):
        self._sc = sc
        self._conf = conf

    def handle_event(self, ev):
        if ev.id == 'SERVICE_CREATED':
            data = ev.data
            self._create_service(data['context'],
                                 data['resource'])

        elif ev.id == 'SERVICE_DELETED':
            data = ev.data
            self._delete_service(data['context'],
                                 data['resource'])

    def _create_service(self, context, resource):
        transport.send_request_to_configurator(self._conf,
                                               context, resource,
                                               "CREATE",
                                               network_function_event=True)

    def _delete_service(self, context, resource):
        transport.send_request_to_configurator(self._conf,
                                               context, resource,
                                               "DELETE",
                                               network_function_event=True)
