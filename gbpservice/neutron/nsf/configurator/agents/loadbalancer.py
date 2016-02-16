from gbpservice.neutron.nsf.core.main import Event
from oslo_log import log

LOG = log.getLogger(__name__)
SERVICE = 'loadbalancer'


class LBaasRpcManager(object):
    def __init__(self, conf, sc):
        pass

    def receive_rpc(self, context):
        pass


class LBaasEventHandler():
    def __init__(self, sc):
        self._load_drivers()

    def handle_event(self, ev):
        pass

    def _load_drivers(self):
        # Driver load logic goes here
        pass


def events_init(sc):
    evs = [
        # Events for LBaaS standard RPCs coming from LBaaS Plugin
        Event(id='CREATE_VIP', handler=LBaasEventHandler(sc)),
        Event(id='UPDATE_VIP', handler=LBaasEventHandler(sc)),
        Event(id='DELETE_VIP', handler=LBaasEventHandler(sc)),

        Event(id='CREATE_POOL', handler=LBaasEventHandler(sc)),
        Event(id='UPDATE_POOL', handler=LBaasEventHandler(sc)),
        Event(id='DELETE_POOL', handler=LBaasEventHandler(sc)),

        Event(id='CREATE_MEMBER', handler=LBaasEventHandler(sc)),
        Event(id='UPDATE_MEMBER', handler=LBaasEventHandler(sc)),
        Event(id='DELETE_MEMBER', handler=LBaasEventHandler(sc)),

        Event(id='CREATE_POOL_HEALTH_MONITOR', handler=LBaasEventHandler(sc)),
        Event(id='UPDATE_POOL_HEALTH_MONITOR', handler=LBaasEventHandler(sc)),
        Event(id='DELETE_POOL_HEALTH_MONITOR', handler=LBaasEventHandler(sc)),
        Event(id='AGENT_UPDATED', handler=LBaasEventHandler(sc)),

        # Poll Events triggered internally
        Event(id='COLLECT_STATS', handler=LBaasEventHandler(sc))
        ]
    sc.register_events(evs)


def register_service_agent(sa, sc, conf):
    service_type = SERVICE
    service_agent = LBaasRpcManager(sc, conf)
    sa.register_service_agent(service_type, service_agent)


def agent_init(sa, sc, conf):
    events_init(sc)
    register_service_agent(sa, sc, conf)


def agent_init_complete(sc):
    LOG.info(" loadbalancer agent init complete")
