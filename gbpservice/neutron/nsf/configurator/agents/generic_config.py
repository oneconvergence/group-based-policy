from gbpservice.neutron.nsf.core.main import Event
from oslo_log import log

LOG = log.getLogger(__name__)
SERVICE = 'gc'

class GenericConfigRpcManager(object):
    def __init__(self, conf, sc):
        pass

    def receive_rpc(self, context):
        pass


class GenericConfigEventHandler():
    def __init__(self, sc):
        self._load_drivers()

    def handle_event(self, ev):
        pass

    def _load_drivers(self):
        # Driver load logic goes here
        pass


def events_init(sc):
    evs = [
        # Events for RPCs coming from orchestrator
        Event(id='CONFIGURE_INTERFACES', handler=GenericConfigEventHandler(
                                                                       sc)),
        Event(id='CLEAR_INTERFACES', handler=GenericConfigEventHandler(sc)),
        Event(id='CONFIGURE_SOURCE_ROUTES', handler=GenericConfigEventHandler(
                                                                       sc)),
        Event(id='DELETE_SOURCE_ROUTES', handler=GenericConfigEventHandler(
                                                                       sc)),
        ]
    sc.register_events(evs)


def register_service_agent(sa, sc, conf):
    service_type = SERVICE
    service_agent = GenericConfigRpcManager(sc, conf)
    sa.register_service_agent(service_type, service_agent)


def agent_init(sa, sc, conf):
    events_init(sc)
    register_service_agent(sa, sc, conf)


def agent_init_complete(sc):
    LOG.info(" Generic Config agent init complete")
