import time

from gbpservice.nfp.core import log as nfp_logging
from gbpservice.nfp.lib import transport

from neutron import context as n_context

LOG = nfp_logging.getLogger(__name__)


def event_init(sc, conf):
    pass


def nfp_module_init(sc, conf):
    event_init(sc, conf)


def nfp_module_post_init(sc, conf):
    try:
        uptime = time.strftime("%c")
        body = {'eventdata': {'uptime': uptime,
                              'module': 'proxy_agent'},
                'eventid': 'NFP_UP_TIME',
                'eventtype': 'NFP_CONTROLLER'}
        context = n_context.Context('dummy_user', 'dummy_tenant')
        transport.send_request_to_configurator(conf,
                                               context,
                                               body,
                                               'CREATE',
                                               network_function_event=True)
    except Exception as e:
        LOG.error("%s" % (e))
