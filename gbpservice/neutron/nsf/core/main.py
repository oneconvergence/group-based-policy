import os
import time
import sys
import copy
import threading

import eventlet
eventlet.monkey_patch()

from multiprocessing.queues import Queue
from Queue import Empty, Full
from multiprocessing import Process, Queue, Lock
import multiprocessing as multiprocessing

from neutron.agent.common import config
from neutron.common import config as common_config
from neutron import context
from neutron.agent import rpc as agent_rpc

from gbpservice.neutron.nsf.core import cfg as core_cfg
from gbpservice.neutron.nsf.core import lb as core_lb
from gbpservice.neutron.nsf.core import threadpool as core_tp
from gbpservice.neutron.nsf.core import periodic_task as core_periodic_task
from gbpservice.neutron.nsf.core import queue as core_queue

from neutron.common import rpc as n_rpc

from oslo_log import log as logging
from oslo_config import cfg
from oslo_service import periodic_task as oslo_periodic_task
from oslo_service import loopingcall
from oslo_service import service as os_service

LOG = logging.getLogger(__name__)

process = os.getpid()


def is_class(obj):
    return 'class' in str(type(obj))


def name(obj):
    if callable(obj):
        return "{0}.{1}.{2}".format(
            type(obj.im_self).__module__,
            type(obj.im_self).__name__,
            obj.__name__)
    elif is_class(obj):
        return "{0}.{1}".format(
            type(obj).__module__,
            type(obj).__name__)
    else:
        return obj.__name__


def identify(obj):
    try:
        return "(%s)" % (name(obj))
    except:
        return ""


class AgentReportState(object):

    def __init__(self, agent_state):
        self._context = context.get_admin_context_without_session()
        self._agent_state = agent_state
        self._report_topic = agent_state['plugin_topic']
        self._report_interval = agent_state['report_interval']
        self._state_rpc = agent_rpc.PluginReportStateAPI(
            self._report_topic)

    def report_state(self):
        try:
            LOG.debug(_("Reporting state ", self._agent_state))
            self._state_rpc.report_state(self._context, self._agent_state)
            self._agent_state.pop('start_flag', None)
        except AttributeError:
            # This means the server does not support report_state
            LOG.warn(_("Neutron server does not support state report."
                       " Agent State reporting will be "
                       "disabled."))
            self._heartbeat.stop()
            return
        except Exception:
            LOG.exception(_("Stopped reporting agent state!"))


class RpcAgent(n_rpc.Service):

    def __init__(
            self, sc, host=None,
            topic=None, manager=None, report_state=None):
        super(RpcAgent, self).__init__(host=host, topic=topic, manager=manager)
        if report_state:
            self._report_state = AgentReportState(self.report_state)

    def start(self):
        LOG.debug(_("RPCAgent listening on %s" % (self.identify)))
        super(RpcAgent, self).start()

    def report_state(self):
        if hasattr(self, '_report_state'):
            LOG.debug(_("Agent (%s) reporting state" % (self.identify())))
            self._report_state.report_state()

    def identify(self):
        return "(host=%s,topic=%s)" % (self.host, self.topic)


class RpcAgents(object):

    def __init__(self):
        self.services = []
        self.launchers = []

    def add(self, agents):
        for agent in agents:
            LOG.debug(_("New RPC Agent %s" % (agent.identify())))
        self.services.extend(agents)

    def launch(self):
        for s in self.services:
            LOG.debug(_("Launching a rpc service %s" % (s.identify())))
            l = os_service.launch(cfg.CONF, s)
            self.launchers.extend([l])

    def wait(self):
        for l in self.launchers:
            l.wait()

    def report_state(self):
        for agent in self.services:
            agent.report_state()


class ReportStateTask(oslo_periodic_task.PeriodicTasks):

    def __init__(self, sc):
        super(ReportStateTask, self).__init__(cfg.CONF)
        self._sc = sc
        pulse = loopingcall.FixedIntervalLoopingCall(
            self.run_periodic_tasks, None, None)
        pulse.start(interval=1, initial_delay=None)

    @oslo_periodic_task.periodic_task(spacing=5)
    def report_state(self, context):
        LOG.debug(_("Report state task invoked !"))
        self._sc.report_state()


class PeriodicTask(oslo_periodic_task.PeriodicTasks):

    def __init__(self, sc):
        super(PeriodicTask, self).__init__(cfg.CONF)
        self._sc = sc
        pulse = loopingcall.FixedIntervalLoopingCall(
            self.run_periodic_tasks, None, None)
        pulse.start(interval=1, initial_delay=None)

    @oslo_periodic_task.periodic_task(spacing=1)
    def periodic_sync_task(self, context):
        LOG.debug(_("Periodic sync task invoked !"))
        self._sc.timeout()


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


class EventCache(object):

    def __init__(self, sc):
        self._sc = sc
        self._cache = core_queue.Queue(sc)

    def rem(self, ev):
        self._cache.remove([ev])

    def rem_multi(self, evs):
        self._cache.remove(evs)

    def add(self, ev):
        self._cache.put(ev)

    def copy(self):
        return self._cache.copy()


class Serializer(object):

    def __init__(self, sc):
        self._sc = sc
        '''
        {'pid':{'binding_key':{'in_use':True, 'queue':[]}}}
        '''
        self._serializer_map = {}

    def serialize(self, ev):
        queued = False
        LOG.debug(_("Serialize event %s" % (ev.identify())))
        self._sc.lock()
        if ev.worker_attached not in self._serializer_map:
            self._serializer_map[ev.worker_attached] = {}
        mapp = self._serializer_map[ev.worker_attached]
        if ev.binding_key in mapp.keys():
            queued = True
            LOG.debug(_(
                "There is already an event in progress"
                "Queueing event %s" % (ev.identify())))

            mapp[ev.binding_key]['queue'].append(ev)
        else:
            LOG.debug(_(
                "Scheduling first event to exec"
                "Event %s" % (ev.identify())))
            mapp[ev.binding_key] = {'in_use': True, 'queue': []}
        self._sc.unlock()
        return queued

    def deserialize(self, ev):
        LOG.debug(_(
            "Deserialize event %s"
            % (ev.identify())))
        self._sc.lock()
        mapp = self._serializer_map[ev.worker_attached][ev.binding_key]
        if mapp['queue'] == []:
            LOG.debug(_(
                "No more events in the serial Q -"
                "Deleting the entry (%d) (%s)"
                % (ev.worker_attached, ev.binding_key)))
            del self._serializer_map[ev.worker_attached][ev.binding_key]
        self._sc.unlock()

    def copy(self):
        self._sc.lock()
        copy = dict(self._serializer_map)
        self._sc.unlock()
        return copy

    def remove(self, ev):
        self._sc.lock()
        self._serializer_map[ev.worker_attached][
            ev.binding_key]['queue'].remove(ev)
        self._sc.unlock()


class PollHandler(object):

    def __init__(self, sc, qu, eh, batch=-1):
        self._sc = sc
        self._eh = eh
        self._cache = EventCache(sc)
        self._pollq = qu
        self._procidx = 0
        self._procpending = 0
        self._batch = 10 if batch == -1 else batch

    def add(self, event):
        LOG.debug(_("Add event %s to the pollq" % (event.identify())))
        self._pollq.put(event)

    def rem(self, event):
        LOG.debug(_("Remove event %s from pollq" % (event.identify())))
        LOG.debug(
            _("Removing all poll events with key %s" % (event.identify())))
        remevs = []
        cache = self._cache.copy()
        for el in cache:
            if el.key == event.key:
                LOG.debug(_(
                    "Event %s key matched event %s key - "
                    "removing event %s from pollq"
                    % (el.identify(), event.identify(), el.identify())))
                remevs.append(el)
        self._cache.rem_multi(remevs)

    def _get(self):
        try:
            return self._pollq.get(timeout=0.1)
        except Empty:
            return None

    def fill(self):
        LOG.debug(_("Fill events from multi processing Q to internal cache"))
        # Get some events from queue into cache
        for i in range(0, 10):
            ev = self._get()
            if ev:
                LOG.debug(_(
                    "Got new event %s from multi processing Q"
                    % (ev.identify())))
                self._cache.add(ev)

    def peek(self, idx, count):
        LOG.debug(_("Peek poll events from index:%d count:%d" % (idx, count)))
        cache = self._cache.copy()
        qlen = len(cache)
        LOG.debug(_("Number of elements in poll q - %d" % (qlen)))
        pull = qlen if (idx + count) > qlen else count
        return cache[idx:(idx + pull)], pull

    def event_done(self, ev):
        LOG.info(_("Poll event %s to be marked done !" % (ev.identify())))
        self.rem(ev)

    def _cancelled(self, ev):
        LOG.info(_("Poll event %s cancelled" % (ev.identify())))
        ev.poll_event = 'POLL_EVENT_CANCELLED'
        self.event_done(ev)
        self._sc.rpc_event(ev)

    def _sched(self, ev):
        LOG.debug(_("Schedule event %s" % (ev.identify())))
        eh = self._eh.get(ev)
        if isinstance(eh, core_periodic_task.PeriodicTasks):
            if eh.check_timedout(ev):
                LOG.info(_(
                    "Event %s timed out -"
                    "scheduling it to a worker" % (ev.identify())))
                self._sc.rpc_event(ev)
                return ev
        else:
            LOG.info(_(
                "Event %s timed out -"
                "scheduling it to a worker" % (ev.identify())))
            self._sc.rpc_event(ev)
            return ev
        return None

    def event(self, ev):
        ev1 = copy.deepcopy(ev)
        ev1.serialize = False
        ev1.poll_event = \
            'POLL_EVENT_CANCELLED' if ev1.max_times == 0 else 'POLL_EVENT'
        if ev1.poll_event == 'POLL_EVENT_CANCELLED':
            self._cancelled(ev1)
        else:
            if self._sched(ev1):
                ev.max_times -= 1
                ev.last_run = ev1.last_run

    def process(self, ev):
        LOG.debug(_("Processing poll event %s" % (ev.identify())))
        self.event_done(ev) if ev.id == 'POLL_EVENT_DONE' else self.event(ev)

    def poll(self):
        # Fill the cache first
        self.fill()
        # Peek the events from cache
        evs, count = self.peek(0, self._batch)
        for ev in evs:
            self.process(ev)
        self._procidx = (self._procidx + count) % (self._batch)


class EventHandler(object):

    def __init__(self, sc, qu, eh):
        self._tpool = core_tp.ThreadPool()
        self._evq = qu
        self._eh = eh
        self._sc = sc

    def _get(self):
        # Check if any event can be pulled from serialize_map - this evs may be
        # waiting long enough
        LOG.debug(_("Checking serialize Q for events long pending"))
        ev = self._sc.serialize_get()
        if not ev:
            LOG.debug(_(
                "No event pending in serialize Q - "
                "checking the event Q"))
            try:
                ev = self._evq.get(timeout=0.1)
            except Empty:
                pass
            if ev:
                LOG.debug(_(
                    "Checking if the ev %s to be serialized"
                    % (ev.identify())))
                ev = self._sc.serialize(ev)
        return ev

    def _cancelled(self, eh, ev):
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

    def _sched(self, eh, ev):
        LOG.debug(_(
            "Event %s to be scheduled to handler %s"
            % (ev.identify(), identify(eh))))
        if isinstance(eh, core_periodic_task.PeriodicTasks):
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
        LOG.info(_("Started worker process - %s" % (process)))
        while True:
            ev = self._get()
            if ev:
                LOG.debug(_("Got event %s" % (ev.identify())))
                eh = self._eh.get(ev)
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
                        self._sched(eh, ev)
            time.sleep(0)  # Yield the CPU


class EventHandlers(object):

    def __init__(self):
        self._ehs = {}

    def register(self, ev):
        LOG.debug(_("Registering handler %s" % (self.identify(ev))))
        if ev.id in self._ehs.keys():
            self._ehs[ev.id].extend([ev])
        else:
            self._ehs[ev.id] = [ev]

    def get(self, ev):
        for id, eh in self._ehs.iteritems():
            if id == ev.id:
                LOG.debug(_("Returning handler %s" % (self.identify(eh[0]))))
                return eh[0].handler
        return None

    def identify(self, ev):
        return "%s - %s" % (ev.identify(), identify(ev.handler))


class ServiceController(object):

    def __init__(self, conf, modules):
        self._conf = conf
        self.modules = modules
        self._lock = Lock()
        self._serializer = Serializer(self)

    def lock(self):
        self._lock.acquire()
        LOG.debug(_("Acquired lock.."))

    def unlock(self):
        self._lock.release()
        LOG.debug(_("Released lock.."))

    def event_done(self, ev):
        LOG.info(_("Event %s done" % (ev.identify())))
        mapp = self._serializer.copy()
        mapp = mapp[ev.worker_attached]
        if ev.binding_key not in mapp:
            return

        LOG.debug(_("Checking if event %s in serialize Q"
                    % (ev.identify())))
        qu = mapp[ev.binding_key]['queue']
        for elem in qu:
            if elem.key == ev.key:
                LOG.debug(_("Removing event %s from serialize Q"
                            % (elem.identify())))
                self._serializer.remove(elem)
                break
        self._serializer.deserialize(ev)

    def serialize(self, ev):
        if not ev.serialize:
            return ev
        if not self._serializer.serialize(ev):
            return ev
        return None

    def serialize_get(self):
        LOG.debug(_(""))
        smap = self._serializer.copy()
        for mapp in smap.values():
            for val in mapp.values():
                if val['in_use']:
                    continue
                else:
                    if val['queue'] == []:
                        continue
                    ev = val['queue'][0]
                    LOG.debug(_("Returing serialized event %s"
                                % (ev.identify())))
                    return ev
        return None

    def workers_init(self):
        wc = 2 * (multiprocessing.cpu_count())
        if cfg.CONF.workers != wc:
            wc = cfg.CONF.workers
            LOG.info(_("Creating %d number of workers" % (wc)))

        workers = [tuple() for w in range(0, wc)]

        for w in range(0, wc):
            qu = Queue()
            evworker = EventHandler(self, qu, self.ehs)
            proc = Process(target=evworker.run, args=(qu,))
            proc.daemon = True
            workers[w] = workers[w] + (proc, qu, evworker)
        return workers

    def poll_init(self):
        qu = Queue()
        ph = PollHandler(self, qu, self.ehs)
        return ph

    def modules_init(self, modules):
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

    def _init(self):
        self.ehs = EventHandlers()
        self.rpc_agents = RpcAgents()
        self.modules = self.modules_init(self.modules)
        self.workers = self.workers_init()
        self.pollhandler = self.poll_init()
        self.loadbalancer = getattr(
            globals()['core_lb'], cfg.CONF.RpcLoadBalancer)(self.workers)

    def wait(self):
        # self.rpc_agents.wait()
        for w in self.workers:
            w[0].join()

    def start(self):
        self._init()
        self.periodic_task = PeriodicTask(self)
        # Seperate task for reporting as report state rpc is a 'call'
        self.reportstate_task = ReportStateTask(self)

        for w in self.workers:
            w[0].start()
            LOG.debug(_("Started worker - %d" % (w[0].pid)))
        self.rpc_agents.launch()

    def rpc_event(self, event):
        worker = self.loadbalancer.get(event.binding_key)
        event.worker_attached = worker[0].pid
        LOG.info(_("Scheduling internal event %s"
                   "to worker %d"
                   % (event.identify(), event.worker_attached)))
        qu = worker[1]
        qu.put(event)

    def poll_event(self, event, max_times=sys.maxint):
        LOG.info(_("Adding to pollq - event %s for maxtimes: %d"
                   % (event.identify(), max_times)))
        event.max_times = max_times
        self.pollhandler.add(event)

    def poll_event_done(self, event):
        LOG.info(_("Poll event %s done.. Adding to pollq"
                   % (event.identify())))
        event.id = 'POLL_EVENT_DONE'
        self.pollhandler.add(event)

    def report_state(self):
        self.rpc_agents.report_state()

    def timeout(self):
        self.pollhandler.poll()

    def register_events(self, evs):
        for ev in evs:
            LOG.info(_("Registering event %s & handler %s"
                       % (ev.identify(), identify(ev.handler))))
            self.ehs.register(ev)

    def register_rpc_agents(self, agents):
        self.rpc_agents.add(agents)

    def event(self, **kwargs):
        return Event(**kwargs)

    def init_complete(self):
        for module in self.modules:
            LOG.info(_("Invoking init_complete() of module %s"
                       % (identify(module))))
            try:
                module.init_complete(self, self._conf)
            except AttributeError:
                LOG.info(_("Module %s does not implement"
                           "init_complete() method - skipping"
                           % (identify(module))))

    def unit_test(self):
        for module in self.modules:
            module.unit_test(self._conf, self)


def modules_import():
    modules = []
    # os.path.realpath(__file__)
    base_module = __import__(cfg.CONF.modules_dir,
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
            module = __import__(cfg.CONF.modules_dir,
                                globals(), locals(), [fname[:-3]], -1)
            modules += [eval('module.%s' % (fname[:-3]))]
            # modules += [__import__(fname[:-3])]
    sys.path = syspath
    return modules


def main():
    cfg.CONF.register_opts(core_cfg.OPTS)
    config.register_interface_driver_opts_helper(cfg.CONF)
    config.register_agent_state_opts_helper(cfg.CONF)
    config.register_root_helper(cfg.CONF)

    common_config.init(sys.argv[1:])
    config.setup_logging()
    modules = modules_import()

    sc = ServiceController(cfg.CONF, modules)
    sc.start()
    sc.init_complete()
    # sc.unit_test()
    sc.wait()
