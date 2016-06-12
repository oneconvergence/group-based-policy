import os
from gbpservice.nfp.core import log as nfp_logging
LOG = nfp_logging.getLogger(__name__)


"""Event Types """
SCHEDULE_EVENT = 'schedule_event'
POLL_EVENT = 'poll_event'
STASH_EVENT = 'stash_event'
EVENT_EXPIRED = 'event_expired'

"""Event Flag """
EVENT_NEW = 'new_event'
EVENT_COMPLETE = 'event_done'
EVENT_ACK = 'event_ack'


def set_event_attrs(f):
    def decorator(self, *args, **kwargs):
        args[0].desc.type = SCHEDULE_EVENT
        args[0].desc.flag = EVENT_NEW
        args[0].desc.pid = os.getpid()
        return f(self, *args, **kwargs)
    return decorator


def get_event_node(f):
    def decorator(*args, **kwargs):
        event = args[1]
        graph = event.graph
        if not graph:
            return
        else:
            kwargs['event_node'] = graph.get_event_node(event)
            return f(*args, **kwargs)
    return decorator


class GraphNode(object):

    def __init__(self, event, p_event=None):
        self.p_link = ()
        self.c_links = []
        self.w_links = []
        self.e_links = []
        self.event = event

        if p_event:
            self.p_link = (p_event.id, p_event.key)

    def __getstate__(self):
        return (self.p_link, self.c_links,
                self.e_links, self.w_links, self.event)

    def __setstate__(self, state):
        (self.p_link, self.c_links, self.e_links,
            self.w_links, self.event) = state

    def add_link(self, event):
        self.c_links.append((event.id, event.key))
        self.w_links.append((event.id, event.key))

    def remove_link(self, event):
        self.e_links.append((event.id, event.key))
        self.w_links.remove((event.id, event.key))

    def remove_c_link(self, event):
        try:
            self.c_links.remove((event.id, event.key))
        except ValueError:
            pass

    def get_c_links(self):
        return self.c_links

    def get_w_links(self):
        return self.w_links

    def get_executed_links(self):
        return self.e_links


class Graph(object):

    def __init__(self, event):
        self.root_node = GraphNode(event)
        self.nodes = {(event.id, event.key): self.root_node}

    def __getstate__(self):
        return self.root_node, self.nodes

    def __setstate__(self, state):
        self.root_node, self.nodes = state

    def add_node(self, event, p_event):
        node = GraphNode(event, p_event)
        self.nodes.update({(event.id, event.key): node})
        p_node = self.nodes.get((p_event.id, p_event.key))
        p_node.add_link(event)
        event.set_fields(graph=self)

    def remove_node(self, node):
        p_node = self.nodes.get(node.p_link)
        if p_node:
            p_node.remove_link(node.event)
        return p_node

    def unlink_node(self, node):
        p_node = self.nodes.get(node.p_link)
        if p_node:
            p_node.remove_c_link(node.event)

    def get_pending_leaf_nodes(self, node):
        c_links = node.get_c_links()
        c_nodes = []
        for link in c_links:
            c_nodes.append(self.nodes[link])

        return c_nodes

    def waiting_events(self, node):
        return len(node.get_w_links())

    def get_leaf_events(self, event):
        events = []
        node = self.nodes[(event.id, event.key)]
        e_links = node.get_executed_links()
        for link in e_links:
            node = self.nodes[link]
            events.append(node.event)
        return events

    def get_event_node(self, event):
        return self.nodes.get((event.id, event.key), None)


class Executor(object):

    def __init__(self, manager, graph):
        self.manager = manager
        self.graph = graph

    def run(self, node=None):
        sequenced = self._scheduled_new_event(node.event, dispatch=False)
        if sequenced:
            self.graph.unlink_node(node)
            return

        l_nodes = self.graph.get_pending_leaf_nodes(node)

        if not l_nodes:
            if not self.graph.waiting_events(node):
                LOG.info("Event : %s triggered" %(node.event.id))
                self._scheduled_new_event(node.event)
                self.graph.unlink_node(node)

            # Set here after dispatching so that executor doesnt get
            # send to worker
            # setattr(node.event, 'executor', self)

        if l_nodes:
            for l_node in l_nodes:
                self.run(node=l_node)

    @set_event_attrs
    def _scheduled_new_event(self, event, dispatch=True):
        return self.manager._scheduled_new_event(event, dispatch=dispatch)

    def complete(self, node):
        LOG.info("Event : %s completed" %(node.event.id))
        p_node = self.graph.remove_node(node)
        if p_node:
            self.run(node=p_node)


@get_event_node
def execute(manager, event, event_node=None):
    executor = Executor(manager, event.graph)
    executor.run(node=event_node)


@get_event_node
def event_complete(manager, event, event_node=None):
    executor = Executor(manager, event.graph)
    executor.complete(event_node)
