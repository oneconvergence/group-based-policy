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

import os
import sys

""" Implements simple roundrobin loadbalancing algo.

    When invoked by caller, returns the next worker in
    the queue.
"""


class RoundRobin(object):

    def __init__(self, workers):
        self._workers = workers
        self._rridx = 0
        self._rrsize = len(self._workers)

    def _rr(self):
        item = self._workers[self._rridx]
        self._rridx = (self._rridx + 1) % (self._rrsize)
        return item

    def get(self, rsrcid):
        return self._rr()

""" Implements round robin algo with stickiness to a worker.

    All the events with same rsrcid, are scheduled to same
    worker. Maintains the map in dict.
"""


class StickyRoundRobin(object):

    def __init__(self, workers):
        self._workers = workers
        self._assoc = {}
        self._rridx = 0
        self._rrsize = len(self._workers)

    def _remove_assoc(self, wpid):
        assoc_elem = None
        print self._assoc
        
        for w in self._workers :
            if w[0].pid == wpid :
                self._workers.remove(w)
                break
    

        for key, value in self._assoc.iteritems() :
            if value[0].pid == wpid :
                del  self._assoc[key]
                break

        print "!!!!!!!! %d is Removed from ASSOC "
        print "Worker structure :"

        print self._assoc

    def _rr(self):
        item = self._workers[self._rridx]
        self._rridx = (self._rridx + 1) % (len(self._workers))
        return item

    def get(self, rsrcid):
        if not rsrcid:
            print "@@@@@@ DOING PLAIN ROUND ROBIN @@@@@@@"
            return self._rr()

        if rsrcid in self._assoc.keys():
            worker = self._assoc[rsrcid]
        else:
            print "@@@@@@@ RSRCID %s not in ASSOC MAP" %(rsrcid)
            worker = self._rr()
            self._assoc[rsrcid] = worker
        return worker
