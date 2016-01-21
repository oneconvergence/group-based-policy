import os
import sys
import threading
import time

from gbpservice.neutron.nsf.core.main import ServiceController
from gbpservice.neutron.nsf.core.main import Event
from gbpservice.neutron.nsf.core.main import RpcAgent
from gbpservice.neutron.nsf.core.main import RpcManager
from oslo.config import cfg
from gbpservice.neutron.nsf.db import service_manager_db as svc_mgr_db
from gbpservice.neutron.nsf.lib import constants
from neutron.openstack.common import periodic_task

def rpc_init(sc):
    rpcmgr = RpcHandler(cfg.CONF, sc)
    agent = RpcAgent(
            sc,
            host=cfg.CONF.host,
            #topic=constants.SERVICE_MANAGER_RPC_TOPIC,
            topic=constants.VPN_AGENT_TOPIC,
            manager=rpcmgr
            )
    sc.register_rpc_agents([agent])

def events_init(sc):
    evs = [
        Event(id='VPN_SERVICE_UPDATED',data=None,handler=LifeCycleManager()),
        Event(id='VPN_SERVICE_CHECK_STATUS',data=None,handler=LifeCycleManager())]
    sc.register_events(evs)

def module_init(sc):
    events_init(sc)
    rpc_init(sc)

class RpcHandler(RpcManager):
    RPC_API_VERSION = '1.0'
   
    def __init__(self, conf, sc):
        super(RpcHandler, self).__init__()
        self.conf = conf
        self._sc = sc

    def vpnservice_updated(self, context, **kwargs):
        resource = kwargs.get('resource')
        ev = self._sc.event(id='VPN_SERVICE_UPDATED', data=resource, handler=None)
        self._sc.rpc_event(ev, resource['id'])

class LifeCycleManager(object):
    def __init__(self):
        pass

    def handle_event(self, ev):
        print "## Handle Evenet invoked - (%d)" %(threading.current_thread().ident)
        time.sleep(10)
 
