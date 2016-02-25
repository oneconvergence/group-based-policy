#  Licensed under the Apache License, Version 2.0 (the "License"); you may
#  not use this file except in compliance with the License. You may obtain
#  a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License.from gbpservice.neutron.nsf.core import main

from gbpservice.nfp.core import main
from gbpservice.nfp.core import poll
import os
from oslo_log import log as logging
import time
LOG = logging.getLogger(__name__)


class Handler_Class(poll.PollEventDesc):

    def __init__(self, sc):
        self._sc = sc
        self.counter = 0
        self.timer = 0

    def handle_poll_event(self, ev):
        if ev.id == 'DUMMY_SERVICE_EVENT7':
            sequenscer_map = self._sc._sequencer.copy()
            if ev.worker_attached in sequenscer_map:
                seq_map_worker = sequenscer_map[ev.worker_attached]
                if ev.binding_key in seq_map_worker:
                    qu = seq_map_worker[ev.binding_key]['queue']
                    for event in qu:
                        print (event.id)
                        if event.id == 'DUMMY_SERVICE_EVENT8':
                            self._sc._event.set()

        if os.getpid() == ev.worker_attached and \
                ev.id == 'DUMMY_SERVICE_EVENT2' and self.counter == 0:
            self._sc._event.set()
        if ev.id == 'DUMMY_SERVICE_EVENT3':
            self.counter = self.counter + 1
        if ev.id == 'DUMMY_SERVICE_EVENT4':
            self.counter = self.counter + 1
            if self.counter == 2:
                self._sc._event.set()
        LOG.debug("Poll event (%s)" % (str(ev)))
        print("Poll event %s", (ev.key))

    def handle_event(self, ev):
        LOG.debug("Process ID :%d" % (os.getpid()))
        if ev.id == 'DUMMY_SERVICE_EVENT1':
            self._handle_dummy_event1(ev)
        elif ev.id == 'DUMMY_SERVICE_EVENT2':
            self._handle_dummy_event2(ev)
        elif ev.id == 'DUMMY_SERVICE_EVENT3':
            self._handle_dummy_event3(ev)
        elif ev.id == 'DUMMY_SERVICE_EVENT4':
            self._handle_dummy_event4(ev)
        elif ev.id == 'DUMMY_SERVICE_EVENT5':
            self._handle_dummy_event5(ev)
        elif ev.id == 'DUMMY_SERVICE_EVENT6':
            self._handle_dummy_event6(ev)
        elif ev.id == 'DUMMY_SERVICE_EVENT7':
            self._handle_dummy_event7(ev)
        elif ev.id == 'DUMMY_SERVICE_EVENT8':
            self._handle_dummy_event8(ev)
        elif ev.id == 'DUMMY_SERVICE_EVENT9':
            self._handle_dummy_event9(ev)

    def _handle_dummy_event6(self, ev):
        self._sc.event_done(ev)
        self._sc.poll_event(ev, max_times=2)

    def _handle_dummy_event5(self, ev):
        self._sc.event_done(ev)
        self._sc.poll_event(ev, max_times=2)

    def _handle_dummy_event4(self, ev):
        self._sc.poll_event(ev, max_times=1)

    def _handle_dummy_event3(self, ev):
        self._sc.poll_event(ev, max_times=2)

    def _handle_dummy_event1(self, ev):
        if os.getpid() == ev.worker_attached:
            self._sc._event.set()
        self._sc.event_done(ev)

    def _handle_dummy_event2(self, ev):
        self._sc.event_done(ev)
        self._sc.poll_event(ev, max_times=1)

    def _handle_dummy_event7(self, ev):
        sequenscer_map = self._sc._sequencer.copy()
        print(sequenscer_map)
        # self._sc.event_done(ev)
        self._sc.poll_event(ev, max_times=2)

    def _handle_dummy_event8(self, ev):
        print("%s event handle called", (ev.key))
        if ev.id == 'DUMMY_SERVICE_EVENT8':
            self._sc._event.set()

    def _handle_dummy_event9(self, ev):
        print("Calling Event done %s", (ev.key))
        self._sc.event_done(ev)

    def poll_event_cancel(self, ev):
        if os.getpid() == ev.worker_attached and self.counter == 2:
            self._sc._event.set()
        LOG.debug("Poll event Canceled counter(%s)" % (str(ev)))

    @poll.poll_event_desc(event='DUMMY_SERVICE_EVENT5', spacing=10)
    def dummy_event5_poll_event(self, ev):
        if self.counter == 0:
            self.timer = time.time()
            self.counter = self.counter + 1
        else:
            time_now = time.time()
            time_elapsed = int(round(time_now - self.timer))
            if ev.id == 'DUMMY_SERVICE_EVENT5' and time_elapsed == 10:
                self._sc._event.set()
        LOG.debug("Poll event (%s)" % (str(ev)))
        print ("Decorator Poll event %s", (ev.key))

    @poll.poll_event_desc(event='DUMMY_SERVICE_EVENT6', spacing=20)
    def dummy_event6_poll_event(self, ev):
        if self.counter == 0:
            self.timer = time.time()
            self.counter = self.counter + 1
        else:
            time_now = time.time()
            time_elapsed = int(round(time_now - self.timer))
            if ev.id == 'DUMMY_SERVICE_EVENT6' and time_elapsed == 20:
                self._sc._event.set()
        LOG.debug("Poll event (%s)" % (str(ev)))
        print ("Decorator Poll event %s", (ev.key))


def module_init(sc, conf):
    evs = [
        main.Event(id='DUMMY_SERVICE_EVENT1', handler=Handler_Class(sc)),
        main.Event(id='DUMMY_SERVICE_EVENT2', handler=Handler_Class(sc)),
        main.Event(id='DUMMY_SERVICE_EVENT3', handler=Handler_Class(sc)),
        main.Event(id='DUMMY_SERVICE_EVENT4', handler=Handler_Class(sc)),
        main.Event(id='DUMMY_SERVICE_EVENT5', handler=Handler_Class(sc)),
        main.Event(id='DUMMY_SERVICE_EVENT6', handler=Handler_Class(sc)),
        main.Event(id='DUMMY_SERVICE_EVENT7', handler=Handler_Class(sc)),
        main.Event(id='DUMMY_SERVICE_EVENT8', handler=Handler_Class(sc)),
        main.Event(id='DUMMY_SERVICE_EVENT9', handler=Handler_Class(sc))
    ]
    sc.register_events(evs)
