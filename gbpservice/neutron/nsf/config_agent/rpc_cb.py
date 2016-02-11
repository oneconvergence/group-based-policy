import importlib

from gbpservice.neutron.nsf.core import periodic_task as core_pt
from gbpservice.neutron.nsf.config_agent import RestClientOverUnix as rc
from gbpservice.neutron.nsf.config_agent import loadbalancer as lb
from gbpservice.neutron.nsf.config_agent import firwall as fw
from gbpservice.neutron.nsf.config_agent import vpn as vpn
from gbpservice.neutron.nsf.config_agent import generic as gc


CONFIG_AGENT_MODULES = {'lb': lb, 'fw': fw, 'vpn': vpn, 'gc': gc}


class RpcCallback(core_pt.PeriodicTasks):

    def __init__(self, sc):
        self._sc = sc

    def handle_event(self, ev):
        self._sc.poll_event(ev)

    @core_pt.periodic_task(event='PULL_RPC_NOTIFICATIONS', spacing=1)
    def rpc_pull_event(self, ev):
        rpc_cbs = rc.get('nsf/get_notifications')
        '''
        Message should be of format -->
        {'resource': 'lb/fw/vpn/gc',
         'method': '<Method name>',
         'data': 'kwargs for the method'
        }
        '''
        for rpc_cb in rpc_cbs:
            try:
                mod = CONFIG_AGENT_MODULES[rpc_cb['resource']]
                clazz = getattr(mod, rpc_cb['resource'].title())()
                method = getattr(clazz, rpc_cb['method'])
                method(**rpc_cb['data'])
            except AttributeError:
                print "AttributeError while handling message" %(rpc_cb)
            except Exception as e:
                print "Generic exception (%s) \
                    while handling message (%s)" % (e, rpc_cb)
