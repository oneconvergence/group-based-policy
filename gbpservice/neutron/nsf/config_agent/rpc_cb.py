import importlib

from gbpservice.neutron.nsf.core import periodic_task as core_pt
from gbpservice.neutron.nsf.config_agent import RestClientOverUnix as rc
from gbpservice.neutron.nsf.config_agent import loadbalancer as lb
from gbpservice.neutron.nsf.config_agent import firewall as fw
from gbpservice.neutron.nsf.config_agent import vpn as vpn
from gbpservice.neutron.nsf.config_agent import generic as gc


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
            clazz = getattr(mod, 'generic'.title())()
            method = getattr(clazz, rpc_cb['method'])
            method(rpc_cb['resource'], **rpc_cb['kwargs'])
        else:
            mod = CONFIG_AGENT_MODULES[rpc_cb['resource']]
            clazz = getattr(mod, rpc_cb['resource'].title())()
            method = getattr(clazz, rpc_cb['method'])
            method(**rpc_cb['kwargs'])

    @core_pt.periodic_task(event='PULL_RPC_NOTIFICATIONS', spacing=1)
    def rpc_pull_event(self, ev):
        rpc_cbs_data = rc.get('nsf/get_notifications')
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
