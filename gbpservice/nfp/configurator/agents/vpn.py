import json
import os
import oslo_messaging as messaging
import requests

from gbpservice.nfp.configurator.agents import agent_base
from gbpservice.nfp.configurator.lib import filter as filters_lib
from gbpservice.nfp.configurator.lib import utils
from gbpservice.nfp.configurator.lib import vpn_constants as const
from gbpservice.nfp.core import main

from oslo_log import log as logging
from oslo_messaging import MessagingTimeout

from neutron import context as ctxt


LOG = logging.getLogger(__name__)


class VpnaasRpcSender(filters_lib.Filter):
    """ RPC APIs to VPNaaS Plugin.
    """
    RPC_API_VERSION = '1.0'
    target = messaging.Target(version=RPC_API_VERSION)

    def __init__(self, context, sc):
        self.context = context
        self.sc = sc
        self.notify = agent_base.AgentBaseNotification(sc)
        super(VpnaasRpcSender, self).__init__(None, None)

    def get_vpn_services(self, context, ids=None, filters=None):
        """Get list of vpnservices on this host.
        """
        return self.call(
            context,
            self.make_msg('get_vpn_services', ids=ids, filters=filters))

    def get_vpn_servicecontext(self, context, filters=None):
        """Get list of vpnservice context on this host.
           For IPSEC connections :
                List of vpnservices -->
                lIst of ipsec connections -->
                ike policy & ipsec policy
        """
        return self.call(
            context,
            self.make_msg(
                'get_vpn_servicecontext', filters=filters))

    def get_ipsec_conns(self, context, filters):
        """
        Get list of ipsec conns with filters
        specified.
        """
        return self.call(
            context,
            self.make_msg(
                'get_ipsec_conns',
                filters=filters))

    def update_status(self, context, status):
        """Update local status.

        This method call updates status attribute of
        VPNServices.
        """
        msg = {'receiver': const.NEUTRON,
               'resource': const.SERVICE_TYPE,
               'method': 'update_status',
               'data': {'context': context,
                        'status': status}
               }
        self.notify._notification(msg)

    def ipsec_site_conn_deleted(self, context, resource_id):
        """ Notify VPNaaS plugin about delete of ipsec-site-conn """

        msg = {'receiver': const.NEUTRON,
               'resource': const.SERVICE_TYPE,
               'method': 'ipsec_site_conn_deleted',
               'data': {'context': context,
                        'resource_id': resource_id}
               }
        self.notify._notification(msg)


class VPNaasRpcManager(agent_base.AgentBaseRPCManager):
    """
    APIs for receiving RPC messages from vpn plugin.
    """
    RPC_API_VERSION = '1.0'
    target = messaging.Target(version=RPC_API_VERSION)

    def __init__(self, conf, sc):
        """Instantiates child and parent class objects.

        Passes the instances of core service controller and oslo configuration
        to parent instance in order to provide event enqueue facility for batch
        processing event.

        :param sc: Service Controller object that is used for interfacing
        with core service controller.
        :param conf: Configuration object that is used for configuration
        parameter access.

        """

        super(VPNaasRpcManager, self).__init__(conf, sc)

    def vpnservice_updated(self, context, kwargs):
        arg_dict = {'context': context,
                    'kwargs': kwargs}
        ev = self.sc.new_event(id='VPNSERVICE_UPDATED', data=arg_dict)
        self.sc.post_event(ev)


class VPNaasEventHandler(object):
    """
    Handler class for demultiplexing vpn configuration
    requests from VPNaas Plugin and sending to appropriate driver.
    """
    def __init__(self, sc, drivers):
        self.sc = sc
        self.drivers = drivers
        self.needs_sync = True
        self.context = ctxt.get_admin_context_without_session()
        self.plugin_rpc = VpnaasRpcSender(
            self.context,
            self.sc)

    def _get_driver(self):

        driver_id = const.SERVICE_TYPE
        return self.drivers[driver_id]

    def handle_event(self, ev):
        try:
            msg = ("Worker process with ID: %s starting "
                   "to handle task: %s of topic: %s. "
                   % (os.getpid(), ev.id, const.VPN_GENERIC_CONFIG_RPC_TOPIC))
            LOG.debug(msg)

            driver = self._get_driver()
            self.vpnservice_updated(ev, driver)
        except Exception as err:
            LOG.error("Failed to perform the operation: %s. %s"
                      % (ev.id, str(err).capitalize()))
        finally:
            self.sc.event_done(ev)

    def vpnservice_updated(self, ev, driver):
        context = ev.data.get('context')
        kwargs = ev.data.get('kwargs')
        LOG.debug(_("Vpn service updated from server side"))

        try:
            # in future if the vpnservice service function changes
            # then one should get the below function with getattr function
            driver.vpnservice_updated(context, kwargs)
        except Exception as err:
            LOG.error("Failed to update VPN service. %s"
                      % str(err).capitalize())

        reason = kwargs.get('reason')
        rsrc = kwargs.get('rsrc_type')

        if (reason == 'delete' and rsrc == 'ipsec_site_connection'):
            conn = kwargs['resource']
            resource_id = conn['id']
            self.plugin_rpc.ipsec_site_conn_deleted(context,
                                                    resource_id=resource_id)

    def _get_service_vendor(self, vpn_svc):
        svc_desc = vpn_svc['description']
        tokens = svc_desc.split(';')
        vendor = tokens[5].split('=')[1]
        return vendor

    def _sync_ipsec_conns(self, context, vendor, svc_context):
        try:
            self._get_driver().check_status(context, svc_context)
        except Exception as err:
            msg = ("Failed to sync ipsec connection information. %s."
                   % str(err).capitalize())
            LOG.error(msg)
            pass

    def sync(self, context,  args=None):
        self.needs_sync = True
        s2s_contexts = self.plugin_rpc.get_vpn_servicecontext(context)
        for svc_context in s2s_contexts:
            svc_vendor = self._get_service_vendor(svc_context['service'])
            self._sync_ipsec_conns(context, svc_vendor, svc_context)

    def _resync_ipsec_conns(self, context, vendor, svc_context):
        for site_conn in svc_context['siteconns']:
            conn = site_conn['connection']
            keywords = {'resource': conn}
            try:
                self._get_driver().delete_ipsec_conn(self.context, **keywords)
            except Exception as err:
                LOG.error("Delete ipsec-site-conn: %s failed"
                          " with Exception %s "
                          % (conn['id'], str(err).capitalize()))

            self.plugin_rpc.ipsec_site_conn_deleted(self.context,
                                                    resource_id=conn['id'])


def events_init(sc, drivers):
    evs = [
        main.Event(id='VPNSERVICE_UPDATED',
                   handler=VPNaasEventHandler(sc, drivers))]
    sc.register_events(evs)


def load_drivers(sc):

    ld = utils.ConfiguratorUtils()
    drivers = ld.load_drivers(const.DRIVERS_DIR)
    context = ctxt.get_admin_context_without_session()
    plugin_rpc = VpnaasRpcSender(context, sc)

    for service_type, driver_name in drivers.iteritems():
        driver_obj = driver_name(plugin_rpc)
        drivers[service_type] = driver_obj

    return drivers


def register_service_agent(cm, sc, conf):

    rpcmgr = VPNaasRpcManager(sc, conf)
    cm.register_service_agent(const.SERVICE_TYPE, rpcmgr)


def init_agent(cm, sc, conf):
    try:
        drivers = load_drivers(sc)
    except Exception as err:
        LOG.error("VPNaas failed to load drivers. %s"
                  % (str(err).capitalize()))
        raise err
    else:
        LOG.debug("VPNaas loaded drivers successfully.")

    try:
        events_init(sc, drivers)
    except Exception as err:
        LOG.error("VPNaas Events initialization unsuccessful. %s"
                  % (str(err).capitalize()))
        raise err
    else:
        LOG.debug("VPNaas Events initialization successful.")

    try:
        register_service_agent(cm, sc, conf)
    except Exception as err:
        LOG.error("VPNaas service agent registration unsuccessful. %s"
                  % (str(err).capitalize()))
        raise err
    else:
        LOG.debug("VPNaas service agent registration successful.")

    msg = ("VPN as a Service Module Initialized.")
    LOG.info(msg)


def init_agent_complete(cm, sc, conf):
    LOG.info(" vpn agent init complete")

