import os
import time
import sys
import copy
import threading
from operator import itemgetter

import eventlet
eventlet.monkey_patch()

from Queue import Empty as QEMPTY
from Queue import Full as QFULL

import multiprocessing
from multiprocessing import Process as mp_process
from multiprocessing import Queue as mp_queue
from multiprocessing import Lock as mp_lock

from neutron.agent.common import config as n_config
from neutron.common import config as n_common_config
from neutron import context as n_context
from neutron.agent import rpc as n_agent_rpc
from neutron.common import rpc as n_rpc

from oslo_log import log as oslo_logging
from oslo_config import cfg as oslo_config
from oslo_service import periodic_task as oslo_periodic_task
from oslo_service import loopingcall as oslo_looping_call
from oslo_service import service as oslo_service

from gbpservice.neutron.nsf.core import cfg as nfp_config
from gbpservice.neutron.nsf.core import rpc_lb as nfp_rpc_lb
from gbpservice.neutron.nsf.core import threadpool as nfp_tp
from gbpservice.neutron.nsf.core import periodic_task as nfp_periodic_task
from gbpservice.neutron.nsf.core import fifo as nfp_fifo


LOG = oslo_logging.getLogger(__name__)
NCPUS = multiprocessing.cpu_count()
PID = os.getpid()


def _is_class(obj):
    return 'class' in str(type(obj))


def _name(obj):
    """ Helper method to construct name of an object.

    'module.class' if object is of type 'class'
    'module.class.method' if object is of type 'method'
    """
    # If it is callable, then it is a method
    if callable(obj):
        return "{0}.{1}.{2}".format(
            type(obj.im_self).__module__,
            type(obj.im_self).__name__,
            obj.__name__)
    # If obj is of type class
    elif _is_class(obj):
        return "{0}.{1}".format(
            type(obj).__module__,
            type(obj).__name__)
    else:
        return obj.__name__


def identify(obj):
    """ Helper method to display identify an object.

    Useful for logging. Decodes based on the type of obj.
    Supports 'class' & 'method' types for now.
    """
    try:
        return "(%s)" % (_name(obj))
    except:
        """ Some unknown type, returning empty """
        return ""

""" Definition of an 'EVENT' in NFP framework.

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
        self.poll_event = None  # Not to be used by user
        self.worker_attached = None  # Not to be used by user
        self.last_run = None  # Not to be used by user
        self.max_times = -1  # Not to be used by user

    def identify(self):
        return "(id=%s,key=%s)" % (self.id, self.key)

""" This class implements the state reporting for neutron *aaS agents

    One common place of handling of reporting logic.
    Each nfp module just need to register the reporting data and
    plugin topic.
"""


class ReportState(object):

    def __init__(self, data):
        self._n_context = n_context.get_admin_context_without_session()
        self._data = data
        self._topic = data['plugin_topic']
        self._interval = data['report_interval']
        self._state_rpc = n_agent_rpc.PluginReportStateAPI(
            self._topic)

    def report(self):
        try:
            LOG.debug(_("Reporting state with data (%s)" % (self._data)))
            self._state_rpc.report_state(self._n_context, self._data)
            self._data.pop('start_flag', None)
        except AttributeError:
            # This means the server does not support report_state
            LOG.warn(_("Neutron server does not support state report."
                       " Agent State reporting will be "
                       "disabled."))
            return
        except Exception:
            LOG.exception(_("Stopped reporting agent state!"))


""" Wrapper class for Neutron RpcAgent definition.

    NFP modules will use this class for the agent definition.
    Associates the state reporting of agent to ease
    the usage for modules.
"""


class RpcAgent(n_rpc.Service):

    def __init__(
            self, sc, host=None,
            topic=None, manager=None, report_state=None):

        super(RpcAgent, self).__init__(host=host, topic=topic, manager=manager)

        # Check if the agent needs to report state
        if report_state:
            self._report_state = ReportState(self._report_state)

    def start(self):
        LOG.debug(_("RPCAgent listening on %s" % (self.identify)))
        super(RpcAgent, self).start()

    def report_state(self):
        if hasattr(self, '_report_state'):
            LOG.debug(_("Agent (%s) reporting state" % (self.identify())))
            self._report_state.report()

    def identify(self):
        return "(host=%s,topic=%s)" % (self.host, self.topic)

""" Periodic task to report neutron *aaS agent state.

    Derived from oslo periodic task, to report the agents state
    if any, to neutron *aaS plugin.
"""


class ReportStateTask(oslo_periodic_task.PeriodicTasks):

    def __init__(self, sc):
        super(ReportStateTask, self).__init__(oslo_config.CONF)
        self._sc = sc
        # Start a looping at the defined pulse
        pulse = oslo_looping_call.FixedIntervalLoopingCall(
            self.run_periodic_tasks, None, None)
        pulse.start(
            interval=oslo_config.CONF.reportstate_interval, initial_delay=None)

    @oslo_periodic_task.periodic_task(spacing=5)
    def report_state(self, context):
        LOG.debug(_("Report state task invoked !"))
        # trigger the state reporting
        self._sc.report_state()

""" Periodic task to poll for nfp events.

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

    @oslo_periodic_task.periodic_task(spacing=1)
    def periodic_sync_task(self, context):
        LOG.debug(_("Periodic sync task invoked !"))
        # invoke the common class to handle event timeouts
        self._sc.timeout()

""" Handles the sequencing of related events.

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

    def add(self, ev):
        """ Add the event to the sequencer.

            Checks if there is already a related event scheduled,
            if not, will not queue the event. If yes, then will
            queue this event.
            Returns True(queued)/False(not queued).
        """
        queued = False
        LOG.debug(_("Sequence event %s" % (ev.identify())))
        self._sc.lock()
        if ev.worker_attached not in self._sequencer_map:
            self._sequencer_map[ev.worker_attached] = {}
        seq_map = self._sequencer_map[ev.worker_attached]
        if ev.binding_key in seq_map.keys():
            queued = True
            LOG.debug(_(
                "There is already an event in progress"
                "Queueing event %s" % (ev.identify())))

            seq_map[ev.binding_key]['queue'].append(ev)
        else:
            LOG.debug(_(
                "Scheduling first event to exec"
                "Event %s" % (ev.identify())))
            seq_map[ev.binding_key] = {'in_use': True, 'queue': []}
        self._sc.unlock()
        return queued

    def copy(self):
        """ Returns the copy of sequencer_map to caller. """
        self._sc.lock()
        copy = dict(self._sequencer_map)
        self._sc.unlock()
        return copy

    def remove(self, ev):
        """ Removes an event from sequencer map.

            If this is the last related event in the map, then
            the complete entry is deleted from sequencer map.
        """
        self._sc.lock()
        self._sequencer_map[ev.worker_attached][
            ev.binding_key]['queue'].remove(ev)
        self._del_evmap(ev)
        self._sc.unlock()

    def _del_evmap(self, ev):
        """ Internal method to delete event map, if it is empty. """
        seq_map = self._sequencer_map[ev.worker_attached][ev.binding_key]
        if seq_map['queue'] == []:
            LOG.debug(_(
                "No more events in the seq map -"
                "Deleting the entry (%d) (%s)"
                % (ev.worker_attached, ev.binding_key)))
            del self._sequencer_map[ev.worker_attached][ev.binding_key]

""" Handles the polling queue, searches for the timedout events.

    Invoked in PollingTask, fetches new events from pollQ to cache them.
    Searches in cache for timedout events, enqueues timedout events to
    respective worker process. Event stays in cache till it is declared to
    be complete or cancelled.
    Event gets cancelled, if it is polled for max number of times. By default,
    it is huge number unless otherwise specified by logic which enqueues this
    event.
"""


class PollQueueHandler(object):

    def __init__(self, sc, qu, ehs, batch=-1):
        self._sc = sc
        self._ehs = ehs
        self._pollq = qu
        self._procidx = 0
        self._procpending = 0
        self._batch = 10 if batch == -1 else batch
        self._cache = nfp_fifo.Fifo(sc)

    def _get(self):
        """ Internal method to get messages from pollQ.

            Handles the empty queue exception.
        """
        try:
            return self._pollq.get(timeout=0.1)
        except QEMPTY:
            return None

    def _cancelled(self, ev):
        """ To cancel an event.

            Removes the event from internal cache and scheds the
            event to worker to handle any cleanup.
        """
        LOG.info(_("Poll event %s cancelled" % (ev.identify())))
        ev.poll_event = 'POLL_EVENT_CANCELLED'
        self._event_done(ev)
        self._sc.post_event(ev)

    def _schedule(self, ev):
        """ Schedule the event to approp worker.

            Checks if the event has timedout and if yes,
            then schedules it to the approp worker. Approp worker -
            worker which handled this event earlier.
        """
        LOG.debug(_("Schedule event %s" % (ev.identify())))
        eh = self._ehs.get(ev)
        """ Check if the event has any defined spacing interval, if yes
            then did it timeout w.r.t the spacing ?
            If yes, then event is scheduled.
            Spacing for event can only be defined if the registered event
            handler is derived from periodic task class. Following check
            is for same.
        """
        if isinstance(eh, nfp_periodic_task.PeriodicTasks):
            if eh.check_timedout(ev):
                LOG.info(_(
                    "Event %s timed out -"
                    "scheduling it to a worker" % (ev.identify())))
                self._sc.post_event(ev)
                return ev
        else:
            LOG.info(_(
                "Event %s timed out -"
                "scheduling it to a worker" % (ev.identify())))
            self._sc.post_event(ev)
            return ev
        return None

    def _process_event(self, ev):
        """ Process different type of poll event. """

        LOG.debug(_("Processing poll event %s" % (ev.identify())))
        if ev.id == 'POLL_EVENT_DONE':
            return self._event_done(ev)
        copyev = copy.deepcopy(ev)
        copyev.serialize = False
        copyev.poll_event = 'POLL_EVENT'
        if copyev.max_times == 0:
            return self._cancelled(copyev)
        if self._schedule(copyev):
            ev.max_times -= 1
            ev.last_run = copyev.last_run

    def _event_done(self, ev):
        """ Marks the event as complete.

            Invoked by caller to mark the event as complete.
            Removes the event from internal cache.
        """
        LOG.info(_("Poll event %s to be marked done !" % (ev.identify())))
        self.remove(ev)

    def add(self, event):
        """ Adds an event to the pollq.

            Invoked in context of worker process
            to send event to polling task.
        """
        LOG.debug(_("Add event %s to the pollq" % (event.identify())))
        self._pollq.put(event)

    def remove(self, event):
        """ Remove an event from polling cache.

            All the events which matches with the event.key
            are removed from cache.
        """
        LOG.debug(_("Remove event %s from pollq" % (event.identify())))
        LOG.debug(
            _("Removing all poll events with key %s" % (event.identify())))
        remevs = []
        cache = self._cache.copy()
        for elem in cache:
            if elem.key == event.key:
                LOG.debug(_(
                    "Event %s key matched event %s key - "
                    "removing event %s from pollq"
                    % (elem.identify(), event.identify(), elem.identify())))
                remevs.append(elem)
        self._cache.remove(remevs)

    def fill(self):
        """ Fill polling cache with events from poll queue.

            Fetch messages from poll queue which is
            python mutiprocessing.queue and fill local cache.
            Events need to persist and polled they are declated complete
            or cancelled.
        """
        LOG.debug(_("Fill events from multi processing Q to internal cache"))
        # Get some events from queue into cache
        for i in range(0, 10):
            ev = self._get()
            if ev:
                LOG.debug(_(
                    "Got new event %s from multi processing Q"
                    % (ev.identify())))
                self._cache.put(ev)

    def peek(self, idx, count):
        """ Peek for events instead of popping.

            Peek into specified number of events, this op does
            not result in pop of events from queue, hence the events
            are not lost.
        """
        LOG.debug(_("Peek poll events from index:%d count:%d" % (idx, count)))
        cache = self._cache.copy()
        qlen = len(cache)
        LOG.debug(_("Number of elements in poll q - %d" % (qlen)))
        pull = qlen if (idx + count) > qlen else count
        return cache[idx:(idx + pull)], pull

    def run(self):
        """ Invoked in loop of periodic task to check for timedout events. """
        # Fill the cache first
        self.fill()
        # Peek the events from cache
        evs, count = self.peek(0, self._batch)
        for ev in evs:
            self._process_event(ev)
        self._procidx = (self._procidx + count) % (self._batch)

""" Handles the processing of evens in event queue.

    Executes in the context of worker process, runs in loop to fetch
    the events and process them. As processing, invokes the registered
    handler for the event.
"""


class EventQueueHandler(object):

    def __init__(self, sc, qu, ehs):
        # Pool of green threads per process
        self._tpool = nfp_tp.ThreadPool()
        self._evq = qu
        self._ehs = ehs
        self._sc = sc

    def _get(self):
        """ Internal function to get an event for processing.

            First checks in sequencer map - these events could be
            waiting for long.
            If no events, then fetch the events from event_queue -
            listener process adds events into this queue.
            Returns the event to be processed.
        """
        # Check if any event can be pulled from serialize_map - this evs may be
        # waiting long enough
        LOG.debug(_("Checking serialize Q for events long pending"))
        ev = self._sc.sequencer_get_event()
        if not ev:
            LOG.debug(_(
                "No event pending in sequencer Q - "
                "checking the event Q"))
            try:
                ev = self._evq.get(timeout=0.1)
            except QEMPTY:
                pass
            if ev:
                LOG.debug(_(
                    "Checking if the ev %s to be serialized"
                    % (ev.identify())))
                """
                If this event needs to be serialized and is first event
                then the same is returned back, otherwise None is
                returned. If event need not be serialized then it is
                returned.
                """
                ev = self._sc.sequencer_put_event(ev)
        return ev

    def _cancelled(self, eh, ev):
        """ Internal function to cancel an event.

            Removes it from poll_queue also.
            Invokes the 'poll_event_cancel' method of the
            registered handler if it is implemented.
        """
        LOG.info(_(
            "Event %s cancelled -"
            "invoking %s handler's poll_event_cancel method"
            % (ev.identify(), identify(eh))))
        try:
            self._sc.poll_event_done(ev)
            eh.poll_event_cancel(ev)
        except AttributeError:
            LOG.info(_(
                "Handler %s does not implement"
                "poll_event_cancel method" % (identify(eh))))

    def _poll_event(self, eh, ev):
        """ Internal function to handle the poll event.

            Poll task adds the timedout events to the worker process.
            This method handles such timedout events in worker context.
            Invoke the decorated timeout handler for the event, if any.
            (or) invoke the default 'handle_poll_event' method of registered
            handler.
            """
        LOG.debug(_(
            "Event %s to be scheduled to handler %s"
            % (ev.identify(), identify(eh))))

        # Event handler can implement decorated timeout methods only if it
        # is dervied from periodic_task. Checking here.
        if isinstance(eh, nfp_periodic_task.PeriodicTasks):
            # Check if this event has a decorated timeout method
            peh = eh.get_periodic_event_handler(ev)
            if peh:
                t = self._tpool.dispatch(peh, eh, ev)
                LOG.info(_(
                    "Dispatched method %s of handler %s"
                    "for event %s to thread %s"
                    % (identify(peh), identify(eh),
                        ev.identify(), t.identify())))

            else:
                t = self._tpool.dispatch(eh.handle_poll_event, ev)
                LOG.info(_(
                    "Dispatched handle_poll_event() of handler %s"
                    "for event %s to thread %s"
                    % (identify(eh),
                        ev.identify(), t.identify())))
        else:
            self._tpool.dispatch(eh.handle_poll_event, ev)
            LOG.info(_(
                "Dispatched handle_poll_event() of handler %s"
                "for event %s to thread %s"
                % (identify(eh),
                    ev.identify(), t.identify())))

    def run(self, qu):
        """ Worker process loop to fetch & process events from event queue.

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
        LOG.info(_("Started worker process - %s" % (PID)))
        while True:
            ev = self._get()
            if ev:
                LOG.debug(_("Got event %s" % (ev.identify())))
                eh = self._ehs.get(ev)
                if not ev.poll_event:
                    t = self._tpool.dispatch(eh.handle_event, ev)
                    LOG.debug(_(
                        "Event %s is not poll event - "
                        "disptaching handle_event() of handler %s"
                        "to thread %s"
                        % (ev.identify(), identify(eh), t.identify())))
                else:
                    if ev.poll_event == 'POLL_EVENT_CANCELLED':
                        LOG.debug(
                            _("Got cancelled event %s" % (ev.identify())))
                        self._cancelled(eh, ev)
                    else:
                        LOG.info(
                            _("Got POLL Event %s scheduling"
                                % (ev.identify())))
                        self._poll_event(eh, ev)
            time.sleep(0)  # Yield the CPU


""" Implements cache of registered event handlers. """


class EventHandlers(object):

    def __init__(self):
        self._ehs = {}

    def register(self, event_desc):
        LOG.debug(_("Registering handler %s" % (self.identify(event_desc))))
        if event_desc.id in self._ehs.keys():
            self._ehs[event_desc.id].extend([event_desc])
        else:
            self._ehs[event_desc.id] = [event_desc]

    def get(self, event):
        for id, eh in self._ehs.iteritems():
            if id == event.id:
                LOG.debug(_("Returning handler %s" % (self.identify(eh[0]))))
                return eh[0].handler
        return None

    def identify(self, event):
        return "%s - %s" % (event.identify(), identify(event.handler))


""" Common class implements all the APIs & cache.

    Common class used across modules and classes to access the
    cache of required objects.
    Also, implements the abstracted APIs for NFP modules interaction.
    All the registered handlers, NFP modules, worker process, rpc agents
    etc all instantiated, stored, maintained in this class.
    Runs in listener process context.
"""


class Controller(object):

    def __init__(self, conf, modules):
        # Configuration object
        self._conf = conf
        # Cache of auto-loaded NFP modules
        self._modules = modules
        # Multi processing lock for safe access to shared resources
        self._lock = mp_lock()
        # Sequencer to sequence the related events.
        self._sequencer = EventSequencer(self)
	self._event = multiprocessing.Event()

    def lock(self):
        self._lock.acquire()
        LOG.debug(_("Acquired lock.."))

    def unlock(self):
        self._lock.release()
        LOG.debug(_("Released lock.."))

    def sequencer_put_event(self, event):
        """ Put an event in sequencer.

            Check if event needs to be sequenced, this is module logic choice.
            If yes, then invokes sequencer. If this is the first event in
            sequence, it is returned immediately, all subsequent events will be
            sequenced by sequencer till this event is complete.
        """
        if not event.serialize:
            return event
        if not self._sequencer.add(event):
            return event
        return None

    def sequencer_get_event(self):
        """ Get an event from the sequencer map.

            Invoked by workers to get the first event in sequencer map.
            Since it is a FIFO, first event could be waiting long to be
            scheduled.
            Loops over copy of sequencer map and returns the first waiting
            event.
        """
        LOG.debug(_(""))
        seq_map = self._sequencer.copy()
        for seq in seq_map.values():
            for val in seq.values():
                if val['in_use']:
                    continue
                else:
                    if val['queue'] == []:
                        continue
                    event = val['queue'][0]
                    LOG.debug(_("Returing serialized event %s"
                                % (event.identify())))
                    return event
        return None

    def report_state(self):
        """ Invoked by report_task to report states of all agents. """
        for agent in self._rpc_agents:
            rpc_agent = itemgetter(0)(agent)
            rpc_agent.report_state()

    def timeout(self):
        """ Invoked by poll task to handle timer events. """
        self._pollhandler.run()

    def workers_init(self):
        """ Initialize the configured number of worker process.

            This method just creates the process and not start them.
            If count is not specified in config file, then 2*NCPUS
            number of workers are created.
            Event queue per process is created.
        """
        wc = 2 * (NCPUS)
        if oslo_config.CONF.workers != wc:
            wc = oslo_config.CONF.workers
            LOG.info(_("Creating %d number of workers" % (wc)))

        ev_workers = [tuple() for w in range(0, wc)]

        for w in range(0, wc):
            evq = mp_queue()
            evq_handler = EventQueueHandler(self, evq, self._event_handlers)
            worker = mp_process(target=evq_handler.run, args=(evq,))
            worker.daemon = True
            ev_workers[w] = ev_workers[w] + (worker, evq, evq_handler)
        return ev_workers

    def poll_handler_init(self):
        """ Initialize poll handler, creates a poll queue. """
        pollq = mp_queue()
        handler = PollQueueHandler(self, pollq, self._event_handlers)
        return handler

    def modules_init(self, modules):
        """ Initializes all the loaded NFP modules.

            Invokes "module_init" method of each module.
            Module can register its rpc & event handlers.
        """
        for module in modules:
            LOG.info(_("Initializing module %s" % (identify(module))))
            try:
                module.module_init(self, self._conf)
            except AttributeError as s:
                LOG.error(_("Module %s does not implement"
                            "module_init() method - skipping"
                            % (identify(module))))
                continue
                # raise AttributeError(module.__file__ + ': ' + str(s))
        return modules

    def init(self):
        """ Intializes the NFP multi process framework.

            Top level method to initialize all the resources required.
        """
        self._event_handlers = EventHandlers()
        self._rpc_agents = []
        self._modules = self.modules_init(self._modules)
        self._workers = self.workers_init()
        self._pollhandler = self.poll_handler_init()
        self._loadbalancer = getattr(
            globals()['nfp_rpc_lb'],
            oslo_config.CONF.rpc_loadbalancer)(self._workers)

    def wait(self):
        """ To wait for workers & rpc agents to stop. """
        # self.rpc_agents.wait()
        for w in self._workers:
            w[0].join()

    def start(self):
        """ To start all the execution contexts.

            Starts worker process, rpc agents, polling task,
            report task.
        """
        self.init()
        # Polling task to poll for timer events
        self._polling_task = PollingTask(self)
        # Seperate task for reporting as report state rpc is a 'call'
        self._reportstate_task = ReportStateTask(self)

        for worker in self._workers:
            worker[0].start()
            LOG.debug(_("Started worker - %d" % (worker[0].pid)))

        for idx, agent in enumerate(self._rpc_agents):
            launcher = oslo_service.launch(oslo_config.CONF, agent[0])
            self._rpc_agents[idx] = agent + (launcher,)

    def post_event(self, event):
        """ API for NFP module to generate a new internal event.

            Schedules this event to one of the worker. 'binding_key' is
            glue between different events, all events with same 'binding_key'
            are scheduled to same worker process.
        """
        worker = self._loadbalancer.get(event.binding_key)
        event.worker_attached = worker[0].pid
        LOG.info(_("Scheduling internal event %s"
                   "to worker %d"
                   % (event.identify(), event.worker_attached)))
        evq = worker[1]
        evq.put(event)

    def event_done(self, event):
        """ API for NFP modules to mark an event complete.

            This is how framework learns that an event is complete and
            any other sequenced event can now be scheduled.
            Ideally, for event module at some point should call event_done.
        """
        LOG.info(_("Event %s done" % (event.identify())))
        seq_map = self._sequencer.copy()
        seq_map = seq_map[event.worker_attached]

        # If there are no events sequenced - nothing to do
        if event.binding_key not in seq_map:
            return

        LOG.debug(_("Checking if event %s in serialize Q"
                    % (event.identify())))
        seq_q = seq_map[event.binding_key]['queue']
        for seq_event in seq_q:
            if seq_event.key == event.key:
                LOG.debug(_("Removing event %s from serialize Q"
                            % (seq_event.identify())))
                self._sequencer.remove(seq_event)
                break

    def poll_event(self, event, max_times=sys.maxint):
        """ API for NFP modules to generate a new poll event.

            Adds event to pollq for the poller to poll on it
            periodically.
            max_times - Defines the max number of times this event
            can timeout, after that event is auto cancelled.
        """
        LOG.info(_("Adding to pollq - event %s for maxtimes: %d"
                   % (event.identify(), max_times)))
        event.max_times = max_times
        self._pollhandler.add(event)

    def poll_event_done(self, event):
        """ API for NFP modules to mark a poll event complete.

            If on any condition, module logic decides to stop polling
            for an event before it gets auto cancelled, then this
            method can be invoked.
        """
        LOG.info(_("Poll event %s done.. Adding to pollq"
                   % (event.identify())))
        event.id = 'POLL_EVENT_DONE'
        self.pollhandler.add(event)

    def new_event(self, **kwargs):
        """ API for NFP modules to prep an Event from passed args """
        return Event(**kwargs)

    def register_events(self, events):
        """ API for NFP modules to register events """
        for event in events:
            LOG.info(_("Registering event %s & handler %s"
                       % (event.identify(), identify(event.handler))))
            self._event_handlers.register(event)

    def register_rpc_agents(self, agents):
        """ API for NFP mofules to register rpc agents """
        for agent in agents:
            self._rpc_agents.extend([(agent,)])

    def init_complete(self):
        """ Invokes NFP modules init_complete() to do any post init logic """
        for module in self._modules:
            LOG.info(_("Invoking init_complete() of module %s"
                       % (identify(module))))
            try:
                module.init_complete(self, self._conf)
            except AttributeError:
                LOG.info(_("Module %s does not implement"
                           "init_complete() method - skipping"
                           % (identify(module))))

    def unit_test(self):
        for module in self._modules:
            module.unit_test(self._conf, self)


def modules_import():
    """ Imports all the .py files from specified modules dir """
    modules = []
    # os.path.realpath(__file__)
    base_module = __import__(oslo_config.CONF.modules_dir,
                             globals(), locals(), ['modules'], -1)
    # modules_dir = os.getcwd() + "/../modules"
    modules_dir = base_module.__path__[0]
    syspath = sys.path
    sys.path = [modules_dir] + syspath

    try:
        files = os.listdir(modules_dir)
    except OSError:
        LOG.error(_("Failed to read files.."))
        files = []

    for fname in files:
        if fname.endswith(".py") and fname != '__init__.py':
            module = __import__(oslo_config.CONF.modules_dir,
                                globals(), locals(), [fname[:-3]], -1)
            modules += [eval('module.%s' % (fname[:-3]))]
            # modules += [__import__(fname[:-3])]
    sys.path = syspath
    return modules


def main():
    oslo_config.CONF.register_opts(nfp_config.OPTS)
    n_config.register_interface_driver_opts_helper(oslo_config.CONF)
    n_config.register_agent_state_opts_helper(oslo_config.CONF)
    n_config.register_root_helper(oslo_config.CONF)

    n_common_config.init(sys.argv[1:])
    n_config.setup_logging()
    modules = modules_import()

    sc = Controller(oslo_config.CONF, modules)
    sc.start()
    sc.init_complete()
    sc.unit_test()
    sc.wait()
