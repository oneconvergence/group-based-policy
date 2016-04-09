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
import multiprocessing
import os
import sys
import time

from oslo_log import log as oslo_logging

from gbpservice.nfp.core import cfg as nfp_cfg
from gbpservice.nfp.core import common as nfp_common
from gbpservice.nfp.core import event as nfp_event
from gbpservice.nfp.core import launcher as nfp_launcher
from gbpservice.nfp.core import manager as nfp_manager
from gbpservice.nfp.core import poll as nfp_poll
from gbpservice.nfp.core import worker as nfp_worker

LOGGER = oslo_logging.getLogger(__name__)
LOG = nfp_common.log
PIPE = multiprocessing.Pipe
PROCESS = multiprocessing.Process
identify = nfp_common.identify

eventlet.monkey_patch()

"""Implements NFP service.

    Base class for nfp modules, modules can invoke methods
    of this class to interact with core.
"""


class NfpService(object):

    def __init__(self, conf):
        self._conf = conf
        self._event_handlers = nfp_event.NfpEventHandlers()

    def _make_new_event(self, event):
        """Make a new event from the object passed. """
        desc_dict = event.desc.__dict__
        desc = nfp_event.EventDesc(**desc_dict)
        event_dict = event.__dict__
        event = self.create_event(**event_dict)
        setattr(event, 'desc', desc)
        return event

    def get_event_handlers(self):
        return self._event_handlers

    def register_events(self, event_descs):
        """Register event handlers with core. """
        # REVISIT (MAK): Can the name be changed
        # to register_event_handlers() ?
        for event_desc in event_descs:
            self._event_handlers.register(event_desc.id, event_desc.handler)

    def register_rpc_agents(self):
        pass

    def new_event(self, **kwargs):
        return self.create_event(**kwargs)

    def create_event(self, **kwargs):
        """To create a new event. """
        event = None
        try:
            event = nfp_event.Event(**kwargs)
        except AssertionError as aerr:
            LOG(LOGGER, 'EXCEPTION', "%s" % (aerr))
        return event

    def post_event(self, event):
        """Post an event.

            As a base class, it only does the descriptor preparation.
            NfpController class implements the required functionality.
        """
        handler = self._event_handlers.get_event_handler(event.id)
        assert handler, "No handler registered for event %s" % (event.id)
        kwargs = {'type': nfp_event.SCHEDULE_EVENT,
                  'flag': nfp_event.EVENT_NEW,
                  'pid': os.getpid()}
        if event.key:
            kwargs.update({'key': event.key})
        desc = nfp_event.EventDesc(**kwargs)
        setattr(event, 'desc', desc)
        return event

    def poll_event(self, event, spacing=0, max_times=sys.maxint):
        """To poll for an event.
            NfpModule will invoke this method to start polling of
            an event. As a base class, it only does the polling
            descriptor preparation.
            NfpController class implements the required functionality.
        """
        ev_spacing = self._event_handlers.get_poll_spacing(event.id)
        assert spacing or ev_spacing, "No spacing specified for polling"
        if ev_spacing:
            spacing = ev_spacing

        handler = self._event_handlers.get_poll_handler(event.id)
        assert handler, "No poll handler found for event %s" % (event.id)

        refuuid = event.desc.uuid
        event = self._make_new_event(event)
        event.lifetime = 0
        event.desc.type = nfp_event.POLL_EVENT

        kwargs = {'spacing': spacing,
                  'max_times': max_times,
                  'ref': refuuid}
        poll_desc = nfp_event.PollDesc(**kwargs)

        setattr(event.desc, 'poll_desc', poll_desc)
        return event

    def event_complete(self, event):
        """To declare and event complete. """
        event.sequence = False
        event.desc.flag = nfp_event.EVENT_COMPLETE
        return event

    def create_work(self, work):
        """Create a work, collection of events. """
        pass


"""NFP Controller class mixin other nfp classes.

    Nfp modules get the instance of this class when
    they are initialized.
    Nfp modules interact with core using the methods
    of 'Service' class, whose methods are implemented
    in this class.
    Also, it mixes the other nfp core classes to complete
    a nfp module request.
"""


class NfpController(nfp_launcher.NfpLauncher, NfpService):

    def __init__(self, conf):
        # Init the super classes.
        nfp_launcher.NfpLauncher.__init__(self, conf)
        NfpService.__init__(self, conf)

        self._conf = conf
        self._pipe = None
        self._manager = nfp_manager.NfpResourceManager(conf, self)
        self._worker = nfp_worker.NfpWorker(conf)
        self._poll_handler = nfp_poll.NfpPollHandler(conf)
        # For book keeping
        self._worker_process = {}

        # ID of process handling this controller obj
        self.PROCESS_TYPE = "distributor"

    def pipe_send(self, pipe, event):
        pipe.send(event)

    def _fork(self, args):
        proc = PROCESS(target=self.child, args=args)
        proc.daemon = True
        proc.start()
        return proc

    def _manager_task(self):
        while True:
            # Run 'Manager' here to monitor for workers and
            # events.
            self._manager.manager_run()
            eventlet.greenthread.sleep(0.01)

    def get_childrens(self):
        # oslo_process.ProcessLauncher has this dictionary,
        # 'NfpLauncher' derives oslo_service.ProcessLauncher
        return self.children

    def fork_child(self, wrap):
        """Forks a child.

            Creates a full duplex pipe for child & parent
            to communicate.

            Returns: Multiprocess object.
        """

        # REVISIT(MAK): Multiprocessing.Queue implements exchanger
        # type model ? any process can generate
        # message for any other ?
        # Pipe allows one-one communication.
        parent_pipe, child_pipe = PIPE(duplex=True)

        # Registered event handlers of nfp module.
        # Workers need copy of this data to dispatch an
        # event to module.
        proc = self._fork(args=(wrap.service, parent_pipe, child_pipe, self))

        LOG(LOGGER, 'ERROR', "Forked a new child: %d"
            "Parent Pipe: % s, Child Pipe: % s" % (
                proc.pid, str(parent_pipe), str(child_pipe)))

        try:
            wrap.child_pipe_map[proc.pid] = parent_pipe
        except AttributeError:
            setattr(wrap, 'child_pipe_map', {})
            wrap.child_pipe_map[proc.pid] = parent_pipe

        self._worker_process[proc.pid] = proc
        return proc.pid

    def launch(self, workers):
        """Launch the controller.

            Uses Oslo Service to launch with configured #of workers.
            Spawns a manager task to manager nfp events & workers.

            :param workers: #of workers to be launched

            Returns: None
        """
        super(NfpController, self).launch_service(
            self._worker, workers=workers)

    def _update_manager(self):
        childs = self.get_childrens()
        for pid, wrapper in childs.iteritems():
            pipe = wrapper.child_pipe_map[pid]
            # Inform 'Manager' class about the new_child.
            self._manager.new_child(pid, pipe)

    def post_launch(self):
        self._update_manager()
        # One task to manage the resources - workers & events.
        eventlet.spawn_n(self._manager_task)
        # Oslo periodic task to poll for timer events
        nfp_poll.PollingTask(self._conf, self)

    def poll_add(self, event, timeout, callback):
        self._poll_handler.poll_add(
            event, timeout, callback)

    def poll(self):
        self._poll_handler.run()

    def _process_event(self, event):
        self._manager.process_events([event])

    def post_event(self, event):
        """Post a new event into the system.

            If distributor(main) process posts an event, it
            is delivered to the worker.
            If worker posts an event, it is deliverd to
            distributor for processing, where it can decide
            to loadbalance & sequence events.

            :param event: Object of 'Event' class.

            Returns: None
        """
        event = super(NfpController, self).post_event(event)
        LOG(LOGGER, 'DEBUG', "(event - %s) - New event" % (event.identify()))
        if self.PROCESS_TYPE == "worker":
            # Event posted in worker context, send it to parent process
            LOG(LOGGER, 'ERROR', "(event - %s) - new event in worker"
                "posting to distributor process" % (event.identify()))
            # Send it to the distributor process
            self.pipe_send(self._pipe, event)
        else:
            LOG(LOGGER, 'ERROR', "(event - %s) - new event in distributor"
                "processing event" % (event.identify()))
            self._manager.process_events([event])

    def poll_event(self, event, spacing=0, max_times=sys.maxint):
        """Post a poll event into the system.

            Core will poll for this event to timeout, after
            timeout registered handler of module is invoked.

            :param event: Object of 'Event' class.
            :param spacing: Spacing at which event should timeout.
            :param max_times: Max #of times the event can timeout,
                after the max_times, event is auto cancelled by
                the core and the registered handler of module
                is invoked.

            Returns: None
        """
        # Poll event can only be posted by worker not by listener process
        if self.PROCESS_TYPE != "worker":
            LOG(LOGGER, 'DEBUG',
                "(event - %s) - poll event in distributor")
            # 'Service' class to construct the poll event descriptor
            event = super(NfpController, self).poll_event(
                event, spacing=spacing, max_times=max_times)
            self._manager.process_events([event])
        else:
            '''
            # Only event which is delivered to a worker can be polled for, coz,
            # after event timeouts, it should be delivered to the same worker,
            # hence the check to make sure the correct event is been asked for
            # polling.
            assert event.desc.worker, "No worker for event %s" % (
                event.identify())
            LOG(LOGGER, 'DEBUG', "(event - %s) - poll event in worker" %
                (event.identify()))
            '''
            # 'Service' class to construct the poll event descriptor
            event = super(NfpController, self).poll_event(
                event, spacing=spacing, max_times=max_times)
            # Send to the distributor process.
            self.pipe_send(self._pipe, event)

    def event_complete(self, event):
        """To mark an event complete.

            Module can invoke this API to mark an event complete.
                a) Next event in sequence will be scheduled.
                b) Event from cache is removed.
                c) Polling for event is stopped.
                d) If the worker dies before event is complete, the
                    event is scheduled to other available workers.

            :param event: Obj of 'Event' class

            Returns: None
        """
        LOG(LOGGER, 'DEBUG', "(event - %s) complete" % (event.identify()))
        event = super(NfpController, self).event_complete(event)
        if self.PROCESS_TYPE == "distributor":
            self._manager.process_events([event])
        else:
            # Send to the distributor process.
            self.pipe_send(self._pipe, event)


def load_nfp_modules(conf, controller):
    """ Load all nfp modules from configured directory. """
    pymodules = []
    try:
        base_module = __import__(conf.nfp_modules_path,
                                 globals(), locals(), ['modules'], -1)
        modules_dir = base_module.__path__[0]
        try:
            files = os.listdir(modules_dir)
            for pyfile in set([f for f in files if f.endswith(".py")]):
                try:
                    pymodule = __import__(conf.nfp_modules_path,
                                          globals(), locals(),
                                          [pyfile[:-3]], -1)
                    pymodule = eval('pymodule.%s' % (pyfile[:-3]))
                    try:
                        pymodule.nfp_module_init(controller, conf)
                        pymodules += [pymodule]
                        LOG(LOGGER, 'DEBUG', "(module - %s) - Initialized" %
                            (identify(pymodule)))
                    except AttributeError:
                        LOG(LOGGER, 'ERROR', "(module - %s) - "
                            "does not implement"
                            "nfp_module_init()" % (identify(pymodule)))
                except ImportError:
                    LOG(LOGGER, 'ERROR',
                        "Failed to import module %s" % (pyfile))
        except OSError:
            LOG(LOGGER, 'ERROR',
                "Failed to read files from %s" % (modules_dir))
    except ImportError:
        LOG(LOGGER, 'ERROR',
            "Failed to import module from path %s" % (conf.nfp_modules_path))

    return pymodules


def controller_init(conf):
    nfp_controller = NfpController(conf)
    nfp_controller.launch(conf.workers)
    # Wait for conf.workers*1 + 1 secs for workers to comeup
    time.sleep(conf.workers * 1 + 1)
    nfp_controller.post_launch()
    return nfp_controller


def nfp_modules_init(conf, nfp_controller):
    nfp_modules = load_nfp_modules(conf, nfp_controller)
    for module in nfp_modules:
        try:
            module.nfp_module_post_init(nfp_controller, conf)
        except AttributeError:
            LOG(LOGGER, 'DEBUG', "(module - %s) - "
                "does not implement"
                "nfp_module_post_init(), ignoring" % (identify(module)))
    return nfp_modules


def main():
    conf = nfp_cfg.init(sys.argv[1:])
    nfp_common.init()
    nfp_controller = controller_init(conf)
    # Init all nfp modules from path configured
    nfp_modules = nfp_modules_init(conf, nfp_controller)
    eventlet.spawn_n(unit_test_task, nfp_modules, nfp_controller, conf)
    # Wait for every exec context to complete
    nfp_controller.wait()


def unit_test_task(modules, controller, conf):
    while True:
        for module in modules:
            module.module_test(controller, conf)
        eventlet.greenthread.sleep(10)
        return
