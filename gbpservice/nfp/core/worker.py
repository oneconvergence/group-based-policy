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
import time

from oslo_log import log as oslo_logging
from oslo_service import service as oslo_service

from gbpservice.nfp.core import common as nfp_common
from gbpservice.nfp.core import event as nfp_event

LOGGER = oslo_logging.getLogger(__name__)
LOG = nfp_common.log
Service = oslo_service.Service
identify = nfp_common.identify

"""Implements worker process.

    Derives from oslo service.
    Implements the worker functionality.
    Waits for the events from distributor, handles them,
    invokes the registered event handler in a thread.
"""


class NfpWorker(Service):

    def __init__(self, conf, threads=10):
        # REVISIT(MAK): Can threads be configured ?
        Service.__init__(self, threads=threads)
        # Parent end of duplex pipe
        self.parent_pipe = None
        # Pipe to recv/send messages to distributor
        self.pipe = None
        # Cache of event handlers
        self.controller = None
        self._conf = conf
        self._threads = threads

    def start(self):
        """Service start, runs here till dies.

            When a oslo service is launched, this method
            is invoked.
            Polls for messages from distributor and process
            them.
        """
        # Update the process type in controller.
        self.controller.PROCESS_TYPE = "worker"
        self.controller._pipe = self.pipe
        self.event_handlers = self.controller.get_event_handlers()
        while True:
            try:
                event = None
                if self.pipe.poll():
                    event = self.pipe.recv()
                if event:
                    LOG(LOGGER, 'DEBUG', "%s - received event" %
                        (self._log_meta(event)))
                    self._process_event(event)
            except Exception as e:
                LOG(LOGGER, 'ERROR', "Exception - %s" % (e))
            # Yeild cpu
            time.sleep(0)

    def _log_meta(self, event=None):
        if event:
            return "(event - %s) - (worker - %d)" % (
                event.identify(), os.getpid())
        else:
            return "(worker - %d)" % (os.getpid())

    def _send_event_ack(self, event):
        # Create new event from existing one
        ack_event = nfp_event.Event()
        ack_event.id = event.id
        desc = nfp_event.EventDesc(**event.desc.__dict__)
        desc.uuid = event.desc.uuid
        desc.flag = nfp_event.EVENT_ACK
        setattr(ack_event, 'desc', desc)
        self.pipe.send(ack_event)

    def _process_event(self, event):
        """Process & dispatch the event.

            Decodes the event type and performs the required
            action.
            Executes the registered event handler in one of the
            thread.
        """
        if event.desc.type == nfp_event.SCHEDULE_EVENT:
            self._send_event_ack(event)
            eh = self.event_handlers.get_event_handler(event.id)
            self.dispatch(eh.handle_event, event)
        elif event.desc.type == nfp_event.POLL_EVENT:
            self.dispatch(self._handle_poll_event, event)
        elif event.desc.type == nfp_event.EVENT_EXPIRED:
            eh = self.event_handlers.get_event_handler(event.id)
            self.dispatch(eh.event_cancelled, event, 'EXPIRED')

    def _build_poll_status(self, ret, event):
        status = {'poll': True, 'event': event}
        if ret:
            status['poll'] = ret.get('poll', status['poll'])
            status['event'] = ret.get('event', status['event'])
            status['event'].desc = event.desc

        return status

    def _repoll(self, ret, event, eh):
        status = self._build_poll_status(ret, event)
        if status['poll']:
            if event.desc.poll_desc.max_times:
                self.pipe.send(status['event'])
            else:
                eh.event_cancelled(event, 'MAX_TIMED_OUT')

    def _handle_poll_event(self, event):
        ret = {}
        event.desc.poll_desc.max_times -= 1
        poll_handler = self.event_handlers.get_poll_handler(event.id)
        event_handler = self.event_handlers.get_event_handler(event.id)
        try:
            ret = poll_handler(event)
        except TypeError:
            ret = poll_handler(event_handler, event)
        self._repoll(ret, event, event_handler)

    def dispatch(self, handler, *args):
        if self._threads:
            th = self.tg.add_thread(handler, *args)
            LOG(LOGGER, 'DEBUG', "%s - (handler - %s) - "
                "dispatched to thread %d" %
                (self._log_meta(), identify(handler), th.ident))
        else:
            handler(*args)
            LOG(LOGGER, 'DEBUG', "%s - (handler - %s) - invoked" %
                (self._log_meta(), identify(handler)))
