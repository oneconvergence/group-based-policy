import os

from oslo_log import log as logging
import oslo_messaging as messaging

from gbpservice.neutron.nsf.configurator.agents.agent_base import AgentBase
from gbpservice.neutron.nsf.core.main import Event
from gbpservice.neutron.nsf.core.queue import Queue
from gbpservice.neutron.nsf.configurator.lib import (
                            generic_config_constants as const)
from gbpservice.neutron.nsf.configurator.lib import utils as load_driver

LOG = logging.getLogger(__name__)


class GenericConfigRpcManager(AgentBase):
    """
    APIs for receiving messages from Orchestrator.
    """
    RPC_API_VERSION = '1.0'
    target = messaging.Target(version=RPC_API_VERSION)

    def __init__(self, sc, conf):
        super(GenericConfigRpcManager, self).__init__(sc, conf)

    def configure_interfaces(self, context, kwargs):
        arg_dict = {'context': context,
                    'kwargs': kwargs}
        ev = self._sc.event(id='CONFIGURE_INTERFACES', data=arg_dict)
        self._sc.rpc_event(ev)

    def clear_interfaces(self, context, kwargs):
        arg_dict = {'context': context,
                    'kwargs': kwargs}
        ev = self._sc.event(id='CLEAR_INTERFACES', data=arg_dict)
        self._sc.rpc_event(ev)

    def configure_source_routes(self, context, kwargs):
        arg_dict = {'context': context,
                    'kwargs': kwargs}
        ev = self._sc.event(id='CONFIGURE_SOURCE_ROUTES', data=arg_dict)
        self._sc.rpc_event(ev)

    def delete_source_routes(self, context, kwargs):
        arg_dict = {'context': context,
                    'kwargs': kwargs}
        ev = self._sc.event(id='DELETE_SOURCE_ROUTES', data=arg_dict)
        self._sc.rpc_event(ev)


class GenericConfigEventHandler(object):
    """
    Handler class for demultiplexing firewall configuration
    requests from Orchestrator and sending to appropriate driver.
    """

    def __init__(self, sc, drivers, rpcmgr):
        self._sc = sc
        self.drivers = drivers
        self._rpcmgr = rpcmgr
        self.qu = Queue(sc)

    def _get_driver(self, service_type):
        ''' TO DO[DEE]: Do demultiplexing logic based on vendor too
                        when a different vendor comes.
        '''
        return self.drivers[service_type]()

    def _process_batch(self, ev):
        try:
            sa_info_list = ev.data.get('sa_info_list')
            notification_data = ev.data.get('notification_data')
            method = sa_info_list[0]['method']
            kwargs = sa_info_list[0]['kwargs']
            service_type = kwargs.get('kwargs').get('service_type')
            driver = self._get_driver(service_type)
            context = ev.data.get('context')
            result = getattr(driver, method)(context, **kwargs)
        except Exception as err:
            result = ("Failed to %s for %s. " %
                      (ev.id.lower(), service_type) + str(err).capitalize())
            msg = {'receiver': const.ORCHESTRATOR,
                   'resource': service_type,
                   'method': "network_function_device_notification",
                   'kwargs': [{'context': context,
                               'result': result}]
                   }
            self.qu.put(msg)
            LOG.error(result)
            return

        msg = {'receiver': const.ORCHESTRATOR,
               'resource': service_type,
               'method': "network_function_device_notification",
               'kwargs': [{'context': context,
                        'result': result}]
            }
        if (len(notification_data) == 0):
            notification_data.extend(msg)
        else:
            data = {'context': context,
                    'result': result}
            notification_data[0]['kwargs'].extend(data)

        sa_info_list.pop(0)
        self._rpcmgr.process_request(context, sa_info_list, notification_data)

    def handle_event(self, ev):
        try:
            if ev.id == 'PROCESS_BATCH':
                self._process_batch(ev)
                return
        except Exception as err:
            result = ("Failed to %s. " % (ev.id.lower()) +
                      str(err).capitalize())
            LOG.error(result)
            return

        kwargs = ev.data.get('kwargs')
        service_type = kwargs.get('service_type')
        try:
            msg = ("Worker process with ID: %s starting "
                   "to handle task: %s for service type: %s. "
                   % (os.getpid(), ev.id, str(service_type)))
            LOG.debug(msg)

            driver = self._get_driver(service_type)
            context = ev.data.get('context')

            if ev.id == 'CONFIGURE_INTERFACES':
                result = driver.configure_interfaces(context, kwargs)
            elif ev.id == 'CLEAR_INTERFACES':
                result = driver.clear_interfaces(context, kwargs)
            elif ev.id == 'CONFIGURE_SOURCE_ROUTES':
                result = driver.configure_source_routes(context, kwargs)
            elif ev.id == 'DELETE_SOURCE_ROUTES':
                result = driver.delete_source_routes(context, kwargs)
            else:
                msg = ("Wrong call from Orchestrator to configure %s generic "
                       "configurations." % service_type)
                LOG.error(msg)
                raise Exception(msg)

            msg = {'receiver': const.ORCHESTRATOR,
                   'resource': service_type,
                   'method': ev.id.lower(),
                   'data': {'context': context,
                            'result': result}
                   }
            self.qu.put(msg)
        except Exception as err:
            result = ("Failed to %s for %s. " % (ev.id.lower(), service_type) +
                      str(err).capitalize())
            msg = {'receiver': const.ORCHESTRATOR,
                   'resource': service_type,
                   'method': ev.id.lower(),
                   'data': {'context': context,
                            'result': result}
                   }
            self.qu.put(msg)
            LOG.error(result)


def events_init(sc, drivers, rpcmgr):
    evs = [
        Event(id='CONFIGURE_INTERFACES',
              handler=GenericConfigEventHandler(sc, drivers, rpcmgr)),
        Event(id='CLEAR_INTERFACES',
              handler=GenericConfigEventHandler(sc, drivers, rpcmgr)),
        Event(id='CONFIGURE_SOURCE_ROUTES',
              handler=GenericConfigEventHandler(sc, drivers, rpcmgr)),
        Event(id='DELETE_SOURCE_ROUTES',
              handler=GenericConfigEventHandler(sc, drivers, rpcmgr)),
        Event(id='PROCESS_BATCH',
              handler=GenericConfigEventHandler(sc, drivers, rpcmgr))]
    sc.register_events(evs)


def load_drivers():
    ld = load_driver.ConfiguratorUtils()
    return ld.load_drivers(const.DRIVERS_DIR)


def register_service_agent(cm, sc, conf, rpcmgr):
    service_type = const.SERVICE_TYPE
    cm.register_service_agent(service_type, rpcmgr)


def init_agent(cm, sc, conf):
    try:
        drivers = load_drivers()
    except Exception as err:
        LOG.error("GenericConfig Agent failed to load drivers. %s"
                  % (str(err).capitalize()))
        raise err
    else:
        LOG.debug("GenericConfig Agent loaded drivers successfully.")

    rpcmgr = GenericConfigRpcManager(sc, conf)
    
    try:
        events_init(sc, drivers, rpcmgr)
    except Exception as err:
        LOG.error("GenericConfig events initialization unsuccessful. %s"
                  % (str(err).capitalize()))
        raise err
    else:
        LOG.debug("GenericConfig events initialization successful.")

    try:
        register_service_agent(cm, sc, conf, rpcmgr)
    except Exception as err:
        LOG.error("GenericConfig service agent registration unsuccessful. %s"
                  % (str(err).capitalize()))
        raise err
    else:
        LOG.debug("GenericConfig service agent registration successful.")

    msg = ("GenericConfig Agent Initialized.")
    LOG.info(msg)


def init_agent_complete(cm, sc, conf):
    LOG.info(" GenericConfig agent init complete")
