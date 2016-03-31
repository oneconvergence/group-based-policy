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

from oslo_config import cfg
from oslo_log import log as logging

from gbpservice.nfp.configurator.agents import agent_base
from gbpservice.nfp.configurator.lib import config_script_constants as const
from gbpservice.nfp.configurator.lib import utils as load_driver
from gbpservice.nfp.core import event as nfp_event

LOG = logging.getLogger(__name__)

""" Implements ConfigScriptRpcManager class which receives requests
    from Configurator to Agent.

Methods of this class are invoked by the configurator. Events are
created according to the requests received and enqueued to worker queues.

"""


class ConfigScriptRpcManager(agent_base.AgentBaseRPCManager):
    RPC_API_VERSION = '1.0'
    target = messaging.Target(version=RPC_API_VERSION)

    def __init__(self, sc, conf):
        """Instantiates child and parent class objects.

        :param sc: Service Controller object that is used to communicate
        with process model core file.
        :param conf: Configuration object that is used for configuration
        parameter access.

        """

        super(ConfigScriptRpcManager, self).__init__(sc, conf)

    def _create_event(self, context, script, host, method):
        """ Creates and enqueues the events to the worker queues.

        :param context: Neutron context
        :param script: Script input by user
        :param host: Name of the host machine
        :param method: CREATE_HEAT/CREATE_ANSIBLE/CREATE_CONFIG_INIT

        """

        arg_dict = {'context': context,
                    'script': script,
                    'host': host}
        # REVISIT(mak): How to send large data ?
        # New API required to send over unix sockert ?
        context['service_info'] = {}
        # ev = self.sc.new_event(id=method, data={}, key=None)
        ev = self.sc.new_event(id=method, data=arg_dict, key=None)
        self.sc.post_event(ev)

    def create_heat(self, context, script, host):
        """ Receives request to create heat from configurator

        """

        msg = ("ConfigScriptRpcManager received Create Heat request.")
        LOG.debug(msg)
        self._create_event(context, script,
                           host, const.CREATE_HEAT_EVENT)

    def create_ansible(self, context, script, host):
        """ Receives request to create ansible from configurator

        """

        msg = ("ConfigScriptRpcManager received Create Ansible request.")
        LOG.debug(msg)
        self._create_event(context, script,
                           host, const.CREATE_ANSIBLE_EVENT)

    def create_config_init(self, context, script, host):
        """ Receives request to create config_init from configurator

        """

        msg = ("ConfigScriptRpcManager received Create ConfigInit request.")
        LOG.debug(msg)
        self._create_event(context, script,
                           host, const.CREATE_CONFIG_INIT_EVENT)

""" Handler class which invokes config_script driver methods

Worker processes dequeue the worker queues and invokes the
appropriate handler class methods for ConfigScript methods.

"""


class ConfigScriptEventHandler(agent_base.AgentBaseEventHandler):
    def __init__(self, sc, drivers, rpcmgr):
        """ Instantiates class object.

        :param sc: Service Controller object that is used to communicate
        with process model core file.
        :param drivers: dictionary of driver name to object mapping
        :param rpcmgr: ConfigScriptRpcManager class object

        """

        super(ConfigScriptEventHandler, self).__init__(sc, drivers, rpcmgr)
        self.sc = sc
        self.drivers = drivers
        self.host = cfg.CONF.host
        self.rpcmgr = rpcmgr

    def _get_driver(self):
        """ Retrieves driver object given the service type

        """

        driver_id = const.SERVICE_TYPE
        return self.drivers[driver_id]

    def handle_event(self, ev):
        """ Demultiplexes the config_script request to appropriate
        driver methods.

        :param ev: event object sent from process model event handler

        """

        context = ev.data.get('context')
        script = ev.data.get('script')
        host = ev.data.get('host')

        try:
            msg = ("Worker process with ID: %s starting to "
                   "handle task: %s of type ConfigScript. "
                   % (os.getpid(), ev.id))
            LOG.debug(msg)

            driver = self._get_driver()
            self.method = getattr(driver, "%s" % (ev.id.lower()))

            try:
                result = self.method(context, script, host)
            except Exception as err:
                msg = ("Failed to configure ConfigScript and status is "
                       "changed to ERROR. %s." % str(err).capitalize())
                LOG.error(msg)
            finally:
                notification_data = {
                    'receiver': 'service_orchestrator',
                    'resource': 'heat',
                    'method': 'network_function_device_notification',
                    'kwargs': [
                        {
                            'context': context,
                            'resource': ev.id.split('_')[1],
                            # For *aaS, we don't have request info right?
                            # 'request_info': request_info,
                            'result': result
                        }
                    ]
                }
                self.notify._notification(notification_data)
        except Exception as err:
            msg = ("Failed to perform the operation: %s. %s"
                   % (ev.id, str(err).capitalize()))
            LOG.error(msg)


def events_init(sc, drivers, rpcmgr):
    """Registers events with core service controller.

    All the events will come to handle_event method of class instance
    registered in 'handler' field.

    :param drivers: Driver instances registered with the service agent
    :param rpcmgr: Instance to receive all the RPC messages from configurator
    module.

    Returns: None

    """

    event_id_list = [const.CREATE_HEAT_EVENT,
                     const.CREATE_ANSIBLE_EVENT,
                     const.CREATE_CONFIG_INIT_EVENT]
    evs = []
    for event in event_id_list:
        evs.append(nfp_event.Event(id=event, handler=ConfigScriptEventHandler(
            sc, drivers, rpcmgr)))
    sc.register_events(evs)


def load_drivers():
    """Imports all the driver files corresponding to this agent.

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
    """Registers ConfigScript service agent with configurator module.

    :param cm: Instance of configurator module
    :param sc: Instance of core service controller
    :param conf: Instance of oslo configuration
    :param rpcmgr: Instance containing RPC methods which are invoked by
    configurator module on corresponding RPC message arrival

    """

    service_type = const.SERVICE_TYPE
    cm.register_service_agent(service_type, rpcmgr)


def init_agent(cm, sc, conf):
    """Initializes Config Script agent.

    :param cm: Instance of configuration module
    :param sc: Instance of core service controller
    :param conf: Instance of oslo configuration

    """

    try:
        drivers = load_drivers()
    except Exception as err:
        msg = ("Config Script failed to load drivers. %s"
               % (str(err).capitalize()))
        LOG.error(msg)
        raise Exception(err)
    else:
        msg = ("Config Script loaded drivers successfully.")
        LOG.debug(msg)

    rpcmgr = ConfigScriptRpcManager(sc, conf)
    try:
        events_init(sc, drivers, rpcmgr)
    except Exception as err:
        msg = ("Config Script Events initialization unsuccessful. %s"
               % (str(err).capitalize()))
        LOG.error(msg)
        raise Exception(err)
    else:
        msg = ("Config Script Events initialization successful.")
        LOG.debug(msg)

    try:
        register_service_agent(cm, sc, conf, rpcmgr)
    except Exception as err:
        msg = ("Config Script service agent registration unsuccessful. %s"
               % (str(err).capitalize()))
        LOG.error(msg)
        raise Exception(err)
    else:
        msg = ("Config Script service agent registration successful.")
        LOG.debug(msg)

    msg = ("ConfigScript as a Service Module Initialized.")
    LOG.info(msg)


def init_agent_complete(cm, sc, conf):
    """ Initializes periodic tasks

    """

    msg = (" Config Script agent init complete")
    LOG.info(msg)
