import os
import sys
import threading
import time
import eventlet
eventlet.monkey_patch()
from eventlet import event
from eventlet import greenpool
from eventlet import greenthread
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


def _thread_done(gt, *args, **kwargs):
    kwargs['pool'].thread_done(kwargs['thread'])


""" Descriptor class for green thread """
class Thread(object):

    def __init__(self, thread, pool):
        self.thread = thread
        self.thread.link(_thread_done, pool=pool, thread=self)

    def stop(self):
        self.thread.kill()

    def wait(self):
        return self.thread.wait()

    def link(self, func, *args, **kwargs):
        self.thread.link(func, *args, **kwargs)

    def identify(self):
        return "(%d -> %s)" % (os.getpid(), 'Thread')

""" Abstract class to manage green threads """
class ThreadPool(object):

    def __init__(self, thread_pool_size=10):
        self.pool = greenpool.GreenPool(thread_pool_size)
        self.threads = []

    def dispatch(self, callback, *args, **kwargs):
        """ Invokes the specified function in one of the thread """
        gt = self.pool.spawn(callback, *args, **kwargs)
        th = Thread(gt, self)
        self.threads.append(th)
        return th

    def thread_done(self, thread):
        """ Invoked when thread is complete, remove it from cache """
        self.threads.remove(thread)

    def stop(self):
        """ To stop the thread """
        current = greenthread.getcurrent()

        # Make a copy
        for x in self.threads[:]:
            if x is current:
                # Skipping the current thread
                continue
            try:
                x.stop()
            except Exception as ex:
                LOG.error(_("Exception", ex))

    def wait(self):
        """ Wait for the thread """
        current = greenthread.getcurrent()

        # Make a copy
        for x in self.threads[:]:
            if x is current:
                continue
            try:
                x.wait()
            except eventlet.greenlet.GreenletExit:
                pass
            except Exception as ex:
                LOG.error(_("Exception", ex))
