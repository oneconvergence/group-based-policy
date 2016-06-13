from gbpservice.nfp.core import threadpool as core_tp
from gbpservice.nfp.core import log as nfp_logging

LOG = nfp_logging.getLogger(__name__)


class InUse(Exception):

    """Exception raised when same executor is fired twice or jobs
       added after executor is fired.
    """
    pass


def check_in_use(f):
    def wrapped(self, *args, **kwargs):
        if self.fired:
            raise InUse("Executor in use")
        return f(self, *args, **kwargs)
    return wrapped

class TaskExecutor(object):

    def __init__(self, jobs=0):
        if not jobs:
            self.thread_pool = core_tp.ThreadPool()
        else:
            self.thread_pool = core_tp.ThreadPool(thread_pool_size=jobs)

        self.pipe_line = []
        self.fired = False

    @check_in_use
    def add_job(self, id, func, *args, **kwargs):
        result_store = kwargs.pop('result_store', None)

        job = {
            'id': id, 'method': func, 'args': args,
            'kwargs': kwargs}

        if result_store is not None:
            job.update({'result_store': result_store})

        self.pipe_line.append(job)

    def _complete(self):
        self.pipe_line = []
        self.fired = False

    @check_in_use
    def fire(self):
        self.fired = True
        for job in self.pipe_line:
            th = self.thread_pool.dispatch(
                job['method'], *job['args'], **job['kwargs'])
            job['thread'] = th

        for job in self.pipe_line:
            result = job['thread'].wait()
            job.pop('thread')
            job['result'] = result
            if 'result_store' in job.keys():
                job['result_store']['result'] = result

        done_jobs = self.pipe_line[:]
        self._complete()
        return done_jobs


def set_node(f):
    def decorator(self, *args, **kwargs):
        node = kwargs.get('node')
        event = kwargs.get('event')
        if not node:
            if not event:
                kwargs['node'] = self.graph.root_node
            else:
                kwargs['node'] = self.graph.get_node(event)
        return f(self, *args, **kwargs)
    return decorator

def get_event_graph_node(f):
    def decorator(self, *args, **kwargs):
        event = args[0]
        node = self.graph.get_node(event)
        kwargs['node'] = node
        return f(self, *args, **kwargs)
    return decorator

class EventGraphExecutor(object):
    def __init__(self, manager, graph):
        self.manager = manager
        self.graph = graph

    @set_node
    def run(self, event=None, node=None):
        if self.manager.schedule_graph_event(node.event, self.graph, dispatch=False):
            return self.graph.unlink_node(node)

        l_nodes = self.graph.get_pending_leaf_nodes(node)

        if not l_nodes:
            if not self.graph.waiting_events(node):
                LOG.info("Event : %s triggered" %(node.event))
                self.manager.schedule_graph_event(node.event, self.graph)
                self.graph.unlink_node(node)

        if l_nodes:
            for l_node in l_nodes:
                self.run(node=l_node)

    @get_event_graph_node
    def complete(self, event, result, node=None):
        LOG.info("Event : %s completed" %(node.event))
        node.result = result
        p_node = self.graph.remove_node(node)
        if p_node:
            self.run(node=p_node)
