from neutron_lib import exceptions as n_exc
from oslo_log import log as logging
from neutron._i18n import _LI

LOG = logging.getLogger(__name__)


class FWInterfaceDeletionFailed(n_exc.NeutronException):
    message = "Firewall Deletion failed"


class NFPL3Agent(object):
    """
    """
    def __init__(self, conf, sc):
        """
        """
        self._conf = conf
        self._sc = sc
        super(NFPL3Agent, self).__init__()

    def routers_updated(self, context, routers_info):
        """
        routers_info = {'routers': list of active_routers,
                        'interfaces':  interfaces (port details - list of
                        dict),
                        'floating_ips': floating_ips (list of dict),
                        'firewalls': list of firewalls,
                        'operation': operation (remove_router_interface/
                                                add_router_interface)
                        }
        """
        routers_info.update(context=context)
        event = self._sc.new_event(id='ROUTERS_UPDATED',
                                   data=routers_info)
        self._sc.post_event(event)
        LOG.info(_LI("Posted ROUTER - routers=%r updated event"),
                 routers_info['routers'])
