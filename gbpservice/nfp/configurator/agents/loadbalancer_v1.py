import os
import oslo_messaging as messaging

from gbpservice.nfp.configurator.agents import agent_base
from oslo_log import log as logging
from gbpservice.nfp.core.main import Event
from gbpservice.nfp.configurator.lib import utils
from gbpservice.nfp.configurator.lib.filter import Filter
from gbpservice.nfp.core import poll as nfp_poll
from gbpservice.nfp.configurator.lib import lb_constants

LOG = logging.getLogger(__name__)


class LBaasRpcSender(Filter):
    """Agent side of the Agent to Plugin RPC API."""

    API_VERSION = '2.0'
    # history
    #   1.0 Initial version
    #   2.0 Generic API for agent based drivers
    #       - get_logical_device() handling changed on plugin side;
    #       - pool_deployed() and update_status() methods added;

    def __init__(self, sc=None):
        self.sc = sc
        pass

    def _notification(self, data):
        LOG.info("Sending notification: %s" % data)
        event = self.sc.new_event(
            id='NOTIFICATION_EVENT', key='NOTIFICATION_EVENT', data=data)
        self.sc.poll_event(event)

    def get_logical_device(self, pool_id, context=None):
        # Call goes to filter library
        return self.call(
            context,
            self.make_msg(
                'get_logical_device',
                pool_id=pool_id
            )
        )

    def update_status(self, obj_type, obj_id, status):
        msg = {'receiver': lb_constants.NEUTRON,
               'resource': lb_constants.SERVICE_TYPE,
               'method': 'update_status',
               'kwargs': [{'obj_type': obj_type,
                           'obj_id': obj_id,
                           'status': status}]
               }
        self._notification(msg)

    def update_pool_stats(self, pool_id, stats):
        LOG.info("[LbaaSRpcSender]: Update pool stats called")
        msg = {'receiver': lb_constants.NEUTRON,
               'resource': lb_constants.SERVICE_TYPE,
               'method': 'update_pool_stats',
               'kwargs': [{'pool_id': pool_id,
                           'stats': stats}]
               }
        self._notification(msg)


"""Implements APIs invoked by configurator for processing RPC messages.

RPC client of configurator module receives RPC messages from REST server
and invokes the API of this class. The instance of this class is registered
with configurator module using register_service_agent API. Configurator module
identifies the service agent object based on service type and invokes ones of
the methods of this class to configure the device.

"""


class LBaaSRpcManager(agent_base.AgentBaseRPCManager):
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

        super(LBaaSRpcManager, self).__init__(sc, conf)

    def create_vip(self, context, vip):

        arg_dict = {'context': context,
                    'vip': vip,
                    'serialize': True,
                    'binding_key': vip['pool_id']
                    }
        ev = self._sc.new_event(id='CREATE_VIP', data=arg_dict)
        self._sc.post_event(ev)

    def update_vip(self, context, old_vip, vip):
        arg_dict = {'context': context,
                    'old_vip': old_vip,
                    'vip': vip,
                    'serialize': True,
                    'binding_key': vip['pool_id']
                    }
        ev = self._sc.new_event(id='UPDATE_VIP', data=arg_dict)
        self._sc.post_event(ev)

    def delete_vip(self, context, vip):

        arg_dict = {'context': context,
                    'vip': vip,
                    'serialize': True,
                    'binding_key': vip['pool_id']
                    }
        ev = self._sc.new_event(id='DELETE_VIP', data=arg_dict)
        self._sc.post_event(ev)

    def create_pool(self, context, pool, driver_name):

        arg_dict = {'context': context,
                    'pool': pool,
                    'driver_name': driver_name,
                    'serialize': True,
                    'binding_key': pool['id']
                    }
        ev = self._sc.new_event(id='CREATE_POOL', data=arg_dict)
        self._sc.post_event(ev)

    def update_pool(self, context, old_pool, pool):
        arg_dict = {'context': context,
                    'old_pool': old_pool,
                    'pool': pool,
                    'serialize': True,
                    'binding_key': pool['id']
                    }

        ev = self._sc.new_event(id='UPDATE_POOL', data=arg_dict)
        self._sc.post_event(ev)

    def delete_pool(self, context, pool):

        arg_dict = {'context': context,
                    'pool': pool,
                    'serialize': True,
                    'binding_key': pool['id']
                    }
        ev = self._sc.new_event(id='DELETE_POOL', data=arg_dict)
        self._sc.post_event(ev)

    def create_member(self, context, member):

        arg_dict = {'context': context,
                    'member': member,
                    'serialize': True,
                    'binding_key': member['pool_id']
                    }
        ev = self._sc.new_event(id='CREATE_MEMBER', data=arg_dict)
        self._sc.post_event(ev)

    def update_member(self, context, old_member, member):
        arg_dict = {'context': context,
                    'old_member': old_member,
                    'member': member,
                    'serialize': True,
                    'binding_key': member['pool_id']
                    }
        ev = self._sc.new_event(id='UPDATE_MEMBER', data=arg_dict)
        self._sc.post_event(ev)

    def delete_member(self, context, member):
        arg_dict = {'context': context,
                    'member': member,
                    'serialize': True,
                    'binding_key': member['pool_id']
                    }
        ev = self._sc.new_event(id='DELETE_MEMBER', data=arg_dict)
        self._sc.post_event(ev)

    def create_pool_health_monitor(self, context, health_monitor, pool_id):

        arg_dict = {'context': context,
                    'health_monitor': health_monitor,
                    'pool_id': pool_id,
                    'serialize': True,
                    'binding_key': pool_id
                    }
        ev = self._sc.new_event(id='CREATE_POOL_HEALTH_MONITOR', data=arg_dict)
        self._sc.post_event(ev)

    def update_pool_health_monitor(self, context, old_health_monitor,
                                   health_monitor, pool_id):
        arg_dict = {'context': context,
                    'old_health_monitor': old_health_monitor,
                    'health_monitor': health_monitor,
                    'pool_id': pool_id,
                    'serialize': True,
                    'binding_key': pool_id
                    }
        ev = self._sc.new_event(id='UPDATE_POOL_HEALTH_MONITOR', data=arg_dict)
        self._sc.post_event(ev)

    def delete_pool_health_monitor(self, context, health_monitor, pool_id):

        arg_dict = {'context': context,
                    'health_monitor': health_monitor,
                    'pool_id': pool_id,
                    'serialize': True,
                    'binding_key': pool_id
                    }
        ev = self._sc.new_event(id='DELETE_POOL_HEALTH_MONITOR', data=arg_dict)
        self._sc.post_event(ev)

    def agent_updated(self, context, payload):
        """Handle the agent_updated notification event."""
        arg_dict = {'context': context,
                    'payload': payload}
        ev = self._sc.new_event(id='AGENT_UPDATED', data=arg_dict)
        self._sc.post_event(ev)


"""Implements event handlers and their helper methods.

Object of this class is registered with the event class of core service
controller. Based on the event key, handle_event method of this class is
invoked by core service controller.

"""


class LBaaSEventHandler(nfp_poll.PollEventDesc):
    instance_mapping = {}

    def __init__(self, sc, drivers, rpcmgr, nqueue):
        self._sc = sc
        self.drivers = drivers
        self._rpcmgr = rpcmgr
        self.nqueue = nqueue
        self.plugin_rpc = LBaasRpcSender(sc)

    def _get_driver(self, service_type):
        """Retrieves service driver object based on service type input.

        Currently, service drivers are identified with service type. Support
        for single driver per service type is provided. When multi-vendor
        support is going to be provided, the driver should be selected based
        on both service type and vendor name.

        :param service_type: Service type - loadbalancer

        Returns: Service driver instance

        """
        service_type = 'loadbalancer'
        return self.drivers[service_type]

    def handle_event(self, ev):
        """Processes the generated events in worker context.

        Processes the following events.
        - create pool
        - update pool
        - delete pool
        - create vip
        - update vip
        - delete vip
        - create member
        - update member
        - delete member
        - create pool health monitor
        - update pool health monitor
        - delete pool health monitor
        - agent updated
        Enqueues responses into notification queue.

        Returns: None

        """

        # Process single request data blob
        try:
            msg = ("Worker process with ID: %s starting "
                   "to handle task: %s of topic: %s. "
                   % (os.getpid(), ev.id, lb_constants.LBAAS_AGENT_RPC_TOPIC))
            LOG.debug(msg)

            method = getattr(self, "_%s" % (ev.id.lower()))
            method(ev)
        except Exception as err:
            LOG.error("Failed to perform the operation: %s. %s"
                      % (ev.id, str(err).capitalize()))
            import traceback
            traceback.print_exc()
        """
        finally:
            if ev.id == 'COLLECT_STATS':
                '''Do not say event done for collect stats as it is
                   to be executed forever
                '''
                pass
            else:
                self._sc.event_done(ev)
        """

    def _create_vip(self, ev):
        data = ev.data
        context = data['context']
        vip = data['vip']
        driver = self._get_driver(vip['pool_id'])
        try:
            driver.create_vip(vip, context)
        except Exception:
            self._handle_failed_driver_call('create', 'vip', vip['id'],
                                            driver.get_name())
        else:
            self.plugin_rpc.update_status('vip', vip['id'],
                                          lb_constants.ACTIVE)

    def _update_vip(self, ev):
        data = ev.data
        context = data['context']
        old_vip = data['old_vip']
        vip = data['vip']
        driver = self._get_driver(vip['pool_id'])
        try:
            driver.update_vip(old_vip, vip, context)
        except Exception:
            self._handle_failed_driver_call('update', 'vip', vip['id'],
                                            driver.get_name())
        else:
            self.plugin_rpc.update_status('vip', vip['id'],
                                          lb_constants.ACTIVE)

    def _delete_vip(self, ev):
        data = ev.data
        context = data['context']
        vip = data['vip']
        driver = self._get_driver(vip['pool_id'])
        try:
            driver.delete_vip(vip, context)
        except Exception:
            LOG.warn(_("Failed to delete vip %s"), vip['id'])

    def _create_pool(self, ev):
        data = ev.data
        context = data['context']
        pool = data['pool']
        driver_name = data['driver_name']
        if driver_name not in self.drivers:
            LOG.error(_('No device driver on agent: %s.'), driver_name)
            self.plugin_rpc.update_status('pool', pool['id'],
                                          lb_constants.ERROR)
            return
        driver = self.drivers[driver_name]
        try:
            driver.create_pool(pool, context)
        except Exception:
            self._handle_failed_driver_call('create', 'pool',
                                            pool['id'],
                                            driver.get_name())
        else:
            LBaaSEventHandler.instance_mapping[pool['id']] = driver_name
            self.plugin_rpc.update_status('pool', pool['id'],
                                          lb_constants.ACTIVE)

    def _update_pool(self, ev):
        data = ev.data
        context = data['context']
        old_pool = data['old_pool']
        pool = data['pool']
        driver = self._get_driver(pool['id'])
        try:
            driver.update_pool(old_pool, pool, context)
        except Exception:
            self._handle_failed_driver_call('update', 'pool',
                                            pool['id'],
                                            driver  # driver.get_name()
                                            )
        else:
            self.plugin_rpc.update_status('pool', pool['id'],
                                          lb_constants.ACTIVE)

    def _delete_pool(self, ev):
        data = ev.data
        context = data['context']
        pool = data['pool']
        driver = self._get_driver(pool['id'])
        try:
            driver.delete_pool(pool, context)
        except Exception:
            LOG.warn(_("Failed to delete pool %s"), pool['id'])
        del LBaaSEventHandler.instance_mapping[pool['id']]

    def _create_member(self, ev):
        data = ev.data
        context = data['context']
        member = data['member']
        driver = self._get_driver(member['pool_id'])
        try:
            driver.create_member(member, context)
        except Exception:
            self._handle_failed_driver_call('create', 'member',
                                            member['id'],
                                            driver.get_name())
        else:
            self.plugin_rpc.update_status('member', member['id'],
                                          lb_constants.ACTIVE)

    def _update_member(self, ev):
        data = ev.data
        context = data['context']
        old_member = data['old_member']
        member = data['member']
        driver = self._get_driver(member['pool_id'])
        try:
            driver.update_member(old_member, member, context)
        except Exception:
            self._handle_failed_driver_call('update', 'member',
                                            member['id'],
                                            driver.get_name())
        else:
            self.plugin_rpc.update_status('member', member['id'],
                                          lb_constants.ACTIVE)

    def _delete_member(self, ev):
        data = ev.data
        context = data['context']
        member = data['member']
        driver = self._get_driver(member['pool_id'])
        try:
            driver.delete_member(member, context)
        except Exception:
            LOG.warn(_("Failed to delete member %s"), member['id'])

    def _create_pool_health_monitor(self, ev):
        data = ev.data
        context = data['context']
        health_monitor = data['health_monitor']
        pool_id = data['pool_id']
        driver = self._get_driver(pool_id)
        assoc_id = {'pool_id': pool_id,
                    'monitor_id': health_monitor['id']}
        try:
            driver.create_pool_health_monitor(health_monitor, pool_id, context)
        except Exception:
            self._handle_failed_driver_call(
             'create', 'health_monitor', assoc_id, driver.get_name())
        else:
            self.plugin_rpc.update_status(
                'health_monitor', assoc_id, lb_constants.ACTIVE)

    def _update_pool_health_monitor(self, ev):
        data = ev.data
        context = data['context']
        old_health_monitor = data['old_health_monitor']
        health_monitor = data['health_monitor']
        pool_id = data['pool_id']
        driver = self._get_driver(pool_id)
        assoc_id = {'pool_id': pool_id,
                    'monitor_id': health_monitor['id']}
        try:
            driver.update_pool_health_monitor(old_health_monitor,
                                              health_monitor,
                                              pool_id,
                                              context)
        except Exception:
            self._handle_failed_driver_call(
             'update', 'health_monitor', assoc_id, driver.get_name())
        else:
            self.plugin_rpc.update_status(
                'health_monitor', assoc_id, lb_constants.ACTIVE)

    def _delete_pool_health_monitor(self, ev):
        data = ev.data
        context = data['context']
        health_monitor = data['health_monitor']
        pool_id = data['pool_id']
        driver = self._get_driver(pool_id)
        assoc_id = {'pool_id': pool_id,
                    'monitor_id': health_monitor['id']}
        try:
            driver.delete_pool_health_monitor(health_monitor, pool_id, context)
        except Exception:
            LOG.warn(_("Failed to delete pool health monitor."
                       " assoc_id: %s"), assoc_id)

    def _agent_updated(self, ev):
        """ TODO:(pritam): Support """
        return None

    def _handle_failed_driver_call(self, operation, obj_type, obj_id, driver):
        LOG.error("Failed operation=%s,for obj_type=%s,obj_id=%s,"
                  "driver=%s " % (operation, obj_type, obj_id, driver))
        self.plugin_rpc.update_status(obj_type, obj_id, lb_constants.ERROR)

    def _collect_stats(self, ev):
        self._sc.poll_event(ev)

    @nfp_poll.poll_event_desc(event='COLLECT_STATS', spacing=60)
    def collect_stats(self, ev):
        for pool_id, driver_name in LBaaSEventHandler.instance_mapping.items():
            driver = self.drivers[driver_name]
            try:
                stats = driver.get_stats(pool_id)
                if stats:
                    self.plugin_rpc.update_pool_stats(pool_id, stats)
            except Exception:
                LOG.exception(_('Error updating statistics on pool %s'),
                              pool_id)


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
        # Events for LBaaS standard RPCs coming from LBaaS Plugin
        Event(id='CREATE_POOL', handler=LBaaSEventHandler(
                                                sc, drivers, rpcmgr, nqueue)),
        Event(id='UPDATE_POOL', handler=LBaaSEventHandler(
                                                sc, drivers, rpcmgr, nqueue)),
        Event(id='DELETE_POOL', handler=LBaaSEventHandler(
                                                sc, drivers, rpcmgr, nqueue)),
        Event(id='CREATE_VIP', handler=LBaaSEventHandler(
                                                sc, drivers, rpcmgr, nqueue)),
        Event(id='UPDATE_VIP', handler=LBaaSEventHandler(
                                                sc, drivers, rpcmgr, nqueue)),
        Event(id='DELETE_VIP', handler=LBaaSEventHandler(
                                                sc, drivers, rpcmgr, nqueue)),
        Event(id='CREATE_MEMBER', handler=LBaaSEventHandler(
                                                sc, drivers, rpcmgr, nqueue)),
        Event(id='UPDATE_MEMBER', handler=LBaaSEventHandler(
                                                sc, drivers, rpcmgr, nqueue)),
        Event(id='DELETE_MEMBER', handler=LBaaSEventHandler(
                                                sc, drivers, rpcmgr, nqueue)),
        Event(id='CREATE_POOL_HEALTH_MONITOR', handler=LBaaSEventHandler(
                                                sc, drivers, rpcmgr, nqueue)),
        Event(id='UPDATE_POOL_HEALTH_MONITOR', handler=LBaaSEventHandler(
                                                sc, drivers, rpcmgr, nqueue)),
        Event(id='DELETE_POOL_HEALTH_MONITOR', handler=LBaaSEventHandler(
                                                sc, drivers, rpcmgr, nqueue)),
        Event(id='AGENT_UPDATED', handler=LBaaSEventHandler(
                                                sc, drivers, rpcmgr, nqueue)),
        Event(id='COLLECT_STATS', handler=LBaaSEventHandler(
                                                sc, drivers, rpcmgr, nqueue))
        ]
    sc.register_events(evs)


def load_drivers(sc):
    """Imports all the driver files.

    Returns: Dictionary of driver objects with a specified service type and
    vendor name

    """
    cutils = utils.ConfiguratorUtils()
    drivers = cutils.load_drivers(lb_constants.DRIVERS_DIR)

    plugin_rpc = LBaasRpcSender(sc)

    for service_type, dobj in drivers.iteritems():
        '''LB Driver constructor needs plugin_rpc as a param'''
        instantiated_dobj = dobj(plugin_rpc)
        drivers[service_type] = instantiated_dobj

    return drivers


def register_service_agent(cm, sc, conf, rpcmgr):
    """Registers Loadbalaner service agent with configurator module.

    :param cm: Instance of configurator module
    :param sc: Instance of core service controller
    :param conf: Instance of oslo configuration
    :param rpcmgr: Instance containing RPC methods which are invoked by
    configurator module on corresponding RPC message arrival

    """

    service_type = 'loadbalancer'  # lb_constants.SERVICE_TYPE
    cm.register_service_agent(service_type, rpcmgr)


def init_agent(cm, sc, conf, nqueue):
    """Initializes Loadbalaner agent.

    :param cm: Instance of configuration module
    :param sc: Instance of core service controller
    :param conf: Instance of oslo configuration

    """

    try:
        drivers = load_drivers(sc)
    except Exception as err:
        msg = ("Loadbalaner agent failed to load service drivers. %s"
               % (str(err).capitalize()))
        LOG.error(msg)
        raise err
    else:
        msg = ("Loadbalaner agent loaded service"
               " drivers successfully.")
        LOG.debug(msg)

    rpcmgr = LBaaSRpcManager(sc, conf)

    try:
        events_init(sc, drivers, rpcmgr, nqueue)
    except Exception as err:
        msg = ("Loadbalaner agent failed to initialize events. %s"
               % (str(err).capitalize()))
        LOG.error(msg)
        raise err
    else:
        msg = ("Loadbalaner agent initialized"
               " events successfully.")
        LOG.debug(msg)

    try:
        register_service_agent(cm, sc, conf, rpcmgr)
    except Exception as err:
        msg = ("Failed to register Loadbalaner agent with"
               " configurator module. %s" % (str(err).capitalize()))
        LOG.error(msg)
        raise err
    else:
        msg = ("Loadbalaner agent registered with configuration"
               " module successfully.")
        LOG.debug(msg)


def _start_collect_stats(sc):
    arg_dict = {}
    ev = sc.new_event(id='COLLECT_STATS', data=arg_dict)
    sc.post_event(ev)


def init_agent_complete(cm, sc, conf):
    _start_collect_stats(sc)
    LOG.info("Initialization of loadbalancer agent completed.")
