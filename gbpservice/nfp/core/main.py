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

import eventlet
import operator
import os
import sys

import multiprocessing

from neutron.agent.common import config as n_config
from neutron.common import config as n_common_config

from oslo_config import cfg as oslo_config
from oslo_log import log as oslo_logging
from oslo_service import service as oslo_service

from gbpservice.nfp.core import cfg as nfp_config
from gbpservice.nfp.core import common as nfp_common
from gbpservice.nfp.core import event as nfp_event
from gbpservice.nfp.core import poll as nfp_poll
from gbpservice.nfp.core import rpc as nfp_rpc
from gbpservice.nfp.core import rpc_lb as nfp_rpc_lb

eventlet.monkey_patch()

LOG = oslo_logging.getLogger(__name__)
NCPUS = multiprocessing.cpu_count()
PID = os.getpid()
identify = nfp_common.identify
Event = nfp_event.Event
EventSequencer = nfp_event.EventSequencer
EventQueueHandler = nfp_event.EventQueueHandler
ReportStateTask = nfp_rpc.ReportStateTask
PollingTask = nfp_poll.PollingTask
PollQueueHandler = nfp_poll.PollQueueHandler
mp_lock = multiprocessing.Lock
mp_process = multiprocessing.Process
mp_queue = multiprocessing.Queue
itemgetter = operator.itemgetter
log_info = nfp_common.log_info
log_debug = nfp_common.log_debug
log_error = nfp_common.log_error


"""Implements cache of registered event handlers. """


class EventHandlers(object):

    def __init__(self):
        self._ehs = {}

    def register(self, event_desc):
        log_debug(LOG, "Registering handler %s" % (self.identify(event_desc)))
        if event_desc.id in self._ehs.keys():
            self._ehs[event_desc.id].extend([event_desc])
        else:
            self._ehs[event_desc.id] = [event_desc]

    def get(self, event):
        for id, eh in self._ehs.iteritems():
            if id == event.id:
                log_debug(LOG, "Returning handler %s" % (self.identify(eh[0])))
                return eh[0].handler
        return None

    def identify(self, event):
        return "%s - %s" % (event.identify(), identify(event.handler))


"""Common class implements all the APIs & cache.

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
        log_debug(LOG, "Acquired lock..")

    def unlock(self):
        self._lock.release()
        log_debug(LOG, "Released lock..")

    def sequencer_put_event(self, event):
        """Put an event in sequencer.

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
        """Get an event from the sequencer map.
        """
        return self._sequencer.get()

    def report_state(self):
        """Invoked by report_task to report states of all agents. """
        for agent in self._rpc_agents:
            rpc_agent = itemgetter(0)(agent)
            rpc_agent.report_state()

    def timeout(self):
        """Invoked by poll task to handle timer events. """
        self._pollhandler.run()

    def workers_init(self):
        """Initialize the configured number of worker process.

            This method just creates the process and not start them.
            If count is not specified in config file, then 2*NCPUS
            number of workers are created.
            Event queue per process is created.
        """
        wc = 2 * (NCPUS)
        if oslo_config.CONF.workers != wc:
            wc = oslo_config.CONF.workers
            log_info(LOG, "Creating %d number of workers" % (wc))

        ev_workers = [tuple() for w in range(0, wc)]

        for w in range(0, wc):
            evq = mp_queue()
            evq_handler = EventQueueHandler(
                self, self._conf, evq, self._event_handlers)
            worker = mp_process(target=evq_handler.run, args=(evq,))
            worker.daemon = True
            ev_workers[w] = ev_workers[w] + (worker, evq, evq_handler)
        return ev_workers

    def poll_handler_init(self):
        """Initialize poll handler, creates a poll & stash queue """
        pollq = mp_queue()
        stashq = mp_queue()
        handler = PollQueueHandler(self, pollq, stashq, self._event_handlers)
        return handler

    def modules_init(self, modules):
        """Initializes all the loaded NFP modules.

            Invokes "module_init" method of each module.
            Module can register its rpc & event handlers.
        """
        for module in modules:
            log_info(LOG, "Initializing module %s" % (identify(module)))
            try:
                module.module_init(self, self._conf)
            except AttributeError:
                log_error(LOG, "Module %s does not implement"
                          "module_init() method - skipping"
                          % (identify(module)))
                continue
                # raise AttributeError(module.__file__ + ': ' + str(s))
        return modules

    def init(self):
        """Intializes the NFP multi process framework.

            Top level method to initialize all the resources required.
        """
        self._event_handlers = EventHandlers()
        self._rpc_agents = []
        self._modules = self.modules_init(self._modules)
        self._workers = self.workers_init()
        self._pollhandler = self.poll_handler_init()
        nfp_rpc_lb.StickyRoundRobin(self._workers)
        self._loadbalancer = getattr(
            globals()['nfp_rpc_lb'],
            oslo_config.CONF.rpc_loadbalancer)(self._workers)

    def wait(self):
        """To wait for workers & rpc agents to stop. """
        # self.rpc_agents.wait()
        for w in self._workers:
            w[0].join()

    def start(self):
        """To start all the execution contexts.

            Starts worker process, rpc agents, polling task,
            report task.
        """
        self.init()
        for worker in self._workers:
            worker[0].start()
            log_debug(LOG, "Started worker - %d" % (worker[0].pid))

        # Polling task to poll for timer events
        self._polling_task = PollingTask(self)
        # Seperate task for reporting as report state rpc is a 'call'
        self._reportstate_task = ReportStateTask(self)

        for idx, agent in enumerate(self._rpc_agents):
            launcher = oslo_service.launch(oslo_config.CONF, agent[0])
            self._rpc_agents[idx] = agent + (launcher,)

    def post_event(self, event):
        """API for NFP module to generate a new internal event.

            Schedules this event to one of the worker. 'binding_key' is
            glue between different events, all events with same 'binding_key'
            are scheduled to same worker process.
        """
        worker = self._loadbalancer.get(event.binding_key)
        event.worker_attached = worker[0].pid
        if not event.worker_attached:
            for w in self._workers:
                if w[0].pid == os.getpid():
                    event.worker_attached = os.getpid()
                    worker = w
                    break
        log_info(LOG, "Scheduling internal event %s"
                 "to worker %d"
                 % (event.identify(), event.worker_attached))
        evq = worker[1]
        evq.put(event)

    def event_done(self, event):
        """API for NFP modules to mark an event complete.

            This is how framework learns that an event is complete and
            any other sequenced event can now be scheduled.
            Ideally, for event module at some point should call event_done.
        """
        log_info(LOG, "Event %s done" % (event.identify()))
        seq_map = self._sequencer.copy()

        try:
            seq_map = seq_map[event.worker_attached]
        except KeyError as err:
            # Event was not serialized
            return

        # If there are no events sequenced - nothing to do
        if event.binding_key not in seq_map:
            return

        log_debug(LOG, "Checking if event %s in serialize Q"
                  % (event.identify()))
        seq_q = seq_map[event.binding_key]['queue']
        for seq_event in seq_q:
            if seq_event.key == event.key:
                log_info(LOG, "Removing event %s from serialize Q"
                         % (seq_event.identify()))
                self._sequencer.remove(seq_event)
                break
        self._sequencer.delete_eventmap(event)

    def poll_event(self, event, max_times=sys.maxint):
        """API for NFP modules to generate a new poll event.

            Adds event to pollq for the poller to poll on it
            periodically.
            max_times - Defines the max number of times this event
            can timeout, after that event is auto cancelled.
        """
        log_info(LOG, "Adding to pollq - event %s for maxtimes: %d"
                 % (event.identify(), max_times))
        event.max_times = max_times
        self._pollhandler.add(event)

    def poll_event_timedout(self, eh, event):
        if event.id == 'EVENT_LIFE_TIMEOUT':
            self._pollhandler.event_life_timedout(eh, event)
        else:
            self._pollhandler.event_timedout(eh, event)

    def poll_event_done(self, event):
        """API for NFP modules to mark a poll event complete.

            If on any condition, module logic decides to stop polling
            for an event before it gets auto cancelled, then this
            method can be invoked.
        """
        log_info(LOG, "Poll event %s done.. Adding to pollq"
                 % (event.identify()))
        event.id = 'POLL_EVENT_DONE'
        self._pollhandler.add(event)

    def new_event(self, **kwargs):
        """API for NFP modules to prep an Event from passed args """
        return Event(**kwargs)

    def register_events(self, events):
        """API for NFP modules to register events """
        for event in events:
            log_info(LOG, "Registering event %s & handler %s"
                     % (event.identify(), identify(event.handler)))
            self._event_handlers.register(event)

    def register_rpc_agents(self, agents):
        """API for NFP mofules to register rpc agents """
        for agent in agents:
            self._rpc_agents.extend([(agent,)])

    def init_complete(self):
        """Invokes NFP modules init_complete() to do any post init logic """
        for module in self._modules:
            log_info(LOG, "Invoking init_complete() of module %s"
                     % (identify(module)))
            try:
                module.init_complete(self, self._conf)
            except AttributeError:
                log_info(LOG, "Module %s does not implement"
                         "init_complete() method - skipping"
                         % (identify(module)))

    def stash_event(self, event):
        """API for NFP modules to generate a new stash event.

            Adds event to stashq for the stasher to stash on it
            periodically.
        """
        log_info(LOG, "Adding to stashq - event %s"
                 % (event.identify()))
        event.max_times = sys.maxint
        self._pollhandler.add_stash_event(event)

    def get_stash_event(self):
        """Get stashed event from the cache. """
        event = self._pollhandler.get_stash_event()
        if event:
            return event.data

    def unit_test(self):
        for module in self._modules:
            module.unit_test(self._conf, self)


def modules_import():
    """Imports all the .py files from specified modules dir """
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
        log_error(LOG, "Failed to read files..")
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
    oslo_config.CONF.register_opts(
        nfp_config.es_openstack_opts, "keystone_authtoken")
    n_config.register_interface_driver_opts_helper(oslo_config.CONF)
    n_config.register_agent_state_opts_helper(oslo_config.CONF)
    n_config.register_root_helper(oslo_config.CONF)

    n_common_config.init(sys.argv[1:])
    n_config.setup_logging()
    modules = modules_import()

    sc = Controller(oslo_config.CONF, modules)
    sc.start()
    sc.init_complete()
    # sc.unit_test()
    sc.wait()
