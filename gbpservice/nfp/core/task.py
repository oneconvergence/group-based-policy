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

from gbpservice.nfp.core import threadpool as core_tp

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
            'id':id, 'method': func, 'args': args,
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
            th = self.thread_pool.dispatch(job['method'], *job['args'], **job['kwargs'])
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
