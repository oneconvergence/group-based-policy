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
import random
import six
import time

from oslo_config import cfg as oslo_config
from oslo_log import log as oslo_logging
from oslo_service import loopingcall as oslo_looping_call
from oslo_service import periodic_task as oslo_periodic_task

from gbpservice.nfp.core import common as nfp_common
from gbpservice.nfp.core import fifo as nfp_fifo

LOG = oslo_logging.getLogger(__name__)
PID = os.getpid()
identify = nfp_common.identify
log_info = nfp_common.log_info
log_debug = nfp_common.log_debug
log_error = nfp_common.log_error


"""Decorator definition """


def poll_event_desc(*args, **kwargs):
    def decorator(f):
        f._desc = True
        f._spacing = kwargs.pop('spacing', 0)
        f._event = kwargs.pop('event', None)
        return f

    return decorator

"""Meta class. """


class _Meta(type):

    def __init__(cls, names, bases, dict_):
        """Metaclass that allows us to collect decorated periodic tasks."""
        super(_Meta, cls).__init__(names, bases, dict_)

        try:
            cls._poll_event_descs = dict(cls._poll_event_descs)
        except AttributeError:
            cls._poll_event_descs = {}

        for value in cls.__dict__.values():
            if getattr(value, '_desc', False):
                desc = value
                # name = desc.__name__
                cls._poll_event_descs[desc._event] = desc

"""Implements the logic to manage periodicity of events.
    Reference to corresponding decorated methods are returned
    if event has timedout.
"""


@six.add_metaclass(_Meta)
class PollEventDesc(object):

    def __init__(self):
        super(PollEventDesc, self).__init__()

    def _nearest_boundary(self, last_run, spacing):
        """Find nearest boundary which is in the past,
        which is a multiple of the
        spacing with the last run as an offset.

        Eg if last run was 10 and spacing was 7,
        the new last run could be: 17, 24,
        31, 38...

        0% to 5% of the spacing value will be added
        to this value to ensure tasks
        do not synchronize. This jitter is rounded
        to the nearest second, this
        means that spacings smaller than 20 seconds
        will not have jitter.
        """
        current_time = time.time()
        if last_run is None:
            return current_time
        delta = current_time - last_run
        offset = delta % spacing
        # Add up to 5% jitter
        jitter = int(spacing * (random.random() / 20))
        return current_time - offset + jitter

    def _timedout(self, desc, event):
        """Check if event timedout w.r.t its spacing. """
        spacing = desc._spacing
        last_run = event.last_run
        delta = 0

        if last_run:
            delta = last_run + spacing - time.time()
        if delta > 0:
            return None
        event.last_run = self._nearest_boundary(last_run, spacing)
        return event

    def check_timedout(self, event):
        """Check if event timedout w.r.t its spacing.

            First check if the spacing is set for this event, if
            not then return the event - in this case events timeout
            at the periodicity of polling task.
            If yes, then check if event timedout.
        """
        if event.id not in self._poll_event_descs.keys():
            return event
        else:
            desc = self._poll_event_descs[event.id]
            return self._timedout(desc, event)

    def get_poll_event_desc(self, event):
        """Get the registered event handler for the event.

            Check if the event has a specific periodic handler
            defined, if then return it.
        """
        if event.id not in self._poll_event_descs.keys():
            return None
        return self._poll_event_descs[event.id]


"""Periodic task to poll for nfp events.

    Derived from oslo periodic task, polls periodically for the
    NFP events, invokes registered event handler for the timedout
    event.
"""


class PollingTask(oslo_periodic_task.PeriodicTasks):

    def __init__(self, sc):
        super(PollingTask, self).__init__(oslo_config.CONF)
        self._sc = sc
        pulse = oslo_looping_call.FixedIntervalLoopingCall(
            self.run_periodic_tasks, None, None)
        pulse.start(
            interval=oslo_config.CONF.periodic_interval, initial_delay=None)

    @oslo_periodic_task.periodic_task(spacing=2)
    def periodic_sync_task(self, context):
        log_debug(LOG, "Periodic sync task invoked !")
        # invoke the common class to handle event timeouts
        self._sc.timeout()

"""Handles the polling queue, searches for the timedout events.

    Invoked in PollingTask, fetches new events from pollQ to cache them.
    Searches in cache for timedout events, enqueues timedout events to
    respective worker process. Event stays in cache till it is declared to
    be complete or cancelled.
    Event gets cancelled, if it is polled for max number of times. By default,
    it is huge number unless otherwise specified by logic which enqueues this
    event.
"""


class PollQueueHandler(object):

    def __init__(self, sc, qu, squ, ehs, batch=-1):
        self._sc = sc
        self._ehs = ehs
        self._pollq = qu
        self._stashq = squ
        self._procidx = 0
        self._procpending = 0
        self._batch = 10 if batch == -1 else batch
        self._cache = nfp_fifo.Fifo(sc)
        self._stash_cache = nfp_fifo.Fifo(sc)

    def _get(self):
        """Internal method to get messages from pollQ.

            Handles the empty queue exception.
        """
        try:
            return self._pollq.get(timeout=0.1)
        except Queue.Empty:
            return None

    def event_life_timedout(self, eh, event):
        try:
            eh.event_cancelled(event.data)
        except AttributeError:
            log_info(LOG,
                     "Handler %s does not implement"
                     "event_cancelled method" % (identify(eh)))

    def event_timedout(self, eh, event):
        if isinstance(eh, PollEventDesc):
            # Check if this event has a decorated timeout method
            peh = eh.get_poll_event_desc(event)
            if peh:
                ret = peh(eh, event)
                log_info(LOG,
                         "Invoking method %s of handler %s"
                         "for event %s "
                         % (identify(peh), identify(eh),
                            event.identify()))

            else:
                ret = eh.handle_poll_event(event)
                log_info(LOG,
                         "Invoking handle_poll_event() of handler %s"
                         "for event %s"
                         % (identify(eh),
                            event.identify()))
        else:
            ret = eh.handle_poll_event(event)
            log_info(LOG,
                     "Invoking handle_poll_event() of handler %s"
                     "for event %s "
                     % (identify(eh),
                        event.identify()))

        self._event_dispatched(eh, event, ret)

    def _poll_event_cancelled(self, eh, event):
        try:
            log_info(LOG,
                     "Event %s cancelled"
                     "invoking %s handler's poll_event_cancel method"
                     % (event.identify(), identify(eh)))
            return eh.poll_event_cancel(event)
        except AttributeError:
            log_info(LOG,
                     "Handler %s does not implement"
                     "poll_event_cancel method" % (identify(eh)))
        finally:
            return

    def _get_empty_status(self, event, ret):
        status = {'poll': True, 'event': event}
        if ret and 'event' in ret.keys():
            status['event'] = ret['event']
        if ret and 'poll' in ret.keys():
            status['poll'] = ret['poll']
        return status

    def _event_dispatched(self, eh, event, ret):
        status = self._get_empty_status(event, ret)
        uevent = status['event']
        poll = status['poll']

        uevent.max_times = event.max_times - 1

        if not uevent.max_times:
            return self._poll_event_cancelled(eh, event)

        if poll:
            uevent.serialize = False
            return self._sc.poll_event(uevent, max_times=uevent.max_times)

    def _schedule(self, ev):
        """Schedule the event to approp worker.

            Checks if the event has timedout and if yes,
            then schedules it to the approp worker. Approp worker -
            worker which handled this event earlier.
        """
        log_debug(LOG, "Schedule event %s" % (ev.identify()))
        eh = self._ehs.get(ev)
        """Check if the event has any defined spacing interval, if yes
            then did it timeout w.r.t the spacing ?
            If yes, then event is scheduled.
            Spacing for event can only be defined if the registered event
            handler is derived from periodic task class. Following check
            is for same.
        """
        if isinstance(eh, PollEventDesc):
            if eh.check_timedout(ev):
                log_info(LOG,
                         "Event %s timed out -"
                         "scheduling it to a worker" % (ev.identify()))
                self._sc.post_event(ev)
                return ev
        else:
            log_info(LOG,
                     "Event %s timed out -"
                     "scheduling it to a worker" % (ev.identify()))
            self._sc.post_event(ev)
            return ev
        return None

    def _scheduled(self, ev):
        """Marks the event as complete.

            Invoked by caller to mark the event as complete.
            Removes the event from internal cache.
        """
        self._cache.remove([ev])

    def _process_event(self, cache, ev):
        """Process different type of poll event. """

        log_debug(LOG, "Processing poll event %s" % (ev.identify()))
        if ev.id == 'POLL_EVENT_DONE':
            return self._scheduled(ev)

        if ev.id == 'EVENT_LIFE_TIMEOUT':
            ev.max_times -= 1
            if ev.max_times:
                return
        ev.poll_event = 'POLL_EVENT'
        ev.serialize  = False
        ev = self._schedule(ev)
        if ev:
            self._scheduled(ev)

    def add(self, event):
        """Adds an event to the pollq.

            Invoked in context of worker process
            to send event to polling task.
        """
        log_debug(LOG, "Add event %s to the pollq" % (event.identify()))
        self._pollq.put(event)

    def s_add(self, event):
        """Adds an event to the pollq.

            Invoked in context of worker process
            to send event to polling task.
        """
        log_debug(LOG, "Add event %s to the pollq" % (event.identify()))
        self._stashq.put(event)

    def s_get(self):
        """Get the event from stashq. """
        try:
            return self._stashq.get(timeout=0.1)
        except Queue.Empty:
            return None

    def fill(self):
        """Fill polling cache with events from poll queue.

            Fetch messages from poll queue which is
            python mutiprocessing.queue and fill local cache.
            Events need to persist and polled they are declated complete
            or cancelled.
        """
        log_debug(LOG, "Fill events from multi processing Q to internal cache")
        # Get some events from queue into cache
        for i in range(0, 10):
            ev = self._get()
            if ev:
                log_debug(LOG,
                          "Got new event %s from multi processing Q"
                          % (ev.identify()))
                self._cache.put(ev)

    def s_fill(self):
        """Fill stashing cache with events from stash queue.

            Fetch messages from stash queue which is
            python mutiprocessing.queue and fill local cache.
            Events need to persist and polled they are declated complete
            or cancelled.
        """
        log_debug(LOG, "Fill events from multi processing Q to internal cache")
        for i in range(0, 10):
            ev = self.s_get()

            if ev:
                log_error(LOG,
                          "Got new event %s from multi processing Q"
                          % (ev.identify()))
                self._stash_cache.put(ev)

    def peek(self, idx, count):
        """Peek for events instead of popping.

            Peek into specified number of events, this op does
            not result in pop of events from queue, hence the events
            are not lost.
        """
        log_debug(LOG,
                  "Peek poll events from index:%d count:%d"
                  % (idx, count))
        cache = self._cache.copy()
        qlen = len(cache)
        log_debug(LOG, "Number of elements in poll q - %d" % (qlen))
        pull = qlen if (idx + count) > qlen else count
        # return cache[idx:(idx + pull)], pull
        return cache, cache[0:pull], pull

    def add_stash_event(self, ev):
        """Add stash event in the cache. """
        return self.s_add(ev)

    def get_stash_event(self):
        """Get the stach event from cache. """
        copy = self._stash_cache.copy()
        for ev in copy:
            self._stash_cache.remove([ev])
            return ev

    def run(self):
        """Invoked in loop of periodic task to check for timedout events. """
        # Fill the cache first
        self.fill()
        self.s_fill()
        # Peek the events from cache
        cache, evs, count = self.peek(0, self._batch)
        for ev in evs:
            self._process_event(cache, ev)
        # self._procidx = (self._procidx + count) % (self._batch)
