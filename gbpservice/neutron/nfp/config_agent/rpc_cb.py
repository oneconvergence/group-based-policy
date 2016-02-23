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

import importlib
from gbpservice.neutron.nfp.core import periodic_task as core_pt
from gbpservice.neutron.nfp.config_agent import RestClientOverUnix as rc
from gbpservice.neutron.nfp.config_agent import loadbalancer as lb
from gbpservice.neutron.nfp.config_agent import firewall as fw
from gbpservice.neutron.nfp.config_agent import vpn as vpn
from gbpservice.neutron.nfp.config_agent import generic as gc

CONFIG_AGENT_MODULES = {'loadbalancer': lb,
                        'firewall': fw,
                        'vpn': vpn,
                        'generic': gc}


class RpcCallback(core_pt.PeriodicTasks):

    def __init__(self, sc):
        self._sc = sc

    def handle_event(self, ev):
        self._sc.poll_event(ev)

    def _method_handler(self, rpc_cb):
        if rpc_cb['receiver'] == 'orchestrator':
            mod = CONFIG_AGENT_MODULES['generic']
            mod_method = getattr(mod, rpc_cb['method'])
            mod_method(rpc_cb['resource'], **rpc_cb['kwargs'])
        else:
            mod = CONFIG_AGENT_MODULES[rpc_cb['resource']]
            mod_method = getattr(mod, rpc_cb['method'])
            mod_method(**rpc_cb['kwargs'])

    @core_pt.periodic_task(event='PULL_RPC_NOTIFICATIONS', spacing=1)
    def rpc_pull_event(self, ev):
        rpc_cbs_data = rc.get('nfp/get_notifications')
        '''
        {response_data : [
            {'receiver': <neutron/orchestrator>,
             'resource': <firewall/vpn/loadbalancer/generic>,
             'method': <notification method name>,
             'kwargs': <notification method arguments>
        },
        ]}
        '''
        rpc_cbs = rpc_cbs_data['response_data']
        for rpc_cb in rpc_cbs:
            try:
                self._method_handler(rpc_cb)
            except AttributeError:
                print "AttributeError while handling message" % (rpc_cb)
            except Exception as e:
                print "Generic exception (%s) \
                    while handling message (%s)" % (e, rpc_cb)