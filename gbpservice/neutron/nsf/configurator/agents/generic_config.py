
from gbpservice.neutron.nsf.configurator.agents import agent_base
from gbpservice.neutron.nsf.configurator.lib import (
                            generic_config_constants as const)
from oslo_log import log as logging
from gbpservice.neutron.nsf.core import main
import os
from gbpservice.neutron.nsf.configurator.lib import utils
from gbpservice.neutron.nsf.core import periodic_task as core_periodic_task

LOG = logging.getLogger(__name__)

SUCCESS = 'SUCCESS'
FAILED = 'FAILED'
MAX_FAIL_COUNT = 5
INITIAL = 'initial'
FOREVER = 'forever'
INITIAL_HM_RETRIES = 12  # 5 secs delay * 12 = 120 secs

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

    def configure_healthmonitor(self, context, kwargs):
        """Enqueues event for worker to process configure healthmonitor request.

        :param context: RPC context
        :param kwargs: RPC Request data

        Returns: None

        """
        kwargs['fail_count'] = 0
        arg_dict = {'context': context,
                    'kwargs': kwargs}
        ev = self._sc.event(id=const.EVENT_CONFIGURE_HEALTHMONITOR,
                            data=arg_dict, key=kwargs['vmid'])
        self._sc.rpc_event(ev)

    def clear_healthmonitor(self, context, kwargs):
        """Enqueues event for worker to process clear healthmonitor request.

        :param context: RPC context
        :param kwargs: RPC Request data

        Returns: None

        """

        arg_dict = {'context': context,
                    'kwargs': kwargs}
        ev = self._sc.event(id=const.EVENT_CLEAR_HEALTHMONITOR,
                            data=arg_dict, key=kwargs['vmid'])
        self._sc.rpc_event(ev)


"""Implements event handlers and their helper methods.

Object of this class is registered with the event class of core service
controller. Based on the event key, handle_event method of this class is
invoked by core service controller.

"""


class GenericConfigEventHandler(agent_base.AgentBaseEventHandler,
                                core_periodic_task.PeriodicTasks):
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
        - Configure health monitor
        - Clear health monitor
        Enqueues responses into notification queue.

        Returns: None

        """

        try:
            # Process batch of request data blobs
            if ev.id == const.EVENT_PROCESS_BATCH:
                self.process_batch(ev)
                return
            # Process HM poll events
            elif ev.id == const.EVENT_CONFIGURE_HEALTHMONITOR:
                kwargs = ev.data.get('kwargs')
                periodicity = kwargs.get('periodicity')
                if periodicity == INITIAL:
                    self._sc.poll_event(ev, max_times=INITIAL_HM_RETRIES)
                elif periodicity == FOREVER:
                    self._sc.poll_event(ev)
                return
            else:
                self._process_event(ev)
        except Exception as err:
            msg = ("Failed to process event %s, reason %s " % (ev.data, err))
            LOG.error(msg)
            return

    def _process_event(self, ev):
        LOG.info(" Handling event %s " % (ev.data))
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

        notification_data = self._prepare_notification_data(service_type,
                                                            ev.id, context,
                                                            result,
                                                            notification_data)
        if ev.id == const.EVENT_CONFIGURE_HEALTHMONITOR:
            if (kwargs.get('periodicity') == INITIAL and
                    result == SUCCESS):
                    LOG.info("Even handling done successfully %s "
                             "sending notification_data=%s " % (
                                                            ev.data,
                                                            notification_data))
                    self._sc.poll_event_done(ev)
                    self.nqueue.put(notification_data)
            elif kwargs.get('periodicity') == FOREVER:
                    if result == FAILED:
                        # If health monitoring fails continuously for 5 times
                        # send fail notification to orchestrator
                        kwargs['fail_count'] = kwargs.get('fail_count') + 1
                        if kwargs.get('fail_count') >= MAX_FAIL_COUNT:
                            self._sc.poll_event_done(ev)
                            self.nqueue.put(notification_data)
                    elif result == SUCCESS:
                        # set fail_count to 0 if it had failed earlier even
                        # once
                        kwargs['fail_count'] = 0
        elif ev.id == const.EVENT_CLEAR_HEALTHMONITOR:
            # Stop current poll event. event.key is vmid which will stop
            # that particular service vm's health monitor
            self._sc.poll_event_done(ev)
            self.nqueue.put(notification_data)
        # For other events, irrespective of result send notification
        else:
            LOG.info("Even handling done successfully %s "
                     "Sending notification_data=%s" % (ev.data,
                                                       notification_data))
            self.nqueue.put(notification_data)

    def _prepare_notification_data(self, service_type, method, context, result,
                                   notification_data):
        msg = {'receiver': const.ORCHESTRATOR,
               'resource': service_type,
               'method': method,
               'kwargs': [{'context': context, 'result': result}]
               }
        if not notification_data:
            notification_data.update(msg)
        else:
            data = {'context': context,
                    'result': result}
            notification_data['kwargs'].extend(data)
        return notification_data

    def poll_event_cancel(self, ev):
        LOG.error('Health monitoring failed for event %s ' % (ev.data))
        kwargs = ev.data.get('kwargs')
        context = ev.data.get('context')
        service_type = kwargs.get('service_type')
        notification_data = context.get('notification_data')
        del context['notification_data']
        result = FAILED
        notification_data = self._prepare_notification_data(
                                                        service_type,
                                                        ev.id, context,
                                                        result,
                                                        notification_data)
        self.nqueue.put(notification_data)

    @core_periodic_task.periodic_task(event=const.EVENT_CONFIGURE_HEALTHMONITOR,
                                      spacing=5)
    def handle_configure_healthmonitor(self, ev):
        self._process_event(ev)


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
        main.Event(id=const.EVENT_CONFIGURE_HEALTHMONITOR,
                   handler=GenericConfigEventHandler(
                                        sc, drivers, rpcmgr, nqueue)),
        main.Event(id=const.EVENT_CLEAR_HEALTHMONITOR,
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
