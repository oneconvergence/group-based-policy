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
import Queue
import time

from oslo_log import log as oslo_logging

from gbpservice.nfp.core import common as nfp_common
from gbpservice.nfp.core import threadpool as nfp_tp

LOG = oslo_logging.getLogger(__name__)
PID = os.getpid()
identify = nfp_common.identify
log_info = nfp_common.log_info
log_debug = nfp_common.log_debug

"""Definition of an 'EVENT' in NFP framework.

    NFP modules instantiates object of this class to define and
    create internal events.
"""


class Event(object):

    def __init__(self, **kwargs):
        self.serialize = kwargs.get(
            'serialize') if 'serialize' in kwargs else False
        self.binding_key = kwargs.get(
            'binding_key') if 'binding_key' in kwargs else None
        self.id = kwargs.get('id')
        self.key = kwargs.get('key')
        self.data = kwargs.get('data') if 'data' in kwargs else None
        self.handler = kwargs.get('handler') if 'handler' in kwargs else None
        self.lifetime = kwargs.get('lifetime') if 'lifetime' in kwargs else 0
        self.poll_event = None  # Not to be used by user
        self.worker_attached = None  # Not to be used by user
        self.last_run = None  # Not to be used by user
        self.max_times = -1  # Not to be used by user

    def identify(self):
        return "(id=%s,key=%s)" % (self.id, self.key)

"""Handles the sequencing of related events.

    If Event needs to be sequenced it is queued otherwise
    it is scheduled. Caller will fetch the sequenced events
    waiting to be scheduled in subsequent calls.
"""


class EventSequencer(object):

    def __init__(self, sc):
        self._sc = sc
        """
        sequenced events are stored in following format :
        {'pid':{'binding_key':{'in_use':True, 'queue':[]}}}
        """
        self._sequencer_map = {}

    def get(self):
        """Get an event from the sequencer map.

            Invoked by workers to get the first event in sequencer map.
            Since it is a FIFO, first event could be waiting long to be
            scheduled.
            Loops over copy of sequencer map and returns the first waiting
            event.
        """
        event = None
        self._sc.lock()
        seq_map = self._sequencer_map
        for pid, seq in seq_map.iteritems():
            for bkey, val in seq.iteritems():
                if val['in_use']:
                    continue
                else:
                    if val['queue'] == []:
                        continue
                    event = val['queue'][0]
                    seq_map[pid][bkey]['in_use'] = True
                    log_info(LOG, "Returing serialized event %s"
                             % (event.identify()))
                    break
            if event:
                break
        self._sc.unlock()
        return event

    def add(self, ev):
        """Add the event to the sequencer.

            Checks if there is already a related event scheduled,
            if not, will not queue the event. If yes, then will
            queue this event.
            Returns True(queued)/False(not queued).
        """
        queued = False
        log_debug(LOG, "Sequence event %s" % (ev.identify()))
        self._sc.lock()
        if ev.worker_attached not in self._sequencer_map:
            self._sequencer_map[ev.worker_attached] = {}
        seq_map = self._sequencer_map[ev.worker_attached]
        if ev.binding_key in seq_map.keys():
            queued = True
            log_info(LOG,
                     "There is already an event in progress"
                     "Queueing event %s" % (ev.identify()))

            seq_map[ev.binding_key]['queue'].append(ev)
        else:
            log_info(LOG,
                     "Scheduling first event to exec"
                     "Event %s" % (ev.identify()))
            seq_map[ev.binding_key] = {'in_use': True, 'queue': [ev]}
        self._sc.unlock()
        return queued

    def copy(self):
        """Returns the copy of sequencer_map to caller. """
        self._sc.lock()
        copy = dict(self._sequencer_map)
        self._sc.unlock()
        return copy

    def remove(self, ev):
        """Removes an event from sequencer map.

            If this is the last related event in the map, then
            the complete entry is deleted from sequencer map.
        """
        self._sc.lock()
        self._sequencer_map[ev.worker_attached][
            ev.binding_key]['queue'].remove(ev)
        self._sequencer_map[ev.worker_attached][
            ev.binding_key]['in_use'] = False
        self._sc.unlock()

    def delete_eventmap(self, ev):
        """Internal method to delete event map, if it is empty. """
        self._sc.lock()
        seq_map = self._sequencer_map[ev.worker_attached][ev.binding_key]
        if seq_map['queue'] == []:
            log_info(LOG,
                     "No more events in the seq map -"
                     "Deleting the entry (%d) (%s)"
                     % (ev.worker_attached, ev.binding_key))
            del self._sequencer_map[ev.worker_attached][ev.binding_key]
        self._sc.unlock()

"""Handles the processing of evens in event queue.

    Executes in the context of worker process, runs in loop to fetch
    the events and process them. As processing, invokes the registered
    handler for the event.
"""


class EventQueueHandler(object):

    def __init__(self, sc, conf, qu, ehs):
        # Pool of green threads per process
        self._conf = conf
        self._tpool = nfp_tp.ThreadPool()
        self._evq = qu
        self._ehs = ehs
        self._sc = sc

    def _get(self):
        """Internal function to get an event for processing.

            First checks in sequencer map - these events could be
            waiting for long.
            If no events, then fetch the events from event_queue -
            listener process adds events into this queue.
            Returns the event to be processed.
        """
        # Check if any event can be pulled from serialize_map - this evs may be
        # waiting long enough
        log_debug(LOG, "Checking serialize Q for events long pending")
        ev = self._sc.sequencer_get_event()
        if not ev:
            log_debug(LOG,
                      "No event pending in sequencer Q - "
                      "checking the event Q")
            try:
                ev = self._evq.get(timeout=0.1)
            except Queue.Empty:
                pass
            if ev:
                log_debug(LOG,
                          "Checking if the ev %s to be serialized"
                          % (ev.identify()))
                """
                If this event needs to be serialized and is first event
                then the same is returned back, otherwise None is
                returned. If event need not be serialized then it is
                returned.
                """
                ev = self._sc.sequencer_put_event(ev)
        return ev

    def _dispatch_poll_event(self, eh, ev):
        """Internal function to handle the poll event.

            Poll task adds the timedout events to the worker process.
            This method handles such timedout events in worker context.
            Invoke the decorated timeout handler for the event, if any.
            (or) invoke the default 'handle_poll_event' method of registered
            handler.
            """
        log_debug(LOG,
                  "Event %s to be scheduled to handler %s"
                  % (ev.identify(), identify(eh)))

        t = self._tpool.dispatch(self._sc.poll_event_timedout, eh, ev)
        log_info(LOG,
                 "Invoking event_timedout method in thread %s"
                 % (t.identify()))

    def run(self, qu):
        """Worker process loop to fetch & process events from event queue.

            Gets the events from event queue which is
            python multiprocessing.queue.
            Listener process adds events into this queue for worker process
            to handle it.
            Handles 3 different type of events -
            a) POLL_EVENT - Event added by poller due to timeout.
            b) POLL_EVENT_CANCELLED - Event added by poller due to event
                getting cancelled as it timedout configured number of
                max times.
            c) EVENT - Internal event added by listener process.
        """
        log_info(LOG,
                 "Started worker process - %s" % (PID))
        while True:
            ev = self._get()
            if ev:
                log_debug(LOG,
                          "Got event %s" % (ev.identify()))
                eh = self._ehs.get(ev)
                if not ev.poll_event:
                    # Creating the Timer Poll Event
                    if ev.lifetime:
                        log_info(LOG, "Creating LIFE_TIMEOUT event (%s) "
                                 " for lifetime (%d)"
                                 % (ev.identify(), ev.lifetime))

                        # convert event lifetime in to polling time
                        max_times = int(
                            ev.lifetime / self._conf.periodic_interval)
                        if ev.lifetime % self._conf.periodic_interval:
                            max_times += 1

                        t_ev = self._sc.new_event(
                            id='EVENT_LIFE_TIMEOUT', data=ev,
                            binding_key=ev.binding_key, key=ev.key)
                        self._sc.poll_event(t_ev, max_times=max_times)

                    t = self._tpool.dispatch(eh.handle_event, ev)
                    log_debug(LOG, "Event %s is not poll event - "
                              "disptaching handle_event() of handler %s"
                              "to thread %s"
                              % (ev.identify(), identify(eh), t.identify()))
                else:
                    self._dispatch_poll_event(eh, ev)
                    log_info(LOG, "Got POLL Event %s scheduling"
                             % (ev.identify()))
            time.sleep(0)  # Yield the CPU
