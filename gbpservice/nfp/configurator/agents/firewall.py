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
import oslo_messaging as messaging
import requests

from oslo_config import cfg
from oslo_log import log as logging

from gbpservice.nfp.configurator.agents import agent_base
from gbpservice.nfp.configurator.lib import fw_constants as const
from gbpservice.nfp.configurator.lib import utils as load_driver
from gbpservice.nfp.core import main


LOG = logging.getLogger(__name__)

rest_timeout = [
    cfg.IntOpt(
        'rest_timeout',
        default=360,
        help=_("rest api timeout"))]
cfg.CONF.register_opts(rest_timeout)

""" Implements Fwaas response path to Neutron plugin.

Methods of this class are invoked by the FwaasEventHandler class
for sending response from driver to the Fwaas Neutron plugin.

"""


class FwaasRpcSender(agent_base.AgentBaseEventHandler):

    def __init__(self, sc, host, drivers, rpcmgr):
        super(FwaasRpcSender, self).__init__(sc, drivers, rpcmgr)
        self.host = host

    def set_firewall_status(self, context, firewall_id, status):
        """ Enqueues the response from FwaaS operation to neutron plugin.

        :param context: Neutron context
        :param firewall_id: id of firewall resource
        :param status: ACTIVE/ ERROR

        """

        msg = {'receiver': const.NEUTRON,
               'resource': const.SERVICE_TYPE,
               'method': 'set_firewall_status',
               'kwargs': {'context': context,
                          'host': self.host,
                          'firewall_id': firewall_id,
                          'status': status}
               }
        self.notify._notification(msg)

    def firewall_deleted(self, context, firewall_id):
        """ Enqueues the response from FwaaS operation to neutron plugin.

        :param context: Neutron context
        :param firewall_id: id of firewall resource

        """

        msg = {'receiver': const.NEUTRON,
               'resource': const.SERVICE_TYPE,
               'method': 'firewall_deleted',
               'kwargs': {'context': context,
                          'host': self.host,
                          'firewall_id': firewall_id}
               }
        self.notify._notification(msg)

""" Implements FWaasRpcManager class which receives requests
    from Configurator to Agent.

Methods of this class are invoked by the configurator. Events are
created according to the requests received and enqueued to worker queues.

"""


class FWaasRpcManager(agent_base.AgentBaseRPCManager):
    RPC_API_VERSION = '1.0'
    target = messaging.Target(version=RPC_API_VERSION)

    def __init__(self, sc, conf):
        """Instantiates child and parent class objects.

        :param sc: Service Controller object that is used to communicate
        with process model core file.
        :param conf: Configuration object that is used for configuration
        parameter access.

        """

        super(FWaasRpcManager, self).__init__(sc, conf)

    def _create_event(self, context, firewall, host, method):
        """ Creates and enqueues the events to the worker queues.

        :param context: Neutron context
        :param firewall: Firewall resource object from neutron fwaas plugin
        :param host: Name of the host machine
        :param method: CREATE_FIREWALL/UPDATE_FIREWALL/DELETE_FIREWALL

        """

        arg_dict = {'context': context,
                    'firewall': firewall,
                    'host': host}
        ev = self.sc.new_event(id=method, data=arg_dict, key=None)
        self.sc.post_event(ev)

    def create_firewall(self, context, firewall, host):
        """ Receives request to create firewall from configurator

        """

        msg = ("FwaasRpcReceiver received Create Firewall request.")
        LOG.debug(msg)
        self._create_event(context, firewall,
                           host, const.FIREWALL_CREATE_EVENT)

    def update_firewall(self, context, firewall, host):
        """ Receives request to update firewall from configurator

        """

        msg = ("FwaasRpcReceiver received Update Firewall request.")
        LOG.debug(msg)
        self._create_event(context, firewall,
                           host, const.FIREWALL_UPDATE_EVENT)

    def delete_firewall(self, context, firewall, host):
        """ Receives request to delete firewall from configurator

        """

        msg = ("FwaasRpcReceiver received Delete Firewall request.")
        LOG.debug(msg)
        self._create_event(context, firewall,
                           host, const.FIREWALL_DELETE_EVENT)

""" Handler class which invokes firewall driver methods

Worker processes dequeue the worker queues and invokes the
appropriate handler class methods for Fwaas methods.

"""


class FWaasEventHandler(object):
    def __init__(self, sc, drivers, rpcmgr):
        """ Instantiates class object.

        :param sc: Service Controller object that is used to communicate
        with process model core file.
        :param drivers: dictionary of driver name to object mapping
        :param rpcmgr: FwaasRpcManager class object

        """

        self.sc = sc
        self.drivers = drivers
        self.host = cfg.CONF.host
        self.rpcmgr = rpcmgr
        self.plugin_rpc = FwaasRpcSender(sc, self.host,
                                         self.drivers, self.rpcmgr)

    def _get_driver(self):
        """ Retrieves driver object given the service type

        """

        driver_id = const.SERVICE_TYPE
        return self.drivers[driver_id]

    def _is_firewall_rule_exists(self, fw):
        """ Checks if firewall rules are present in the request data

        :param fw: Firewall resource object

        """

        if not fw['firewall_rule_list']:
            return False
        else:
            return True

    def handle_event(self, ev):
        """ Demultiplexes the firewall request to appropriate
        driver methods.

        :param ev: event object sent from process model event handler

        """

        try:
            msg = ("Worker process with ID: %s starting to "
                   "handle task: %s of type firewall. "
                   % (os.getpid(), ev.id))
            LOG.debug(msg)

            driver = self._get_driver()
            self.method = getattr(driver, "%s" % (ev.id.lower()))
            self.invoke_driver_for_plugin_api(ev)
        except Exception as err:
            msg = ("Failed to perform the operation: %s. %s"
                   % (ev.id, str(err).capitalize()))
            LOG.error(msg)

    def invoke_driver_for_plugin_api(self, ev):
        """ Invokes the appropriate driver methods

        :param ev: event object sent from process model event handler

        """

        context = ev.data.get('context')
        firewall = ev.data.get('firewall')
        host = ev.data.get('host')

        if ev.id == const.FIREWALL_CREATE_EVENT:
            if not self._is_firewall_rule_exists(firewall):
                msg = ("Firewall status set to ACTIVE")
                LOG.debug(msg)
                return self.plugin_rpc.set_firewall_status(
                    context, firewall['id'], const.STATUS_ACTIVE)
            # Added to handle in service vm agents. VM agent will add
            # default DROP rule.
            # if not self._is_firewall_rule_exists(firewall):
            #     self.plugin_rpc.set_firewall_status(
            #         context, firewall['id'], const.STATUS_ACTIVE)
            try:
                status = self.method(context, firewall, host)
            except Exception as err:
                self.plugin_rpc.set_firewall_status(
                    context, firewall['id'], const.STATUS_ERROR)
                msg = ("Failed to configure Firewall and status is "
                       "changed to ERROR. %s." % str(err).capitalize())
                LOG.error(msg)
            else:
                self.plugin_rpc.set_firewall_status(
                    context, firewall['id'], status)
                msg = ("Configured Firewall and status set to %s" % status)
                LOG.info(msg)

        elif ev.id == const.FIREWALL_DELETE_EVENT:
            if not self._is_firewall_rule_exists(firewall):
                return self.plugin_rpc.firewall_deleted(context,
                                                        firewall['id'])
            try:
                status = self.method(context, firewall, host)
            except requests.ConnectionError:
                # FIXME It can't be correct everytime
                msg = ("There is a connection error for firewall %r of "
                       "tenant %r. Assuming either there is serious "
                       "issue with VM or data path is completely "
                       "broken. For now marking that as delete."
                       % (firewall['id'], firewall['tenant_id']))
                LOG.warning(msg)
                self.plugin_rpc.firewall_deleted(context, firewall['id'])

            except Exception as err:
                # TODO(VIKASH) Is it correct to raise ? As the subsequent
                # attempt to clean will only re-raise the last one.And it
                # can go on and on and may not be ever recovered.
                self.plugin_rpc.set_firewall_status(
                    context, firewall['id'], const.STATUS_ERROR)
                msg = ("Failed to delete Firewall and status is "
                       "changed to ERROR. %s." % str(err).capitalize())
                LOG.error(msg)
                # raise(err)
            else:
                if status == const.STATUS_ERROR:
                    self.plugin_rpc.set_firewall_status(
                        context, firewall['id'], status)
                else:
                    msg = ("Firewall %r deleted of tenant: %r" % (
                           firewall['id'], firewall['tenant_id']))
                    LOG.info(msg)
                    self.plugin_rpc.firewall_deleted(
                                        context, firewall['id'])

        elif ev.id == const.FIREWALL_UPDATE_EVENT:
            if not self._is_firewall_rule_exists(firewall):
                return self.plugin_rpc.set_firewall_status(
                    context, firewall['id'], const.STATUS_ACTIVE)
            try:
                status = self.method(context, firewall, host)
            except Exception as err:
                self.plugin_rpc.set_firewall_status(
                            context, firewall['id'], 'ERROR')
                msg = ("Failed to update Firewall and status is "
                       "changed to ERROR. %s." % str(err).capitalize())
                LOG.error(msg)
            else:
                self.plugin_rpc.set_firewall_status(
                                context, firewall['id'], status)
                msg = ("Updated Firewall and status set to %s" % status)
                LOG.info(msg)
        else:
            msg = ("Wrong call to Fwaas event handler.")
            raise Exception(msg)


def events_init(sc, drivers, rpcmgr):
    """Registers events with core service controller.

    All the events will come to handle_event method of class instance
    registered in 'handler' field.

    :param drivers: Driver instances registered with the service agent
    :param rpcmgr: Instance to receive all the RPC messages from configurator
    module.

    Returns: None

    """

    event_id_list = [const.FIREWALL_CREATE_EVENT,
                     const.FIREWALL_UPDATE_EVENT,
                     const.FIREWALL_DELETE_EVENT]
    evs = []
    for event in event_id_list:
        evs.append(main.Event(id=event, handler=FWaasEventHandler(
                              sc, drivers, rpcmgr)))
    sc.register_events(evs)


def load_drivers():
    """Imports all the driver files.

    Returns: Dictionary of driver objects with a specified service type and
    vendor name

    """

    ld = load_driver.ConfiguratorUtils()
    drivers = ld.load_drivers(const.DRIVERS_DIR)

    for service_type, driver_name in drivers.iteritems():
        driver_obj = driver_name()
        drivers[service_type] = driver_obj

    return drivers


def register_service_agent(cm, sc, conf, rpcmgr):
    """Registers Fwaas service agent with configurator module.

    :param cm: Instance of configurator module
    :param sc: Instance of core service controller
    :param conf: Instance of oslo configuration
    :param rpcmgr: Instance containing RPC methods which are invoked by
    configurator module on corresponding RPC message arrival

    """

    service_type = const.SERVICE_TYPE
    cm.register_service_agent(service_type, rpcmgr)


def init_agent(cm, sc, conf):
    """Initializes Fwaas agent.

    :param cm: Instance of configuration module
    :param sc: Instance of core service controller
    :param conf: Instance of oslo configuration

    """

    try:
        drivers = load_drivers()
    except Exception as err:
        msg = ("Fwaas failed to load drivers. %s"
               % (str(err).capitalize()))
        LOG.error(msg)
        raise Exception(err)
    else:
        msg = ("Fwaas loaded drivers successfully.")
        LOG.debug(msg)

    rpcmgr = FWaasRpcManager(sc, conf)
    try:
        events_init(sc, drivers, rpcmgr)
    except Exception as err:
        msg = ("Fwaas Events initialization unsuccessful. %s"
               % (str(err).capitalize()))
        LOG.error(msg)
        raise Exception(err)
    else:
        msg = ("Fwaas Events initialization successful.")
        LOG.debug(msg)

    try:
        register_service_agent(cm, sc, conf, rpcmgr)
    except Exception as err:
        msg = ("Fwaas service agent registration unsuccessful. %s"
               % (str(err).capitalize()))
        LOG.error(msg)
        raise Exception(err)
    else:
        msg = ("Fwaas service agent registration successful.")
        LOG.debug(msg)

    msg = ("FIREWALL as a Service Module Initialized.")
    LOG.info(msg)


def init_agent_complete(cm, sc, conf):
    """ Initializes periodic tasks

    """

    msg = (" Firewall agent init complete")
    LOG.info(msg)
