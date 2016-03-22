#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.


from gbpservice.nfp.configurator.agents import agent_base
from gbpservice.nfp.configurator.lib import data_filter
from gbpservice.nfp.configurator.lib import utils
from gbpservice.nfp.configurator.lib import vpn_constants as const
from gbpservice.nfp.core import main

import os
import oslo_messaging as messaging
from oslo_messaging import MessagingTimeout
from oslo_log import log as logging


LOG = logging.getLogger(__name__)

""" Implements VPNaas response path to Neutron plugin.

Methods of this class are invoked by the VPNaasEventHandler class
for sending response from driver to the VPNaas Neutron plugin.

"""


class VpnaasRpcSender(data_filter.Filter):
    RPC_API_VERSION = '1.0'
    target = messaging.Target(version=RPC_API_VERSION)

    def __init__(self, sc):
        self._sc = sc
        self._notify = agent_base.AgentBaseNotification(sc)
        super(VpnaasRpcSender, self).__init__(None, None)

    def get_vpn_services(self, context, ids=None, filters=None):
        """Gets list of vpnservices for tenant.
        :param context: dictionary which holds details of vpn service type like
            For IPSEC connections :
                List of vpnservices
                lIst of ipsec connections
                ike policy & ipsec policy.
        :param ids: based on which the filter library extracts the data.
        :param filter: based on which the filter library extracts the data.

        Returns: Dictionary of vpn service type which matches with the filters.
        """
        return self.call(
            context,
            self.make_msg('get_vpn_services', ids=ids, filters=filters))

    def get_vpn_servicecontext(self, context, filters=None):
        """Get list of vpnservice context on this host.
        :param context: dictionary which holds details of vpn service type like
            For IPSEC connections :
                List of vpnservices
                lIst of ipsec connections
                ike policy & ipsec policy.
        :param filter: based on which the filter library extracts the data
        from context dictionary.

        Returns: dictionary of vpnservice
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

""" Implements VPNaasRpcManager class which receives requests
    from Configurator to Agent.

Methods of this class are invoked by the configurator. Events are
created according to the requests received and enqueued to worker queues.

"""


class VPNaasRpcManager(agent_base.AgentBaseRPCManager):

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
        """Registers the VPNaas plugin events to update the vpn configurations.

        :param context: dictionary, confined to the specific service type.
        :param kwargs: dictionary, confined to the specific operation type.

        Returns: None
        """
        arg_dict = {'context': context,
                    'kwargs': kwargs}
        ev = self._sc.new_event(id='VPNSERVICE_UPDATED', data=arg_dict)
        self._sc.post_event(ev)

"""
Handler class to invoke the vpn driver methods.
For every event that gets invoked from worker process lands over here
to make a call to the driver methods.
"""


class VPNaasEventHandler(object):

    def __init__(self, sc, drivers):
        """ Instantiates class object.

        :param sc: Service Controller object that is used to communicate
        with process model core file.
        :param drivers: dictionary of driver name to object mapping

        """
        self._sc = sc
        self._drivers = drivers
        self._needs_sync = True
        self._plugin_rpc = VpnaasRpcSender(self._sc)

    def _get_driver(self):

        driver_id = const.SERVICE_TYPE
        return self._drivers[driver_id]

    def handle_event(self, ev):
        """
        Demultiplexes the vpn request to appropriate  driver methods.

        :param ev: event object sent from the process model.

        Returns: None
        """
        if ev.id == 'SYNC_UPDATE':
            self._sc.poll_event(ev)

        if ev.id == 'VPNSERVICE_UPDATED':
            try:
                msg = ("Worker process with ID: %s starting "
                       "to handle task: %s of topic: %s. "
                       % (os.getpid(),
                          ev.id, const.VPN_GENERIC_CONFIG_RPC_TOPIC))
                LOG.debug(msg)

                driver = self._get_driver()
                self._vpnservice_updated(ev, driver)
            except Exception as err:
                msg = ("Failed to perform the operation: %s. %s"
                       % (ev.id, str(err).capitalize()))
                LOG.error(msg)
            finally:
                self._sc.event_done(ev)

    def _vpnservice_updated(self, ev, driver):
        context = ev.data.get('context')
        self.resync(context)
        # I still don't know from where to call this method
        kwargs = ev.data.get('kwargs')
        msg = "Vpn service updated from server side"
        LOG.debug(msg)

        try:
            # in future if the vpnservice service function changes
            # then one should get the below function with getattr function
            driver.vpnservice_updated(context, kwargs)
        except Exception as err:
            msg = ("Failed to update VPN service. %s" % str(err).capitalize())
            LOG.error(msg)
        reason = kwargs.get('reason')
        rsrc = kwargs.get('rsrc_type')

        if (reason == 'delete' and rsrc == 'ipsec_site_connection'):
            conn = kwargs['resource']
            resource_id = conn['id']
            self._plugin_rpc.ipsec_site_conn_deleted(context,
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

    @core_pt.poll_event_desc(event='SYNC_UPDATE', spacing=10)
    def sync(self, context):
        """Periodically updates the status of vpn service, whether the
        tunnel is UP or DOWN.

        :param context: Dictionary of the vpn service type.

        Returns: None
        """
        s2s_contexts = self._plugin_rpc.get_vpn_servicecontext(context)
        for svc_context in s2s_contexts:
            svc_vendor = self._get_service_vendor(svc_context['service'])
            self._sync_ipsec_conns(context, svc_vendor, svc_context)

    def resync(self, context):
        """
        Gets invoked when the agents gets started or restarted, deleted if
        any services which are in PENDING_DELETE state.
        :param context: Dictionary of the vpn service type.

        Returns: None
        """
        try:
            s2s_contexts = self.plugin_rpc.get_vpn_servicecontext(
                context, filters={'status': ['PENDING_DELETE']})
        except MessagingTimeout as e:
            LOG.error("Failed in get_vpn_servicecontext for"
                      " IPSEC connections. Error: %s" % (e))
        else:
            for svc_context in s2s_contexts:
                svc_vendor = self._get_service_vendor(svc_context['service'])
                self._resync_ipsec_conns(context, svc_vendor, svc_context)

    def _resync_ipsec_conns(self, context, vendor, svc_context):
        """
        """
        for site_conn in svc_context['siteconns']:
            conn = site_conn['connection']
            keywords = {'resource': conn}
            try:
                self._get_driver().delete_ipsec_conn(context, **keywords)
            except Exception as err:
                msg = ("Delete ipsec-site-conn: %s failed"
                       " with Exception %s "
                       % (conn['id'], str(err).capitalize()))
                LOG.error(msg)

            self._plugin_rpc.ipsec_site_conn_deleted(context,
                                                     resource_id=conn['id'])


def events_init(sc, drivers):
    """Registers events with core service controller.

    All the events will come to handle_event method of class instance
    registered in 'handler' field.

    :param sc: Object of Service Controller from the process model to regiters
    the different events
    :param drivers: Driver instance registered with the service agent

    Returns: None
    """
    evs = [
        main.Event(id='VPNSERVICE_UPDATED',
                   handler=VPNaasEventHandler(sc, drivers)),
        main.Event(id='SYNC_UPDATE',
                   handler=VPNaasEventHandler(sc, drivers))]

    sc.register_events(evs)


def load_drivers(sc):
    """Loads the drivers dynamically.

    Loads the drivers that register with the agents.
    :param sc: Object of the Service Controller class from core
    service controller.

    Returns: dictionary of instances of the respective driver classes.
    """

    ld = utils.ConfiguratorUtils()
    drivers = ld.load_drivers(const.DRIVERS_DIR)
    plugin_rpc = VpnaasRpcSender(sc)

    for service_type, driver_name in drivers.iteritems():
        driver_obj = driver_name(plugin_rpc)
        drivers[service_type] = driver_obj

    return drivers


def register_service_agent(cm, sc, conf):
    """Registers the agents with Cofigurator module.
    Puts all the agents into the dictionary with their service types.
    :prarm cm: Configurator module's object to communicate back and forth
    :param sc: Object of the Service Controller class from core
    service controller.
    :param conf: Object of oslo configurator passed from the core service
    controller

    Returns: None
    """

    rpcmgr = VPNaasRpcManager(sc, conf)
    cm.register_service_agent(const.SERVICE_TYPE, rpcmgr)


def init_agent(cm, sc, conf):
    """Loads the drivers and registers the agents.
    Loads the dynamicaaly both the drivers and agents, registers the agents
    with their service types.

    :prarm cm: Configurator module's object to communicate back and forth
    :param sc: Object of the Service Controller class from core
    service controller.
    :param conf: Object of oslo configurator passed from the core service
    controller

    Returns: None

    """
    try:
        drivers = load_drivers(sc)
    except Exception as err:
        msg = ("VPNaas failed to load drivers. %s" % (str(err).capitalize()))
        LOG.error(msg)
        raise err
    else:
        msg = "VPNaas loaded drivers successfully."
        LOG.debug(msg)

    try:
        events_init(sc, drivers)
    except Exception as err:
        msg = ("VPNaas Events initialization unsuccessful. %s"
               % (str(err).capitalize()))
        LOG.error(msg)
        raise err
    else:
        msg = "VPNaas Events initialization successful."
        LOG.debug(msg)

    try:
        register_service_agent(cm, sc, conf)
    except Exception as err:
        msg = ("VPNaas service agent registration unsuccessful. %s"
               % (str(err).capitalize()))
        LOG.error(msg)
        raise err
    else:
        msg = "VPNaas service agent registration successful."
        LOG.debug(msg)

    msg = "VPN as a Service Module Initialized."
    LOG.info(msg)


def init_agent_complete(cm, sc, conf):
    """
    Initializes periodic tasks.
    """
    ev = sc.new_event(id='SYNC_UPDATE',
                      key='SYNC_UPDATE')
    sc.post_event(ev)
    msg = " vpn agent init complete"
    LOG.info(msg)
