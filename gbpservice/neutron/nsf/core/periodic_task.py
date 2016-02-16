import random
import time
import time
import six

from oslo_config import cfg
from oslo_log import log as logging

LOG = logging.getLogger(__name__)

""" Decorator definition """
def periodic_task(*args, **kwargs):
    def decorator(f):
        f._periodic_task = True
        f._periodic_spacing = kwargs.pop('spacing', 0)
        f._periodic_event = kwargs.pop('event', None)
        f._periodic_last_run = None
        return f

    return decorator

""" Meta class. """
class _PeriodicTasksMeta(type):

    def __init__(cls, names, bases, dict_):
        """Metaclass that allows us to collect decorated periodic tasks."""
        super(_PeriodicTasksMeta, cls).__init__(names, bases, dict_)

        try:
            cls._periodic_tasks = cls._periodic_tasks[:]
        except AttributeError:
            cls._periodic_tasks = []

        try:
            cls._ev_to_periodic_task_map = dict(cls._ev_to_periodic_task_map)
        except AttributeError:
            cls._ev_to_periodic_task_map = {}

        for value in cls.__dict__.values():
            if getattr(value, '_periodic_task', False):
                task = value
                name = task.__name__
                cls._periodic_tasks.append((name, task))
                cls._ev_to_periodic_task_map[task._periodic_event] = task

""" Implements the logic to manage periodicity of events.
    Reference to corresponding decorated methods are returned
    if event has timedout.
"""
@six.add_metaclass(_PeriodicTasksMeta)
class PeriodicTasks(object):

    def __init__(self):
        super(PeriodicTasks, self).__init__()

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

    def _timedout(self, task, event):
        """ Check if event timedout w.r.t its spacing. """
        spacing = task._periodic_spacing
        last_run = event.last_run
        delta = 0

        if last_run:
            delta = last_run + spacing - time.time()
        if delta > 0:
            return None
        event.last_run = self._nearest_boundary(last_run, spacing)
        return event

    def check_timedout(self, event):
        """ Check if event timedout w.r.t its spacing.

            First check if the spacing is set for this event, if
            not then return the event - in this case events timeout
            at the periodicity of polling task.
            If yes, then check if event timedout.
        """
        if event.id not in self._ev_to_periodic_task_map.keys():
            return event
        else:
            task = self._ev_to_periodic_task_map[event.id]
            return self._timedout(task, event)

    def get_periodic_event_handler(self, event):
        """ Get the registered event handler for the event.

            Check if the event has a specific periodic handler
            defined, if then return it.
        """
        if event.id not in self._ev_to_periodic_task_map.keys():
            return None
        return self._ev_to_periodic_task_map[event.id]
