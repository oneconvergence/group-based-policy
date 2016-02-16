from gbpservice.neutron.nsf.core.main import Event
from oslo_log import log

LOG = log.getLogger(__name__)
SERVICE = 'vpn'

class VPNaasRpcManager(object):
    def __init__(self, sc, conf):
        pass

    def receive_rpc(self, context):
        pass


class VPNaasEventHandler():
    def __init__(self, sc):
        self._load_drivers()

    def handle_event(self, ev):
        pass

    def _load_drivers(self):
        # Driver load logic goes here
        pass


def events_init(sc):
    evs = [
        # Events for VPNaaS standard RPCs coming from VPNaaS Plugin
        Event(id='VPNSERVICE_UPDATED', handler=VPNaasEventHandler(sc)),
        ]
    sc.register_events(evs)


def register_service_agent(sa, sc, conf):
    service_type = SERVICE
    service_agent = VPNaasRpcManager(sc, conf)
    sa.register_service_agent(service_type, service_agent)


def agent_init(sa, sc, conf):
    events_init(sc)
    register_service_agent(sa, sc, conf)


def agent_init_complete(sc):
    LOG.info(" vpn agent init complete")
