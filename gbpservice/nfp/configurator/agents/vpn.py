<<<<<<< HEAD
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


import os

from gbpservice.nfp.configurator.agents import agent_base
from gbpservice.nfp.configurator.drivers.base import base_driver
from gbpservice.nfp.configurator.lib import data_filter
from gbpservice.nfp.configurator.lib import utils
from gbpservice.nfp.configurator.lib import vpn_constants as const
from gbpservice.nfp.core import event as main
from gbpservice.nfp.core import log as nfp_logging
from gbpservice.nfp.core import poll as nfp_poll

import oslo_messaging as messaging

LOG = nfp_logging.getLogger(__name__)


class VpnaasRpcSender(data_filter.Filter):
    """
    Implements VPNaas response path to Neutron plugin.

    Methods of this class are invoked by the VPNaasEventHandler class
    for sending response from driver to the VPNaas Neutron plugin.

=======
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
>>>>>>> 9bbe395... Merging changes from liberty branch
    """
    RPC_API_VERSION = '1.0'
    target = messaging.Target(version=RPC_API_VERSION)

<<<<<<< HEAD
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
=======
    def __init__(self, context, sc):
        self.context = context
        self.sc = sc
        self.notify = agent_base.AgentBaseNotification(sc)
        super(VpnaasRpcSender, self).__init__(None, None)

    def get_vpn_services(self, context, ids=None, filters=None):
        """Get list of vpnservices on this host.
>>>>>>> 9bbe395... Merging changes from liberty branch
        """
        return self.call(
            context,
            self.make_msg('get_vpn_services', ids=ids, filters=filters))

    def get_vpn_servicecontext(self, context, filters=None):
        """Get list of vpnservice context on this host.
<<<<<<< HEAD
        :param context: dictionary which holds details of vpn service type like
            For IPSEC connections :
                List of vpnservices
                lIst of ipsec connections
                ike policy & ipsec policy.
        :param filter: based on which the filter library extracts the data
        from context dictionary.

        Returns: dictionary of vpnservice
=======
           For IPSEC connections :
                List of vpnservices -->
                lIst of ipsec connections -->
                ike policy & ipsec policy
>>>>>>> 9bbe395... Merging changes from liberty branch
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
<<<<<<< HEAD
        msg = {'info': {'service_type': const.SERVICE_TYPE,
                        'context': context['agent_info']['context']},
               'notification': [{
                     'resource': context['agent_info']['resource'],
                     'data': {'status': status,
                              'notification_type': (
                                    'update_status')}}]
               }
        self._notify._notification(msg)
=======
        msg = {'receiver': const.NEUTRON,
               'resource': const.SERVICE_TYPE,
               'method': 'update_status',
               'data': {'context': context,
                        'status': status}
               }
        self.notify._notification(msg)
>>>>>>> 9bbe395... Merging changes from liberty branch

    def ipsec_site_conn_deleted(self, context, resource_id):
        """ Notify VPNaaS plugin about delete of ipsec-site-conn """

<<<<<<< HEAD
        msg = {'info': {'service_type': const.SERVICE_TYPE,
                        'context': context['agent_info']['context']},
               'notification': [{
                     'resource': context['agent_info']['resource'],
                     'data': {'resource_id': resource_id,
                              'notification_type': (
                                    'ipsec_site_conn_deleted')}}]
               }
        self._notify._notification(msg)
=======
        msg = {'receiver': const.NEUTRON,
               'resource': const.SERVICE_TYPE,
               'method': 'ipsec_site_conn_deleted',
               'data': {'context': context,
                        'resource_id': resource_id}
               }
        self.notify._notification(msg)
>>>>>>> 9bbe395... Merging changes from liberty branch


class VPNaasRpcManager(agent_base.AgentBaseRPCManager):
    """
<<<<<<< HEAD
    Implements VPNaasRpcManager class which receives requests
        from Configurator to Agent.

    Methods of this class are invoked by the configurator. Events are
    created according to the requests received and enqueued to worker queues.

    """

=======
    APIs for receiving RPC messages from vpn plugin.
    """
>>>>>>> 9bbe395... Merging changes from liberty branch
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

<<<<<<< HEAD
    def vpnservice_updated(self, context, **resource_data):
        """Registers the VPNaas plugin events to update the vpn configurations.

        :param context: dictionary, confined to the specific service type.
        :param resource_data: dictionary, confined to the specific
               operation type.

        Returns: None
        """
        arg_dict = {'context': context,
                    'resource_data': resource_data}
=======
    def vpnservice_updated(self, context, kwargs):
        arg_dict = {'context': context,
                    'kwargs': kwargs}
>>>>>>> 9bbe395... Merging changes from liberty branch
        ev = self.sc.new_event(id='VPNSERVICE_UPDATED', data=arg_dict)
        self.sc.post_event(ev)


<<<<<<< HEAD
class VPNaasEventHandler(nfp_poll.PollEventDesc):
    """
    Handler class to invoke the vpn driver methods.
    For every event that gets invoked from worker process lands over here
    to make a call to the driver methods.
    """

    def __init__(self, sc, drivers):
        """ Instantiates class object.

        :param sc: Service Controller object that is used to communicate
        with process model core file.
        :param drivers: dictionary of driver name to object mapping

        """
        self._sc = sc
        self._drivers = drivers
        self._plugin_rpc = VpnaasRpcSender(self._sc)

    def _get_driver(self):

        driver_id = const.SERVICE_TYPE + const.SERVICE_VENDOR
        return self._drivers[driver_id]

    def handle_event(self, ev):
        """
        Demultiplexes the vpn request to appropriate  driver methods.

        :param ev: event object sent from the process model.

        Returns: None
        """
        if ev.id == 'VPN_SYNC':
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
        """
        Makes call to the respective operation method of vpn driver.

        :param ev: event object sent from the process model.
        :param driver: vpn driver class object.

        Returns: None.
        """
        context = ev.data.get('context')
        resource_data = ev.data.get('resource_data')
        msg = "Vpn service updated from server side"
        LOG.debug(msg)

        try:
            driver.vpnservice_updated(context, resource_data)

            if 'ipsec_site_conns' in context['service_info']:
                for item in context['service_info']['ipsec_site_conns']:
                    if item['id'] == resource_data['resource']['id'] and (
                                       resource_data['reason'] == 'create'):
                        item['status'] = 'INIT'
                        arg_dict = {'context': context,
                                    'resource_data': resource_data}
                        ev1 = self._sc.new_event(id='VPN_SYNC',
                                                 key='VPN_SYNC', data=arg_dict)
                        self._sc.post_event(ev1)
                    break
        except Exception as err:
            msg = ("Failed to update VPN service. %s" % str(err).capitalize())
            LOG.error(msg)
        reason = resource_data.get('reason')
        rsrc = resource_data.get('rsrc_type')

        if (reason == 'delete' and rsrc == 'ipsec_site_connection'):
            conn = resource_data['resource']
            resource_id = conn['id']
            self._plugin_rpc.ipsec_site_conn_deleted(context,
                                                     resource_id=resource_id)

    def _get_service_vendor(self, vpn_svc):
        """
        Extracts the vendor from the description.
        :param vpn_svc: vpn service operation type dictionary,
        which it gets from filter library

        Returns: None
        """
        svc_desc = vpn_svc['description']
        tokens = svc_desc.split(';')
        vendor = tokens[5].split('=')[1]
        return vendor

    def _sync_ipsec_conns(self, context, svc_context):
        """
        Gets the status of the vpn service.
        :param context: Dictionary of the vpn service type.
        :param vendor: vendor name
        :param svc_context: vpn service operation type dictionary,
        which it gets filter library

        Returns: None
        """
        try:
            self._get_driver()

            return self._get_driver().check_status(context, svc_context)
=======
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
        # TODO: This function should support multiple device drivers
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
        svc_desc = json.loads(vpn_svc['description'])
        vendor = svc_desc.get("service_vendor")
        return vendor

    def _sync_ipsec_conns(self, context, vendor, svc_context):
        try:
            self._get_driver().check_status(context, svc_context)
>>>>>>> 9bbe395... Merging changes from liberty branch
        except Exception as err:
            msg = ("Failed to sync ipsec connection information. %s."
                   % str(err).capitalize())
            LOG.error(msg)
<<<<<<< HEAD

    @nfp_poll.poll_event_desc(event='VPN_SYNC', spacing=10)
    def sync(self, ev):
        """Periodically updates the status of vpn service, whether the
        tunnel is UP or DOWN.

        :param context: Dictionary of the vpn service type.

        Returns: None
        """

        context = ev.data.get('context')
        s2s_contexts = self._plugin_rpc.get_vpn_servicecontext(context)
        state = self._sync_ipsec_conns(context, s2s_contexts[0])
        if state == const.STATE_ACTIVE:
            return {'poll': False}


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
        main.Event(id='VPN_SYNC',
                   handler=VPNaasEventHandler(sc, drivers))]

    sc.register_events(evs)


def load_drivers(sc, conf):
    """Loads the drivers dynamically.

    Loads the drivers that register with the agents.
    :param sc: Object of the Service Controller class from core
    service controller.

    Returns: dictionary of instances of the respective driver classes.
    """

    ld = utils.ConfiguratorUtils()
    drivers = ld.load_drivers(const.DRIVERS_DIR)

    for service_type, driver_name in drivers.iteritems():
        driver_obj = driver_name(conf=conf)
=======
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
            # whether it has to be the self.context or normal context?
            try:
                self._get_driver().delete_ipsec_conn(context, **keywords)
            except Exception as err:
                LOG.error("Delete ipsec-site-conn: %s failed"
                          " with Exception %s "
                          % (conn['id'], str(err).capitalize()))

            self.plugin_rpc.ipsec_site_conn_deleted(context,
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
>>>>>>> 9bbe395... Merging changes from liberty branch
        drivers[service_type] = driver_obj

    return drivers


def register_service_agent(cm, sc, conf):
<<<<<<< HEAD
    """Registers the agents with Cofigurator module.
    Puts all the agents into the dictionary with their service types.
    :prarm cm: Configurator module's object to communicate back and forth
    :param sc: Object of the Service Controller class from core
    service controller.
    :param conf: Object of oslo configurator passed from the core service
    controller

    Returns: None
    """
=======
>>>>>>> 9bbe395... Merging changes from liberty branch

    rpcmgr = VPNaasRpcManager(sc, conf)
    cm.register_service_agent(const.SERVICE_TYPE, rpcmgr)


def init_agent(cm, sc, conf):
<<<<<<< HEAD
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
        drivers = load_drivers(sc, conf)
    except Exception as err:
        msg = ("VPNaas failed to load drivers. %s" % (str(err).capitalize()))
        LOG.error(msg)
        raise err
    else:
        msg = "VPNaas loaded drivers successfully."
        LOG.debug(msg)
=======
    try:
        drivers = load_drivers(sc)
    except Exception as err:
        LOG.error("VPNaas failed to load drivers. %s"
                  % (str(err).capitalize()))
        raise err
    else:
        LOG.debug("VPNaas loaded drivers successfully.")
>>>>>>> 9bbe395... Merging changes from liberty branch

    try:
        events_init(sc, drivers)
    except Exception as err:
<<<<<<< HEAD
        msg = ("VPNaas Events initialization unsuccessful. %s"
               % (str(err).capitalize()))
        LOG.error(msg)
        raise err
    else:
        msg = "VPNaas Events initialization successful."
        LOG.debug(msg)

    try:
        register_service_agent(cm, sc, conf)
        bdobj = base_driver.BaseDriver(conf)
        bdobj.register_agent_object_with_driver('agent', VpnaasRpcSender(sc))
    except Exception as err:
        msg = ("VPNaas service agent registration unsuccessful. %s"
               % (str(err).capitalize()))
        LOG.error(msg)
        raise err
    else:
        msg = "VPNaas service agent registration successful."
        LOG.debug(msg)

    msg = "VPN as a Service Module Initialized."
=======
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
>>>>>>> 9bbe395... Merging changes from liberty branch
    LOG.info(msg)


def init_agent_complete(cm, sc, conf):
<<<<<<< HEAD
    """
    Initializes periodic tasks.
    """
    msg = " vpn agent init complete"
    LOG.info(msg)
=======
    LOG.info(" vpn agent init complete")

>>>>>>> 9bbe395... Merging changes from liberty branch
