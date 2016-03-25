from oslo_log import log as logging
from gbpservice.nfp.core.event import Event
from gbpservice.nfp.proxy_agent.notifications import pull

LOG = logging.getLogger(__name__)

def events_init(sc, conf):
    evs = [
        Event(id='PULL_NOTIFICATIONS', handler=pull.PullNotification(sc, conf))]
    sc.register_events(evs)

def nfp_module_init(sc, conf):
    events_init(sc, conf)

def nfp_module_post_init(sc, conf):
    ev = sc.new_event(id='PULL_NOTIFICATIONS',
                      key='PULL_NOTIFICATIONS')
    sc.post_event(ev)
