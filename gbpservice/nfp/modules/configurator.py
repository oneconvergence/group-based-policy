
from gbpservice.nfp.configurator.lib import constants
from gbpservice.nfp.configurator.lib import demuxer
from oslo_log import log
from gbpservice.nfp.core import rpc
from gbpservice.nfp.core import fifo as queue
from gbpservice.nfp.configurator.lib import utils

AGENTS_PKG = 'gbpservice.nfp.configurator.agents'
CONFIGURATOR_RPC_TOPIC = 'configurator'
LOG = log.getLogger(__name__)

"""Implements procedure calls invoked by an REST server.

Implements following RPC methods.
  - create_network_device_config
  - delete_network_device_config
  - update_network_device_config
  - create_network_service_config
  - delete_network_service_config
  - update_network_service_config
  - get_notifications
Also implements local methods for supporting RPC methods

"""


class ConfiguratorRpcManager(object):
    def __init__(self, sc, cm, conf, demuxer):
        self.sc = sc
        self.cm = cm
        self.conf = conf
        self.demuxer = demuxer

    def _get_service_agent_instance(self, service_type):
        """Provides service agent instance based on service type.

        :param service_type: firewall/vpn/loadbalancer/generic_config

        Returns: Instance of service agent for a given service type

        """

        return self.cm.service_agent_instances[service_type]

    def _send_request(self, operation, request_data):
        """Maps and invokes an RPC call to a service agent method.

        Takes help of de-multiplexer to get service type and corresponding
        data and invokes the method of service agent. Service agent instance
        is identified based on the service type passed in the request data

        :param operation: Operation type - create/delete/update
        :param request_data: RPC data

        Returns: None

        """

        # Retrieves service type from RPC data
        service_type = self.demuxer.get_service_type(request_data)
        if (constants.invalid_service_type == service_type):
            msg = ("Configurator received invalid service type %s." %
                   service_type)
            raise Exception(msg)

        # Retrieves service agent information from RPC data
        # Format of sa_info_list:
        # [{'method': <m1>, 'kwargs': <rpc_data1>}, {}, ... ]
        sa_info_list = self.demuxer.get_service_agent_info(
                                                    operation,
                                                    service_type,
                                                    request_data)
        if not sa_info_list:
            msg = ("Configurator received invalid data format for service"
                   " type %s. Data format: %r" % (service_type, request_data))
            raise Exception(msg)

        # Retrieves service agent instance using service type
        sa_obj = self._get_service_agent_instance(service_type)
        if not sa_obj:
            msg = ("Failed to find agent with service type %s." % service_type)
            raise Exception(msg)

        # Notification data list that needs to be returned after processing
        # RPC request. Format of notification data:
        # notification_data[
        #    {
        #        'receiver': <neutron/orchestrator>,
        #        'resource': <firewall/vpn/loadbalancer/healthmonitor/
        #                    routes/interfaces>,
        #        'method': <network_function_device_notification/
        #                  *aaS response RPC method name>,
        #        'kwargs': [{<data1>}, {data2}]
        #    },
        #    {
        #    }, ...
        # ]
        #
        # Initially, notification data will be empty and is populated
        # after processing each request data in the request data list
        notification_data = {}

        # Handover the request data list and notification data to the
        # identified service agent
        sa_obj.forward_request(sa_info_list, notification_data)

    def create_network_device_config(self, context, request_data):
        """RPC method to configure a network service device.

        Configures a network service VM to facilitate network service
        operation. This RPC method is invoked by the configurator REST
        server. It configures a network service based on the configuration
        request specified in the request_data argument.

        :param context: RPC context instance
        :param request_data: RPC data

        Returns: None

        """

        try:
            # REVISIT: This is added during integration testing as health
            # monitoring support is not provided. This needs to be removed
            # once HM is added to configurator
            import time; time.sleep(180)
            self._send_request('create', request_data)
        except Exception as err:
            msg = ("Failed to create network device configuration. %s" %
                   str(err).capitalize())
            LOG.error(msg)

    def delete_network_device_config(self, context, request_data):
        """RPC method to clear configuration of a network service device.

        Clears configuration of a network service VM. This RPC method is
        invoked by the configurator REST server. It clears configuration
        of a network service based on the configuration request specified
        in the request_data argument.

        :param context: RPC context instance
        :param request_data: RPC data

        Returns: None

        """

        try:
            self._send_request('delete', request_data)
        except Exception as err:
            msg = ("Failed to delete network device configuration. %s" %
                   str(err).capitalize())
            LOG.error(msg)

    def update_network_device_config(self, context, request_data):
        """RPC method to update of configuration in a network service device.

        Updates configuration of a network service VM. This RPC method is
        invoked by the configurator REST server. It updates configuration
        of a network service based on the configuration request specified
        in the request_data argument.

        :param context: RPC context instance
        :param request_data: RPC data

        Returns: None

        """

        try:
            self._send_request('update', request_data)
        except Exception as err:
            msg = ("Failed to update network device configuration. %s" %
                   str(err).capitalize())
            LOG.error(msg)

    def create_network_service_config(self, context, request_data):
        """RPC method to configure a network service.

        Configures a network service specified in the request data. This
        RPC method is invoked by the configurator REST server. It configures
        a network service based on the configuration request specified in
        the request_data argument.

        :param context: RPC context instance
        :param request_data: RPC data

        Returns: None

        """

        try:
            self._send_request('create', request_data)
        except Exception as err:
            msg = ("Failed to create network service configuration. %s" %
                   str(err).capitalize())
            LOG.error(msg)

    def delete_network_service_config(self, context, request_data):
        """RPC method to clear configuration of a network service.

        Clears configuration of a network service. This RPC method is
        invoked by the configurator REST server. It clears configuration
        of a network service based on the configuration request specified
        in the request_data argument.

        :param context: RPC context instance
        :param request_data: RPC data

        Returns: None

        """

        try:
            self._send_request('delete', request_data)
        except Exception as err:
            msg = ("Failed to delete network service configuration. %s" %
                   str(err).capitalize())
            LOG.error(msg)

    def update_network_service_config(self, context, request_data):
        """RPC method to update of configuration in a network service.

        Updates configuration of a network service. This RPC method is
        invoked by the configurator REST server. It updates configuration
        of a network service based on the configuration request specified
        in the request_data argument.

        :param context: RPC context instance
        :param request_data: RPC data

        Returns: None

        """

        try:
            self._send_request('update', request_data)
        except Exception as err:
            msg = ("Failed to update network service configuration. %s" %
                   str(err).capitalize())
            LOG.error(msg)

    def get_notifications(self, context):
        """RPC method to get all notifications published by configurator.

        Gets all the notifications from the notifications from notification
        queue and sends to configurator agent

        :param context: RPC context instance

        Returns: notification_data

        """

        return self.cm.nqueue.get()

"""Implements configurator module APIs.

    Implements methods which are either invoked by registered service agents
    or by the configurator global methods. The methods invoked by configurator
    global methods interface with service agents.

"""


class ConfiguratorModule(object):
    def __init__(self, sc):
        self.service_agent_instances = {}
        self.imported_service_agents = []
        self.nqueue = queue.Fifo(sc)

    def register_service_agent(self, service_type, service_agent):
        """Stores service agent object.

        :param service_type: Type of service - firewall/vpn/loadbalancer/
        generic_config.
        :param service_agent: Instance of service agent class.

        Returns: Nothing

        """

        if service_type not in self.service_agent_instances:

            msg = ("Configurator registered service agent of type %s." %
                   service_type)
            LOG.info(msg)
        else:
            msg = ("Identified duplicate registration with service type %s." %
                   service_type)
            LOG.warn(msg)

        # Register the service agent irrespective of previous registration
        self.service_agent_instances.update({service_type: service_agent})

    def init_service_agents(self, sc, conf):
        """Invokes service agent initialization method.

        :param sc: Service Controller object that is used for interfacing
        with core service controller.
        :param conf: Configuration object that is used for configuration
        parameter access.

        Returns: None

        """

        for agent in self.imported_service_agents:
            try:
                agent.init_agent(self, sc, conf, self.nqueue)
            except AttributeError as attr_err:
                LOG.error(agent.__dict__)
                raise AttributeError(agent.__file__ + ': ' + str(attr_err))

    def init_service_agents_complete(self, sc, conf):
        """Invokes service agent initialization complete method.

        :param sc: Service Controller object that is used for interfacing
        with core service controller.
        :param conf: Configuration object that is used for configuration
        parameter access.

        Returns: None

        """

        for agent in self.imported_service_agents:
            try:
                agent.init_agent_complete(self, sc, conf)
            except AttributeError as attr_err:
                LOG.error(agent.__dict__)
                raise AttributeError(agent.__file__ + ': ' + str(attr_err))


def init_rpc(sc, cm, conf, demuxer):
    """Initializes oslo RPC client.

    Creates RPC manager object and registers the configurator's RPC
    agent object with core service controller.

    :param sc: Service Controller object that is used for interfacing
    with core service controller.
    :param cm: Configurator module object that is used for accessing
    ConfiguratorModule class methods.
    :param conf: Configuration object that is used for configuration
    parameter access.
    :param demuxer: De-multiplexer object that is used for accessing
    ConfiguratorDemuxer class methods.

    Returns: None

    """

    # Initializes RPC client
    rpc_mgr = ConfiguratorRpcManager(sc, cm, conf, demuxer)
    configurator_agent = rpc.RpcAgent(sc,
                                       topic=CONFIGURATOR_RPC_TOPIC,
                                       manager=rpc_mgr)

    # Registers RPC client object with core service controller
    sc.register_rpc_agents([configurator_agent])


def get_configurator_module_instance(sc):
    """ Provides ConfiguratorModule class object and loads service agents.

    Returns: Instance of ConfiguratorModule class

    """

    cm = ConfiguratorModule(sc)
    conf_utils = utils.ConfiguratorUtils()

    # Loads all the service agents under AGENT_PKG module path
    cm.imported_service_agents = conf_utils.load_agents(AGENTS_PKG)
    msg = ("Configurator loaded service agents from %s location."
           % (cm.imported_service_agents))
    LOG.info(msg)
    return cm


def module_init(sc, conf):
    """Initializes configurator module.

    Creates de-multiplexer object and invokes all the agent entry point
    functions. Initializes oslo RPC client for receiving messages from
    REST server. Exceptions are raised to parent function for all types
    of failures.

    :param sc: Service Controller object that is used for interfacing
    with core service controller.
    :param conf: Configuration object that is used for configuration
    parameter access.

    Returns: None
    Raises: Generic exception including error message

    """

    # Create configurator module and de-multiplexer objects
    try:
        cm = get_configurator_module_instance(sc)
        demuxer_instance = demuxer.ConfiguratorDemuxer()
    except Exception as err:
        msg = ("Failed to initialize configurator de-multiplexer. %s."
               % (str(err).capitalize()))
        LOG.error(msg)
        raise Exception(err)
    else:
        LOG.info("Initialized configurator de-multiplexer.")

    # Initialize all the pre-loaded service agents
    try:
        cm.init_service_agents(sc, conf)
    except Exception as err:
        msg = ("Failed to initialize configurator agent modules. %s."
               % (str(err).capitalize()))
        LOG.error(msg)
        raise Exception(err)
    else:
        LOG.info("Initialized configurator agents.")

    # Initialize RPC client for receiving messages from REST server
    try:
        init_rpc(sc, cm, conf, demuxer_instance)
    except Exception as err:
        msg = ("Failed to initialize configurator RPC with topic %s. %s."
               % (CONFIGURATOR_RPC_TOPIC, str(err).capitalize()))
        LOG.error(msg)
        raise Exception(err)
    else:
        LOG.debug("Initialized configurator RPC with topic %s."
                  % CONFIGURATOR_RPC_TOPIC)


def init_complete(sc, conf):
    """Invokes service agent's initialization complete methods.

    :param sc: Service Controller object that is used for interfacing
    with core service controller.
    :param conf: Configuration object that is used for configuration
    parameter access.

    Returns: None
    Raises: Generic exception including error message

    """

    try:
        cm = get_configurator_module_instance(sc)
        cm.init_service_agents_complete(sc, conf)
    except Exception as err:
        msg = ("Failed to trigger initialization complete for configurator"
               " agent modules. %s." % (str(err).capitalize()))
        LOG.error(msg)
        raise Exception(err)
    else:
        LOG.info("Initialization of configurator agent modules completed.")
