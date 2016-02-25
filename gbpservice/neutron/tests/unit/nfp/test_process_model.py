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
#  under the License.

from gbpservice.nfp.core import cfg as nfp_config
from gbpservice.nfp.core import common as nfp_common
from gbpservice.nfp.core import main
import mock
import multiprocessing
from neutron.agent.common import config as n_config
import os
from oslo_config import cfg as oslo_config
from oslo_log import log as oslo_logging
import sys
import time
import unittest
LOG = oslo_logging.getLogger(__name__)


class Test_Process_Model(unittest.TestCase):

    @mock.patch(
        'multiprocessing.queues.Queue.put'
    )
    def test_event_create(self, mock_put):
        self.initialize_process_model()
        event = self.sc.new_event(
            id='DUMMY_SERVICE_EVENT1', data=self.service1,
            binding_key=self.service1['id'],
            key=self.service1['id'], serialize=True
        )
        self.sc.post_event(event)
        self.assertIsNotNone(event.worker_attached)
        mock_put.assert_called_once_with(event)

    @mock.patch(
        'multiprocessing.queues.Queue.put'
    )
    def test_events_with_same_binding_keys(self, mock_put):
        self.initialize_process_model()
        event1 = self.sc.new_event(
            id='DUMMY_SERVICE_EVENT1', data=self.service1,
            binding_key=self.service1['tenant'],
            key=self.service1['id'], serialize=True
        )
        event2 = self.sc.new_event(
            id='DUMMY_SERVICE_EVENT2', data=self.service1,
            binding_key=self.service1['tenant'],
            key=self.service1['id'], serialize=True
        )
        self.sc.post_event(event1)
        self.sc.post_event(event2)
        self.assertIsNotNone(event1.worker_attached)
        self.assertIsNotNone(event2.worker_attached)
        self.assertEqual(event1.worker_attached, event2.worker_attached)
        self.assertEqual(mock_put.call_count, 2)

    def test_serialize_events(self):
        self.initialize_process_model()
        event1 = self.sc.new_event(
            id='DUMMY_SERVICE_EVENT7', data=self.service1,
            binding_key=self.service1['tenant'],
            key=self.service1['id'], serialize=True
        )
        event2 = self.sc.new_event(
            id='DUMMY_SERVICE_EVENT8', data=self.service1,
            binding_key=self.service1['tenant'],
            key=self.service1['id'], serialize=True
        )
        self.sc.post_event(event1)
        time.sleep(5)
        self.sc.post_event(event2)
        time.sleep(3)
        event2_on_sequencer_map = self.sc._event.wait(20)
        self.assertTrue(event2_on_sequencer_map)

    def test_serialize_event_dequeued(self):
        self.initialize_process_model()
        event1 = self.sc.new_event(
            id='DUMMY_SERVICE_EVENT9', data=self.service1,
            binding_key=self.service1['tenant'],
            key=self.service1['id'], serialize=True
        )
        event2 = self.sc.new_event(
            id='DUMMY_SERVICE_EVENT8', data=self.service1,
            binding_key=self.service1['tenant'],
            key=self.service1['id'], serialize=True
        )
        self.sc.post_event(event1)
        time.sleep(5)
        self.sc.post_event(event2)
        time.sleep(3)
        event2_dequeued = self.sc._event.wait(20)
        self.assertTrue(event2_dequeued)

    @mock.patch(
        'multiprocessing.queues.Queue.put'
    )
    def test_events_with_no_binding_key(self, mock_put):
        self.initialize_process_model()
        event1 = self.sc.new_event(
            id='DUMMY_SERVICE_EVENT1', data=self.service1,
            key=self.service1['id'], serialize=False
        )
        event2 = self.sc.new_event(
            id='DUMMY_SERVICE_EVENT2', data=self.service1,
            key=self.service1['id'], serialize=False
        )
        self.sc.post_event(event1)
        self.sc.post_event(event2)
        self.assertIsNotNone(event1.worker_attached)
        self.assertIsNotNone(event2.worker_attached)
        self.assertNotEqual(event1.worker_attached, event2.worker_attached)
        self.assertEqual(mock_put.call_count, 2)

    @mock.patch(
        'multiprocessing.queues.Queue.put'
    )
    def test_loadbalancing_events(self, mock_put):
        self.initialize_process_model()
        event1 = self.sc.new_event(
            id='SERVICE_CREATE', data=self.service1,
            binding_key=self.service1['id'],
            key=self.service1['id'], serialize=False
        )
        self.sc.post_event(event1)
        count = 0
        for worker in self.sc._workers:
            if event1.worker_attached == worker[0].pid:
                rrid_event1 = count
                break
            count = count + 1

        event2 = self.sc.new_event(
            id='SERVICE_CREATE', data=self.service2,
            binding_key=self.service2['id'],
            key=self.service2['id'], serialize=False
        )
        self.sc.post_event(event2)
        if rrid_event1 + 1 == len(self.sc._workers):
            self.assertEqual(event2.worker_attached,
                             self.sc._workers[0][0].pid)
        else:
            self.assertEqual(
                event2.worker_attached,
                self.sc._workers[rrid_event1 + 1][0].pid
            )
        self.assertEqual(mock_put.call_count, 2)

    @mock.patch('gbpservice.nfp.core.main.EventSequencer.add')
    def test_sequencer_put_serialize_false(self, mock_sequencer):
        self.initialize_process_model()
        event1 = self.mock_event(
            id='SERVICE_CREATE', data=self.service1,
            binding_key=self.service1['id'],
            key=self.service1['id'], serialize=False,
            worker_attached=self.sc._workers[0][0].pid
        )
        sequenced_event1 = self.sc.sequencer_put_event(event1)
        self.assertEqual(mock_sequencer.call_count, 0)
        self.assertEqual(sequenced_event1, event1)

    @mock.patch('gbpservice.nfp.core.main.EventSequencer.add')
    def test_sequencer_put_serialze_true(self, mock_sequencer):
        self.initialize_process_model()
        event1 = self.mock_event(
            id='SERVICE_CREATE', data=self.service1,
            binding_key=self.service1['id'],
            key=self.service1['id'], serialize=True,
            worker_attached=self.sc._workers[0][0].pid
        )
        mock_sequencer.return_value = True
        sequenced_event1 = self.sc.sequencer_put_event(event1)
        mock_sequencer.assert_called_once_with(event1)
        self.assertEqual(sequenced_event1, None)
        mock_sequencer.return_value = False
        sequenced_event1 = self.sc.sequencer_put_event(event1)
        self.assertEqual(sequenced_event1, event1)

    @mock.patch('gbpservice.nfp.core.event.EventSequencer')
    def test_EventSequencer_add(self, mocked_sequencer):
        self.initialize_process_model()
        event1 = self.mock_event(
            id='SERVICE_CREATE', data=self.service1,
            binding_key=self.service1['id'],
            key=self.service1['id'], serialize=True,
            worker_attached=self.sc._workers[0][0].pid
        )
        mocked_sequencer_map = mock.Mock()
        mocked_sequencer._sequencer_map = mocked_sequencer_map
        mocked_sequencer_map = {}
        self.assertEqual(self.EventSequencer.add(event1), False)
        mocked_sequencer_map = self.create_sequencer_map(
            self.sc._workers[0][0].pid,
            self.service1['id']
        )
        self.assertEqual(self.EventSequencer.add(event1), True)

    def test_handle_event_on_queue(self):
        self.initialize_process_model()
        event1 = self.sc.new_event(
            id='DUMMY_SERVICE_EVENT1', data=self.service1,
            binding_key=self.service1['id'],
            key=self.service1['id'], serialize=True
        )
        self.sc.post_event(event1)
        time.sleep(3)
        handle_event_invoked = self.sc._event.wait(5)
        self.assertTrue(handle_event_invoked)

    def test_poll_handle_event(self):
        self.initialize_process_model()
        ev = self.sc.new_event(
            id='DUMMY_SERVICE_EVENT2', data=self.service1,
            binding_key=self.service1['id'],
            key=self.service1['id'], serialize=True
        )
        self.sc.post_event(ev)
        time.sleep(3)
        poll_handle_event_invoked = self.sc._event.wait(10)
        self.assertTrue(poll_handle_event_invoked)

    def test_poll_event_maxtimes(self):
        self.initialize_process_model()
        ev = self.sc.new_event(
            id='DUMMY_SERVICE_EVENT3', data=self.service1,
            binding_key=self.service1['id'],
            key=self.service1['id'], serialize=True
        )
        self.sc.post_event(ev)
        time.sleep(3)
        event_polled_maxtimes = self.sc._event.wait(50)
        self.assertTrue(event_polled_maxtimes)

    def test_poll_event_done(self):
        self.initialize_process_model()
        ev = self.sc.new_event(
            id='DUMMY_SERVICE_EVENT4', data=self.service1,
            binding_key=self.service1['id'],
            key=self.service1['id'], serialize=True
        )
        self.sc.post_event(ev)
        time.sleep(3)
        sc_event_set = self.sc._event.wait(30)
        self.assertFalse(sc_event_set)

    '''def test_periodic_method_withspacing_10(self):
        self.initialize_process_model()
        ev = self.sc.new_event(
            id='DUMMY_SERVICE_EVENT5', data=self.service1,
            binding_key=self.service1['id'],
            key=self.service1['id'], serialize=True)
        self.sc.post_event(ev)
        time.sleep(3)
        called_with_correct_spacing = self.sc._event.wait(30)
        self.assertTrue(called_with_correct_spacing)

    def test_periodic_method_withspacing_20(self):
        self.initialize_process_model()
        ev = self.sc.new_event(
            id='DUMMY_SERVICE_EVENT6', data=self.service1,
            binding_key=self.service1['id'],
            key=self.service1['id'], serialize=True)
        self.sc.post_event(ev)
        time.sleep(3)
        called_with_correct_spacing = self.sc._event.wait(30)
        self.assertTrue(called_with_correct_spacing)'''

    def test_worker_process_initilized(self):
        self.initialize_process_model()
        workers = self.sc._workers
        test_process = multiprocessing.Process()
        self.assertEqual(len(workers), 4)
        for worker in workers:
            self.assertTrue(type(worker[0]), type(test_process))

    def test_modules_import_nonexisting_path(self):
        modules_dir = 'this.path.does.not.exist'
        import_error_seen = False
        try:
            self.initialize_process_model(modules_dir)
        except ImportError:
            import_error_seen = True
        self.assertTrue(import_error_seen)

    def test_modules_import_path_format(self):
        modules_dir = 'gbpservice/neutron/tests/unit/nfp/EventHandler'
        import_error_seen = False
        try:
            self.initialize_process_model(modules_dir)
        except ImportError:
            import_error_seen = True
        self.assertTrue(import_error_seen)

    @mock.patch('gbpservice.nfp.core.main.LOG')
    def test_no_modules_init(self, mock_log):
        modules_dir = 'gbpservice.neutron.tests.unit.nfp.DummyModule'
        self.initialize_process_model(modules_dir)
        modules = self.sc._modules
        identify = nfp_common.identify
        for module in modules:
            mock_log.error.assert_called_with(
                _("Module %s does not implement"
                  "module_init() method - skipping"
                   % (identify(module))))
        self.assertEqual(len(self.sc._workers), 4)

    def create_sequencer_map(self, worker_attached, binding_key):
        sequencer_map = {}
        sequencer_map[worker_attached] = {}
        mapp = sequencer_map[worker_attached]
        mapp[binding_key] = {'in_use': True, 'queue': []}
        return sequencer_map

    def mock_event(self, **kwargs):
        event = self.sc.new_event(**kwargs)
        event.poll_event = \
            kwargs.get('poll_event') if 'poll_event' in kwargs else None
        event.worker_attached = \
            kwargs.get(
                'worker_attached') if 'worker_attached' in kwargs else None
        event.last_run = kwargs.get(
            'last_run') if 'last_run' in kwargs else None
        event.max_times = kwargs.get(
            'max_times') if 'max_times' in kwargs else -1
        return event

    def modules_import(self):
        modules = []
        modules_dir = 'gbpservice.neutron.tests.unit.nfp.EventHandler'
        base_module = __import__(
            modules_dir,
            globals(), locals(),
            ['modules'], -1
        )
        modules_dir_test = base_module.__path__[0]
        syspath = sys.path
        sys.path = [modules_dir_test] + syspath
        try:
            files = os.listdir(modules_dir_test)
        except OSError:
            #LOG.error(_("Failed to read files.."))
            files = []
        for fname in files:
            if fname.endswith(".py") and fname != '__init__.py':
                module = __import__(
                    modules_dir,
                    globals(), locals(),
                    [fname[:-3]], -1
                )
                modules += [__import__(fname[:-3])]
        sys.path = syspath
        return modules

    def initialize_process_model(
        self, modules_dir='gbpservice.neutron.tests.unit.nfp.EventHandler',
        no_of_workers=4
    ):
        oslo_config.CONF.workers = no_of_workers
        oslo_config.CONF.modules_dir = modules_dir
        modules = main.modules_import()
        self._modules = modules
        self.sc = main.Controller(oslo_config.CONF, modules)
        self.EventSequencer = main.EventSequencer(self.sc)
        self.sc.start()

    def setUp(self):
        oslo_config.CONF.register_opts(nfp_config.OPTS)
        #modules = self.modules_import()
        n_config.register_interface_driver_opts_helper(oslo_config.CONF)
        n_config.register_agent_state_opts_helper(oslo_config.CONF)
        n_config.register_root_helper(oslo_config.CONF)
        self.service1 = {
            'id': 'sc2f2b13-e284-44b1-9d9a-2597e216271a',
            'tenant': '40af8c0695dd49b7a4980bd1b47e1a1b',
            'servicechain': 'sc2f2b13-e284-44b1-9d9a-2597e2161c',
            'servicefunction': 'sf2f2b13-e284-44b1-9d9a-2597e216561d',
            'vip_id': '13948da4-8dd9-44c6-adef-03a6d8063daa',
            'service_vendor': 'haproxy',
            'service_type': 'loadbalancer',
            'ip': '192.168.20.199'
        }
        self.service2 = {
            'id': 'sc2f2b13-e284-44b1-9d9a-2597e216272a',
            'tenant': '40af8c0695dd49b7a4980bd1b47e1a2b',
            'servicechain': 'sc2f2b13-e284-44b1-9d9a-2597e216562c',
            'servicefunction': 'sf2f2b13-e284-44b1-9d9a-2597e216562d',
            'mac_address': 'fa:16:3e:3f:93:05',
            'service_vendor': 'vyos',
            'service_type': 'firewall',
            'ip': '192.168.20.197'
        }
        n_config.setup_logging()
        self._conf = oslo_config.CONF