from gbpservice.neutron.nsf.core.main import Event
from oslo_log import log

LOG = log.getLogger(__name__)

class FwaasRpcHandler(object):
    def __init__(self, sc, conf, rpc_mgr):
        self._sc = sc
        self._conf = conf
        self._rpc_mgr = rpc_mgr

    def rpc_handler(self, context, config):
        method = context['operation'] + config['resource']
        self._rpc_mgr.method(**config['kwargs'])

class FWaasRpcManager(object):
    def __init__(self, sc, conf):
        self._sc = sc
        self._conf = conf
    
    def create_firewall(self, context, firewall, host):
        LOG.debug("FwaasRpcReceiver received Create Firewall request.")
        arg_dict = {'context': context,
                    'firewall': firewall,
                    'host': host}
        ev = self._sc.event(id='CREATE_FIREWALL', data=arg_dict)
        self._sc.rpc_event(ev)

    def update_firewall(self, context, firewall, host):
        LOG.debug("FwaasRpcReceiver received Update Firewall request.")
        arg_dict = {'context': context,
                    'firewall': firewall,
                    'host': host}
        ev = self._sc.event(id='UPDATE_FIREWALL', data=arg_dict)
        self._sc.rpc_event(ev)

    def delete_firewall(self, context, firewall, host):
        LOG.debug("FwaasRpcReceiver received Delete Firewall request.")
        arg_dict = {'context': context,
                    'firewall': firewall,
                    'host': host}
        ev = self._sc.event(id='DELETE_FIREWALL', data=arg_dict)
        self._sc.rpc_event(ev)


class FWaasEventHandler():
    def __init__(self, sc):
        self._load_drivers()

    def handle_event(self, ev):
        pass

    def _load_drivers(self):
        # Driver load logic goes here
        pass


def events_init(sc):
    evs = [
        # Events for FWaaS standard RPCs coming from FWaaS Plugin
        Event(id='CREATE_FIREWALL', handler=FWaasEventHandler(sc)),
        Event(id='UPDATE_FIREWALL', handler=FWaasEventHandler(sc)),
        Event(id='DELETE_FIREWALL', handler=FWaasEventHandler(sc)),
        ]
    sc.register_events(evs)


def register_service_agent(sa, sc, conf):
    service_type = 'firewall'
    rpc_mgr = FWaasRpcManager(sc, conf)
    rpc_handler = FwaasRpcHandler(sc, conf, rpc_mgr)
    sa.register_service_agent(service_type, rpc_handler)


def init_agent(sa, sc, conf):
    events_init(sc)
    register_service_agent(sa, sc, conf)


def init_agent_complete(sa, sc, conf):
    LOG.info(" firewall agent init complete")
