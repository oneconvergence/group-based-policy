
from gbpservice.neutron.nsf.configurator.agents import agent_base
from gbpservice.neutron.nsf.configurator.lib import (
                            generic_config_constants as const)
from oslo_log import log as logging
from gbpservice.neutron.nsf.core import main
import os
from gbpservice.neutron.nsf.configurator.lib import utils

LOG = logging.getLogger(__name__)


"""Implements APIs invoked by configurator for processing RPC messages.

RPC client of configurator module receives RPC messages from REST server
and invokes the API of this class. The instance of this class is registered
with configurator module using register_service_agent API. Configurator module
identifies the service agent object based on service type and invokes ones of
the methods of this class to configure the device.

"""


class GenericConfigRpcManager(agent_base.AgentBaseRPCManager):
    def __init__(self, sc, conf):
        """Instantiates child and parent class objects.

        Passes the instances of core service controller and oslo configuration
        to parent instance inorder to provide event enqueue facility for batch
        processing event.

        :param sc: Service Controller object that is used for interfacing
        with core service controller.
        :param conf: Configuration object that is used for configuration
        parameter access.

        """

        super(GenericConfigRpcManager, self).__init__(sc, conf)

    def configure_interfaces(self, context, kwargs):
        """Enqueues event for worker to process configure interfaces request.

        :param context: RPC context
        :param kwargs: RPC Request data

        Returns: None

        """

        arg_dict = {'context': context,
                    'kwargs': kwargs}
        ev = self._sc.event(id='CONFIGURE_INTERFACES', data=arg_dict)
        self._sc.rpc_event(ev)

    def clear_interfaces(self, context, kwargs):
        """Enqueues event for worker to process clear interfaces request.

        :param context: RPC context
        :param kwargs: RPC Request data

        Returns: None

        """

        arg_dict = {'context': context,
                    'kwargs': kwargs}
        ev = self._sc.event(id='CLEAR_INTERFACES', data=arg_dict)
        self._sc.rpc_event(ev)

    def configure_routes(self, context, kwargs):
        """Enqueues event for worker to process configure routes request.

        :param context: RPC context
        :param kwargs: RPC Request data

        Returns: None

        """

        arg_dict = {'context': context,
                    'kwargs': kwargs}
        ev = self._sc.event(id='CONFIGURE_ROUTES', data=arg_dict)
        self._sc.rpc_event(ev)

    def clear_routes(self, context, kwargs):
        """Enqueues event for worker to process clear routes request.

        :param context: RPC context
        :param kwargs: RPC Request data

        Returns: None

        """

        arg_dict = {'context': context,
                    'kwargs': kwargs}
        ev = self._sc.event(id='CLEAR_ROUTES', data=arg_dict)
        self._sc.rpc_event(ev)

"""Implements event handlers and their helper methods.

Object of this class is registered with the event class of core service
controller. Based on the event key, handle_event method of this class is
invoked by core service controller.

"""


class GenericConfigEventHandler(agent_base.AgentBaseEventHandler):
    def __init__(self, sc, drivers, rpcmgr, nqueue):
        super(GenericConfigEventHandler, self).__init__(
                                        sc, drivers, rpcmgr, nqueue)

    def _get_driver(self, service_type):
        """Retrieves service driver object based on service type input.

        Currently, service drivers are identified with service type. Support
        for single driver per service type is provided. When multi-vendor
        support is going to be provided, the driver should be selected based
        on both service type and vendor name.

        :param service_type: Service type - firewall/vpn/loadbalancer

        Returns: Service driver instance

        """

        return self.drivers[service_type]()

    def handle_event(self, ev):
        """Processes the generated events in worker context.

        Processes the following events.
        - Configure Interfaces
        - Clear Interfaces
        - Configure routes
        - Clear routes
        Enqueues responses into notification queue.

        Returns: None

        """

        # Process batch of request data blobs
        try:
            if ev.id == 'PROCESS_BATCH':
                self.process_batch(ev)
                return
        except Exception as err:
            msg = ("Failed to process data batch. %s" %
                   str(err).capitalize())
            LOG.error(msg)
            return

        # Process single request data blob
        kwargs = ev.data.get('kwargs')
        context = ev.data.get('context')
        service_type = kwargs.get('service_type')

        # Retrieve notification and remove it from context. Context is used
        # as transport from batch processing function to this last event
        # processing function. To keep the context unchanged, delete the
        # notification_data before invoking driver API.
        notification_data = context.get('notification_data')
        del context['notification_data']

        try:
            msg = ("Worker process with ID: %s starting "
                   "to handle task: %s for service type: %s. "
                   % (os.getpid(), ev.id, str(service_type)))
            LOG.debug(msg)

            driver = self._get_driver(service_type)

            # Invoke service driver methods based on event type received
            result = getattr(driver, "%s" % ev.id.lower())(context, kwargs)
        except Exception as err:
            result = ("Failed to process %s request for %s service type. %s" %
                      (ev.id, service_type, str(err).capitalize()))
            LOG.error(result)
        finally:
            msg = {'receiver': const.ORCHESTRATOR,
                   'resource': service_type,
                   'method': ev.id,
                   'kwargs': [{'context': context, 'result': result}]
                   }
            if not notification_data:
                notification_data.update(msg)
            else:
                data = {'context': context,
                        'result': result}
                notification_data['kwargs'].extend(data)
            self.nqueue.put(notification_data)


def events_init(sc, drivers, rpcmgr, nqueue):
    """Registers events with core service controller.

    All the events will come to handle_event method of class instance
    registered in 'handler' field.

    :param drivers: Driver instances registered with the service agent
    :param rpcmgr: Instance to receive all the RPC messages from configurator
    module.

    Returns: None

    """

    evs = [
        main.Event(id=const.EVENT_CONFIGURE_INTERFACES,
                   handler=GenericConfigEventHandler(
                                        sc, drivers, rpcmgr, nqueue)),
        main.Event(id=const.EVENT_CLEAR_INTERFACES,
                   handler=GenericConfigEventHandler(
                                        sc, drivers, rpcmgr, nqueue)),
        main.Event(id=const.EVENT_CONFIGURE_ROUTES,
                   handler=GenericConfigEventHandler(
                                        sc, drivers, rpcmgr, nqueue)),
        main.Event(id=const.EVENT_CLEAR_ROUTES,
                   handler=GenericConfigEventHandler(
                                        sc, drivers, rpcmgr, nqueue)),
        main.Event(id=const.EVENT_PROCESS_BATCH,
                   handler=GenericConfigEventHandler(
                                        sc, drivers, rpcmgr, nqueue))
    ]
    sc.register_events(evs)


def load_drivers():
    """Imports all the driver files.

    Returns: Dictionary of driver objects with a specified service type and
    vendor name

    """

    cutils = utils.ConfiguratorUtils()
    return cutils.load_drivers(const.DRIVERS_DIR)


def register_service_agent(cm, sc, conf, rpcmgr):
    """Registers generic configuration service agent with configurator module.

    :param cm: Instance of configurator module
    :param sc: Instance of core service controller
    :param conf: Instance of oslo configuration
    :param rpcmgr: Instance containing RPC methods which are invoked by
    configurator module on corresponding RPC message arrival

    """

    service_type = const.SERVICE_TYPE
    cm.register_service_agent(service_type, rpcmgr)


def init_agent(cm, sc, conf, nqueue):
    """Initializes generic configuration agent.

    :param cm: Instance of configuration module
    :param sc: Instance of core service controller
    :param conf: Instance of oslo configuration

    """

    try:
        drivers = load_drivers()
    except Exception as err:
        msg = ("Generic configuration agent failed to load service drivers. %s"
               % (str(err).capitalize()))
        LOG.error(msg)
        raise err
    else:
        msg = ("Generic configuration agent loaded service"
               " drivers successfully.")
        LOG.debug(msg)

    rpcmgr = GenericConfigRpcManager(sc, conf)

    try:
        events_init(sc, drivers, rpcmgr, nqueue)
    except Exception as err:
        msg = ("Generic configuration agent failed to initialize events. %s"
               % (str(err).capitalize()))
        LOG.error(msg)
        raise err
    else:
        msg = ("Generic configuration agent initialized"
               " events successfully.")
        LOG.debug(msg)

    try:
        register_service_agent(cm, sc, conf, rpcmgr)
    except Exception as err:
        msg = ("Failed to register generic configuration agent with"
               " configurator module. %s" % (str(err).capitalize()))
        LOG.error(msg)
        raise err
    else:
        msg = ("Generic configuration agent registered with configuration"
               " module successfully.")
        LOG.debug(msg)


def init_agent_complete(cm, sc, conf):
    LOG.info("Initialization of generic configuration agent completed.")
