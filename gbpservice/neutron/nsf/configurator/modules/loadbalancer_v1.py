import os
import oslo_messaging as messaging

from oslo_config import cfg
from oslo_log import log as logging

from neutron import context
from neutron.common import exceptions as n_exc
from gbpservice.neutron.nsf.configurator.lib import lb_constants as const
from gbpservice.neutron.nsf.core.main import Event
from gbpservice.neutron.nsf.core.main import RpcAgent
#from gbpservice.neutron.nsf.configurator.lib.filter import Filter
from gbpservice.neutron.nsf.core import periodic_task as core_periodic_task
from gbpservice.neutron.nsf.configurator.drivers.loadbalancer.v1.\
 haproxy.haproxy_lb_driver import HaproxyOnVmDriver

LOG = logging.getLogger(__name__)


class DeviceNotFoundOnAgent(n_exc.NotFound):
    msg = _('Unknown device with pool_id %(pool_id)s')


class LBaasRpcSender(object):
    """Agent side of the Agent to Plugin RPC API."""

    API_VERSION = '2.0'
    # history
    #   1.0 Initial version
    #   2.0 Generic API for agent based drivers
    #       - get_logical_device() handling changed on plugin side;
    #       - pool_deployed() and update_status() methods added;

    def __init__(self, topic, context, host):
        '''TODO:(pritam) Call constructor of Filter class
        super(LBaasRpcSender, self).__init__(topic, self.API_VERSION)
        '''
        self.context = context
        self.host = host

    def get_logical_device(self, pool_id):
        # Call goes to filter library
        return self.call(
            self.context,
            self.make_msg(
                'get_logical_device',
                pool_id=pool_id
            )
        )

    def update_status(self, obj_type, obj_id, status):
        LOG.info("[LbaaSRpcSender]: Update status called")
        """
        '''TODO:(pritam) Enqueue event in ResponseQ
        '''
        return self.call(
            self.context,
            self.make_msg('update_status', obj_type=obj_type, obj_id=obj_id,
                          status=status)
        )
        """

    def update_pool_stats(self, pool_id, stats):
        LOG.info("[LbaaSRpcSender]: Update pool stats called")
        """
        '''TODO:(pritam) Enqueue event in ResponseQ
        '''
        return self.call(
            self.context,
            self.make_msg(
                'update_pool_stats',
                pool_id=pool_id,
                stats=stats,
                host=self.host
            )
        )
        """

    def resource_deleted(self, obj_type, obj_id):
        LOG.info("[LbaaSRpcSender]: resource deleted called called")
        """
        '''TODO:(pritam) Enqueue event in ResponseQ
        '''
        return self.call(
            self.context,
            self.make_msg('resource_deleted', obj_type=obj_type, obj_id=obj_id)
        )
        """


class LBaasRpcReceiver(object):
    """
    APIs for receiving RPC messages from LBaaS plugin.
    """
    RPC_API_VERSION = '1.0'
    target = messaging.Target(version=RPC_API_VERSION)

    def __init__(self, conf, sc):
        super(LBaasRpcReceiver, self).__init__()
        self.conf = conf
        self._sc = sc

    def create_vip(self, context, vip):

        arg_dict = {'context': context,
                    'vip': vip
                    # TODO:(pritam)
                    # 'serialize': True,
                    # 'binding_key': vip['id']
                    }
        ev = self._sc.event(id='CREATE_VIP', data=arg_dict)
        self._sc.rpc_event(ev)

    def update_vip(self, context, old_vip, vip):
        arg_dict = {'context': context,
                    'old_vip': old_vip,
                    'vip': vip}
        ev = self._sc.event(id='UPDATE_VIP', data=arg_dict)
        self._sc.rpc_event(ev)

    def delete_vip(self, context, vip):

        arg_dict = {'context': context,
                    'vip': vip}
        ev = self._sc.event(id='DELETE_VIP', data=arg_dict)
        self._sc.rpc_event(ev)

    def create_pool(self, context, pool, driver_name):

        arg_dict = {'context': context,
                    'pool': pool,
                    'driver_name': driver_name}
        ev = self._sc.event(id='CREATE_POOL', data=arg_dict)
        self._sc.rpc_event(ev)

    def update_pool(self, context, old_pool, pool):
        arg_dict = {'context': context,
                    'old_pool': old_pool,
                    'pool': pool}

        ev = self._sc.event(id='UPDATE_POOL', data=arg_dict)
        self._sc.rpc_event(ev)

    def delete_pool(self, context, pool):

        arg_dict = {'context': context,
                    'pool': pool}
        ev = self._sc.event(id='DELETE_POOL', data=arg_dict)
        self._sc.rpc_event(ev)

    def create_member(self, context, member):

        arg_dict = {'context': context,
                    'member': member}
        ev = self._sc.event(id='CREATE_MEMBER', data=arg_dict)
        self._sc.rpc_event(ev)

    def update_member(self, context, old_member, member):
        arg_dict = {'context': context,
                    'old_member': old_member,
                    'member': member}
        ev = self._sc.event(id='UPDATE_MEMBER', data=arg_dict)
        self._sc.rpc_event(ev)

    def delete_member(self, context, member):
        arg_dict = {'context': context,
                    'member': member}
        ev = self._sc.event(id='DELETE_MEMBER', data=arg_dict)
        self._sc.rpc_event(ev)

    def create_pool_health_monitor(self, context, health_monitor, pool_id):

        arg_dict = {'context': context,
                    'health_monitor': health_monitor,
                    'pool_id': pool_id}
        ev = self._sc.event(id='CREATE_POOL_HEALTH_MONITOR', data=arg_dict)
        self._sc.rpc_event(ev)

    def update_pool_health_monitor(self, context, old_health_monitor,
                                   health_monitor, pool_id):
        arg_dict = {'context': context,
                    'old_health_monitor': old_health_monitor,
                    'health_monitor': health_monitor,
                    'pool_id': pool_id}
        ev = self._sc.event(id='UPDATE_POOL_HEALTH_MONITOR', data=arg_dict)
        self._sc.rpc_event(ev)

    def delete_pool_health_monitor(self, context, health_monitor, pool_id):

        arg_dict = {'context': context,
                    'health_monitor': health_monitor,
                    'pool_id': pool_id}
        ev = self._sc.event(id='DELETE_POOL_HEALTH_MONITOR', data=arg_dict)
        self._sc.rpc_event(ev)

    def agent_updated(self, context, payload):
        """Handle the agent_updated notification event."""
        arg_dict = {'context': context,
                    'payload': payload}
        ev = self._sc.event(id='AGENT_UPDATED', data=arg_dict)
        self._sc.rpc_event(ev)


class LBaasHandler(core_periodic_task.PeriodicTasks):
    """Handler class for demultiplexing LBaaS rpc requests
    from LBaaS plugin and sending to appropriate driver.
    """

    def __init__(self, sc, drivers):
        self._sc = sc
        self.drivers = drivers
        self.context = context.get_admin_context_without_session()
        self.plugin_rpc = LBaasRpcSender(const.LBAAS_AGENT_RPC_TOPIC,
                                         self.context,
                                         cfg.CONF.host)
        self.instance_mapping = {}

    def _get_driver(self, pool_id):
        if pool_id not in self.instance_mapping:
            raise DeviceNotFoundOnAgent(pool_id=pool_id)

        driver_name = self.instance_mapping[pool_id]
        return self.drivers[driver_name]

    def handle_event(self, ev):
        try:
            msg = ("Worker process with ID: %s starting "
                   "to handle task: %s of topic: %s. "
                   % (os.getpid(), ev.id, const.LBAAS_AGENT_RPC_TOPIC))
            LOG.debug(msg)

            method = getattr(self, "_%s" % (ev.id.lower()))
            method(ev)
        except Exception as err:
            LOG.error("Failed to perform the operation: %s. %s"
                      % (ev.id, str(err).capitalize()))
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
            driver.create_vip(vip,context)
        except Exception:
            self._handle_failed_driver_call('create', 'vip', vip['id'],
                                            driver.get_name())
        else:
            self.plugin_rpc.update_status('vip', vip['id'],
                                          const.ACTIVE)

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
                                          const.ACTIVE)

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
                                          const.ERROR)
            return
        driver = self.drivers[driver_name]
        try:
            driver.create_pool(pool, context)
        except Exception:
            self._handle_failed_driver_call('create', 'pool',
                                            pool['id'],
                                            driver.get_name())
        else:
            self.instance_mapping[pool['id']] = driver_name
            self.plugin_rpc.update_status('pool', pool['id'],
                                          const.ACTIVE)

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
                                          const.ACTIVE)

    def _delete_pool(self, ev):
        data = ev.data
        context = data['context']
        pool = data['pool']
        driver = self._get_driver(pool['id'])
        try:
            driver.delete_pool(pool, context)
        except Exception:
            LOG.warn(_("Failed to delete pool %s"), pool['id'])
        del self.instance_mapping[pool['id']]

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
                                          const.ACTIVE)

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
                                          const.ACTIVE)

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
                'health_monitor', assoc_id, const.ACTIVE)

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
                'health_monitor', assoc_id, const.ACTIVE)

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
                       " Health monitor: %s, Pool: %s"),
                     health_monitor['id'], pool_id)

    def _agent_updated(self, ev):
        """ TODO:(pritam): Support """
        return None

    def _handle_failed_driver_call(self, operation, obj_type, obj_id, driver):
        LOG.exception(_('%(operation)s %(obj)s %(id)s failed on device driver '
                        '%(driver)s'),
                      {'operation': operation.capitalize(), 'obj': obj_type,
                       'id': obj_id, 'driver': driver})
        self.plugin_rpc.update_status(obj_type, obj_id, const.ERROR)

    def _collect_stats(self, ev):
        self._sc.poll_event(ev)

    @core_periodic_task.periodic_task(event='COLLECT_STATS', spacing=60)
    def collect_stats(self, ev):
        for pool_id, driver_name in self.instance_mapping.items():
            driver = self.device_drivers[driver_name]
            try:
                stats = driver.get_stats(pool_id)
                if stats:
                    self.plugin_rpc.update_pool_stats(pool_id, stats)
            except Exception:
                LOG.exception(_('Error updating statistics on pool %s'),
                              pool_id)


class LBGenericConfigRpcReceiver(object):

    """
    APIs for receiving RPC messages from Orchestrator plugin.
    """
    RPC_API_VERSION = '1.0'
    target = messaging.Target(version=RPC_API_VERSION)

    def __init__(self, conf, sc):
        super(LBGenericConfigRpcReceiver, self).__init__()
        self.conf = conf
        self._sc = sc

    def configure_interfaces(self, context, **kwargs):
        arg_dict = {'context': context,
                    'kwargs': kwargs}
        ev = self._sc.event(id='CONFIGURE_INTERFACES', data=arg_dict)
        self._sc.rpc_event(ev)

    def clear_interfaces(self, context, vm_mgmt_ip, service_vendor,
                         provider_interface_position,
                         stitching_interface_position):
        '''TODO:(pritam) receive all arguments in kwargs '''
        arg_dict = {'context': context,
                    'vm_mgmt_ip': vm_mgmt_ip,
                    'service_vendor': service_vendor,
                    'provider_interface_position': provider_interface_position,
                    'stitching_interface_position':
                        stitching_interface_position}
        ev = self._sc.event(id='CLEAR_INTERFACES', data=arg_dict)
        self._sc.rpc_event(ev)

    def configure_source_routes(self, context, vm_mgmt_ip, service_vendor,
                                source_cidrs, destination_cidr, gateway_ip,
                                provider_interface_position):
        '''TODO:(pritam) receive all arguments in kwargs '''
        arg_dict = {'context': context,
                    'vm_mgmt_ip': vm_mgmt_ip,
                    'service_vendor': service_vendor,
                    'source_cidrs': source_cidrs,
                    'destination_cidr': destination_cidr,
                    'gateway_ip': gateway_ip,
                    'provider_interface_position': (
                                        provider_interface_position)}
        ev = self._sc.event(id='CONFIGURE_SOURCE_ROUTES', data=arg_dict)
        self._sc.rpc_event(ev)

    def clear_source_routes(self, context, vm_mgmt_ip, service_vendor,
                            source_cidrs, provider_interface_position):
        '''TODO:(pritam) receive all arguments in kwargs '''
        arg_dict = {'context': context,
                    'vm_mgmt_ip': vm_mgmt_ip,
                    'service_vendor': service_vendor,
                    'source_cidrs': source_cidrs,
                    'provider_interface_position': (
                                    provider_interface_position)}
        ev = self._sc.event(id='CLEAR_SOURCE_ROUTES', data=arg_dict)
        self._sc.rpc_event(ev)


class LBaasGenericConfigHandler():
    """Handler class for demultiplexing LbaaS configuration
       requests from Orchestrator and sending to appropriate driver.
    """

    def __init__(self, sc, drivers):
        self._sc = sc
        self.drivers = drivers

    def _get_driver(self, data):
        """TODO:(pritam) Do demultiplexing logic based on vendor
           when a different vendor comes.
        """
        return self.drivers["haproxy_on_vm"]

    def handle_event(self, ev):
        try:
            msg = ("Worker process with ID: %s starting "
                   "to handle task: %s of topic: %s. "
                   % (os.getpid(), ev.id,
                      const.LBAAS_GENERIC_CONFIG_RPC_TOPIC))
            LOG.debug(msg)

            driver = self._get_driver(ev.data)
            method = getattr(driver, "%s" % (ev.id.lower()))
            method(ev)
        except Exception as err:
            LOG.error("Failed to perform the operation: %s. %s"
                      % (ev.id, str(err).capitalize()))
        #finally:
        #    self._sc.event_done(ev)


def _create_rpc_agent(sc, topic, manager, agent_state=None):
    return RpcAgent(sc, cfg.CONF.host, topic, manager, agent_state)


def rpc_init(sc, conf):

    agent_state = {
        'binary': 'nsf-lb-module',
        'host': conf.host,
        'topic': const.LBAAS_AGENT_RPC_TOPIC,
        'report_interval': 10,
        'plugin_topic': const.LBAAS_PLUGIN_RPC_TOPIC,
        'configurations': {'device_drivers': 'haproxy_on_vm'},
        'agent_type': const.AGENT_TYPE_LOADBALANCER,
        'start_flag': True,
    }

    lb_rpc_mgr = LBaasRpcReceiver(conf, sc)
    lb_generic_rpc_mgr = LBGenericConfigRpcReceiver(conf, sc)

    lb_agent = _create_rpc_agent(sc, const.LBAAS_AGENT_RPC_TOPIC, lb_rpc_mgr,
                                 agent_state)
    lb_generic_agent = _create_rpc_agent(
                                    sc,
                                    const.LBAAS_GENERIC_CONFIG_RPC_TOPIC,
                                    lb_generic_rpc_mgr)

    sc.register_rpc_agents([lb_agent, lb_generic_agent])


def events_init(sc, drivers):
    evs = [
        # Events for LBaaS standard RPCs coming from LBaaS Plugin
        Event(id='CREATE_VIP', handler=LBaasHandler(sc, drivers)),
        Event(id='UPDATE_VIP', handler=LBaasHandler(sc, drivers)),
        Event(id='DELETE_VIP', handler=LBaasHandler(sc, drivers)),

        Event(id='CREATE_POOL', handler=LBaasHandler(sc, drivers)),
        Event(id='UPDATE_POOL', handler=LBaasHandler(sc, drivers)),
        Event(id='DELETE_POOL', handler=LBaasHandler(sc, drivers)),

        Event(id='CREATE_MEMBER', handler=LBaasHandler(sc, drivers)),
        Event(id='UPDATE_MEMBER', handler=LBaasHandler(sc, drivers)),
        Event(id='DELETE_MEMBER', handler=LBaasHandler(sc, drivers)),

        Event(id='CREATE_POOL_HEALTH_MONITOR', handler=LBaasHandler(
                                                                sc, drivers)),
        Event(id='UPDATE_POOL_HEALTH_MONITOR', handler=LBaasHandler(
                                                                sc, drivers)),
        Event(id='DELETE_POOL_HEALTH_MONITOR', handler=LBaasHandler(
                                                                sc, drivers)),
        Event(id='AGENT_UPDATED', handler=LBaasHandler(sc, drivers)),
        Event(id='COLLECT_STATS', handler=LBaasHandler(sc, drivers)),

        # Events for Generic configuration RPCs coming from Orchestrator
        Event(id='CONFIGURE_INTERFACES', handler=LBaasGenericConfigHandler(
                                                               sc, drivers)),
        Event(id='CLEAR_INTERFACES', handler=LBaasGenericConfigHandler(
                                                               sc, drivers)),
        Event(id='CONFIGURE_SOURCE_ROUTES', handler=LBaasGenericConfigHandler(
                                                               sc, drivers)),
        Event(id='CLEAR_SOURCE_ROUTES', handler=LBaasGenericConfigHandler(
                                                               sc, drivers)),
        ]
    sc.register_events(evs)


def load_drivers():
    ''' Create objects of lb drivers.
        TODO:(pritam) We need to make load_drivers() work by dynamic class
         detection from the driver directory and instantiate objects out of it.
    '''
    ctxt = context.get_admin_context_without_session()
    plugin_rpc = LBaasRpcSender(const.LBAAS_AGENT_RPC_TOPIC,
                                ctxt,
                                cfg.CONF.host)

    drivers = {'haproxy_on_vm': HaproxyOnVmDriver(None, plugin_rpc)}
    return drivers


def _start_collect_stats(sc):
    arg_dict = {}
    ev = sc.event(id='COLLECT_STATS', data=arg_dict)
    sc.rpc_event(ev)


def init_complete(sc, conf):
    _start_collect_stats(sc)


def module_init(sc, conf):
    try:
        drivers = load_drivers()
    except Exception as err:
        LOG.error("Failed to load drivers. %s"
                  % (str(err).capitalize()))
        raise err
    else:
        LOG.debug("Loaded drivers successfully.")
    try:
        events_init(sc, drivers)
    except Exception as err:
        LOG.error("Events initialization unsuccessful. %s"
                  % (str(err).capitalize()))
        raise err
    else:
        LOG.debug("Events initialization successful.")

    msg = ("RPC topics are: %s and %s."
           % (const.LBAAS_AGENT_RPC_TOPIC,
              const.LBAAS_GENERIC_CONFIG_RPC_TOPIC))
    try:
        rpc_init(sc, conf)
    except Exception as err:
        LOG.error("RPC initialization unsuccessful. " +
                  msg + " %s." % str(err).capitalize())
        raise err
    else:
        LOG.debug("RPC initialization successful. " + msg)

    msg = ("LOADBALANCER as a Service Module Initialized.")
    LOG.info(msg)
