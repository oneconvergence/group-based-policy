
from gbpservice.neutron.nsf.configurator.agents import agent_base
from gbpservice.neutron.nsf.configurator.lib import (
                            generic_config_constants as const)
from oslo_log import log as logging
from gbpservice.neutron.nsf.core import main
import os
import oslo_messaging as messaging
from gbpservice.neutron.nsf.core import queue
from gbpservice.neutron.nsf.configurator.lib import utils

LOG = logging.getLogger(__name__)


"""Implements APIs invoked by configurator for processing RPC messages.

RPC client of configurator module receives RPC messages from REST server
and invokes the API of this class. The instance of this class is registered
with configurator module using register_service_agent API. Configurator module
identifies the service agent object based on service type and invokes ones of
the methods of this class to configure the device.

"""

class GenericConfigRpcManager(agent_base.AgentBase):
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

class GenericConfigEventHandler(object):
    def __init__(self, sc, drivers, rpcmgr):
        self._sc = sc
        self.drivers = drivers
        self._rpcmgr = rpcmgr
        self.qu = queue.Queue(sc)

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

    def _process_batch(self, ev):
        """Processes a request with multiple data blobs.
        
        Configurator processes the request with multiple data blobs and sends
        a list of service information to be processed. This function goes
        through the list of service information and invokes specific service
        driver methods. After processing each request data blob, notification
        data blob is prepared.

        :param ev: Event instance that contains information of event type and
        corresponding event data to be processed.

        """

        try:
            # Get service agent information list and notification data list
            # from the event data
            sa_info_list = ev.data.get('sa_info_list')
            notification_data = ev.data.get('notification_data')
            
            # Process the first data blob from the service information list.
            # Get necessary parameters needed for driver method invocation.
            method = sa_info_list[0]['method']
            kwargs = sa_info_list[0]['kwargs']
            service_type = kwargs.get('kwargs').get('service_type')
            
            # Get the service driver and invoke its method
            driver = self._get_driver(service_type)
            context = ev.data.get('context')
            
            # Service driver should return "success" on successful API
            # processing. All other return values and exceptions are treated
            # as failures.
            result = getattr(driver, method)(context, **kwargs)
        except Exception as err:
            result = ("Failed to process %s request for %s service type. %s" %
                      (method, service_type, str(err).capitalize()))
            
            # Prepare the failure notification and enqueue in
            # notification queue
            msg = {'receiver': const.ORCHESTRATOR,
                   'resource': service_type,
                   'method': "network_function_device_notification",
                   'kwargs': [{'context': context, 'result': result}]
                }
            self.qu.put(msg)
            raise Exception(err)
        else:
            # Prepare success notification and populate notification data list
            msg = {'receiver': const.ORCHESTRATOR,
                   'resource': service_type,
                   'method': "network_function_device_notification",
                   'kwargs': [{'context': context, 'result': result}]
                }

            # If the data processed is first one, then prepare notification
            # dict. Otherwise, append the notification to the kwargs list.
            # Whether it is a data batch or single data blob request,
            # notification generated will be single dictionary. In case of
            # batch, multiple notifications are sent in the kwargs list.
            if (0 == len(notification_data)):
                notification_data.extend(msg)
            else:
                data = {'context': context,
                        'result': result}
                notification_data[0]['kwargs'].extend(data)
        
            # Remove the processed request data blob from the service
            # information list. APIs will always process first data blob in
            # the request.
            sa_info_list.pop(0)
            
            # Invoke base class method to process further data blobs in the
            # request
            self._rpcmgr.process_request(context,
                                         sa_info_list, notification_data)

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
                self._process_batch(ev)
                return
        except Exception as err:
            msg = ("Failed to process data batch. %s" %
                      str(err).capitalize())
            LOG.error(msg)
            return

        # Process single request data blob
        kwargs = ev.data.get('kwargs')
        service_type = kwargs.get('service_type')
        try:
            msg = ("Worker process with ID: %s starting "
                   "to handle task: %s for service type: %s. "
                   % (os.getpid(), ev.id, str(service_type)))
            LOG.debug(msg)

            driver = self._get_driver(service_type)
            context = ev.data.get('context')

            # Invoke service driver methods based on event type received
            if ev.id == 'CONFIGURE_INTERFACES':
                result = driver.configure_interfaces(context, kwargs)
            elif ev.id == 'CLEAR_INTERFACES':
                result = driver.clear_interfaces(context, kwargs)
            elif ev.id == 'CONFIGURE_ROUTES':
                result = driver.configure_source_routes(context, kwargs)
            elif ev.id == 'CLEAR_ROUTES':
                result = driver.delete_source_routes(context, kwargs)
            else:
                msg = ("Invalid event %s received for %s service type." %
                       (ev.id, service_type))
                LOG.error(msg)
                raise Exception(msg)

            msg = {'receiver': const.ORCHESTRATOR,
                   'resource': service_type,
                   'method': ev.id.lower(),
                   'kwargs': [{'context': context, 'result': result}]
                   }
            self.qu.put(msg)
        except Exception as err:
            result = ("Failed to process %s request for %s service type. %s" %
                      (ev.id.lower(), service_type, str(err).capitalize()))

            msg = {'receiver': const.ORCHESTRATOR,
                   'resource': service_type,
                   'method': ev.id.lower(),
                   'kwargs': [{'context': context, 'result': result}]
                   }
            self.qu.put(msg)
            LOG.error(result)


def events_init(sc, drivers, rpcmgr):
    """Registers events with core service controller.
    
    All the events will come to handle_event method of class instance
    registered in 'handler' field.
    
    :param drivers: Driver instances registered with the service agent
    :param rpcmgr: Instance to receive all the RPC messages from configurator
    module.
    
    Returns: None

    """

    evs = [
        main.Event(id='CONFIGURE_INTERFACES',
                   handler=GenericConfigEventHandler(sc, drivers, rpcmgr)),
        main.Event(id='CLEAR_INTERFACES',
                   handler=GenericConfigEventHandler(sc, drivers, rpcmgr)),
        main.Event(id='CONFIGURE_ROUTES',
                   handler=GenericConfigEventHandler(sc, drivers, rpcmgr)),
        main.Event(id='CLEAR_ROUTES',
                   handler=GenericConfigEventHandler(sc, drivers, rpcmgr)),
        main.Event(id='PROCESS_BATCH',
                   handler=GenericConfigEventHandler(sc, drivers, rpcmgr))
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


def init_agent(cm, sc, conf):
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
        events_init(sc, drivers, rpcmgr)
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
