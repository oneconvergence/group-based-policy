# One Convergence, Inc. CONFIDENTIAL
# Copyright (c) 2012-2015, One Convergence, Inc., USA
# All Rights Reserved.
#
# All information contained herein is, and remains the property of
# One Convergence, Inc. and its suppliers, if any. The intellectual and
# technical concepts contained herein are proprietary to One Convergence,
# Inc. and its suppliers.
#
# Dissemination of this information or reproduction of this material is
# strictly forbidden unless prior written permission is obtained from
# One Convergence, Inc., USA
#

import datetime
import json
from oslo_config import cfg
from neutron.agent import rpc as agent_rpc
from neutron.common import constants as neutron_constants
from neutron import context
from neutron.common import log
from neutron.common import topics
from neutron.common.exceptions import NeutronException
from neutron.openstack.common import loopingcall
from neutron.openstack.common import periodic_task

from f5.oslbaasv1agent.drivers.bigip import agent_api
from f5.oslbaasv1agent.drivers.bigip import constants
import f5.oslbaasv1agent.drivers.bigip.constants as lbaasv1constants

#from service_manager.vendors.f5 import send_arp
import send_arp

preJuno = False
preKilo = False

DRIVER_NAME='oc_f5_manager'

try:
    from neutron.openstack.common import importutils
    from neutron.openstack.common import log as logging
    preKilo = True
    try:
        from neutron.openstack.common.rpc import dispatcher
        preJuno = True
    except ImportError:
        from neutron.common import rpc
except ImportError:
    from oslo_log import log as logging
    from oslo_utils import importutils
    from f5.oslbaasv1agent.drivers.bigip import rpc

LOG = logging.getLogger(__name__)

__VERSION__ = "0.1.1"

# configuration options useful to all drivers
OPTS = [
    cfg.StrOpt(
        'f5_bigip_lbaas_device_driver',
        default=('f5.oslbaasv1agent.drivers.bigip'
                 '.icontrol_driver.iControlDriver'),
        help=_('The driver used to provision BigIPs'),
    ),
    cfg.BoolOpt(
        'l2_population',
        default=False,
        help=_('Use L2 Populate service for fdb entries on the BIG-IP')
    ),
    cfg.BoolOpt(
        'f5_global_routed_mode',
        default=False,
        help=_('Disable all L2 and L3 integration in favor or global routing')
    ),
    cfg.BoolOpt(
        'use_namespaces',
        default=True,
        help=_('Allow overlapping IP addresses for tenants')
    ),
    cfg.BoolOpt(
        'f5_snat_mode',
        default=True,
        help=_('use SNATs, not direct routed mode')
    ),
    cfg.IntOpt(
        'f5_snat_addresses_per_subnet',
        default='1',
        help=_('Interface and VLAN for the VTEP overlay network')
    ),
    cfg.StrOpt(
        'static_agent_configuration_data',
        default=None,
        help=_(
            'static name:value entries to add to the agent configurations')
    ),
    cfg.IntOpt(
        'service_resync_interval',
        default=300,
        help=_('Number of seconds between service refresh check')
    ),
    cfg.StrOpt(
        'environment_prefix', default='',
        help=_('The object name prefix for this environment'),
    ),
    cfg.BoolOpt(
        'environment_specific_plugin', default=False,
        help=_('Use environment specific plugin topic')
    ),
    cfg.IntOpt(
        'environment_group_number',
        default=1,
        help=_('Agent group number for it environment')
    ),
    cfg.DictOpt(
        'capacity_policy', default={},
        help=_('Metrics to measure capacity and their limits.')
    )
]

cfg.CONF.register_opts(OPTS)

class OcF5Manager(periodic_task.PeriodicTasks):

    def __init__(self, conf, plugin_rpc):
        self.conf = cfg.CONF
        self.conf.set_override('f5_global_routed_mode', True)
        LOG.debug('Setting f5_global_routed_mode to: %s'%self.conf.f5_global_routed_mode)
        self.plugin_rpc = plugin_rpc
        self.lbdriver = {}
        self.do_init(self.conf)

    def do_init(self, conf):
        LOG.info(_('Initializing LbaasAgentManager'))
        self.conf = conf

        # create the cache of provisioned services
        #self.last_resync = datetime.datetime.now()
        #self.needs_resync = False
        #self.plugin_rpc = None

        if conf.service_resync_interval:
            self.service_resync_interval = conf.service_resync_interval
        else:
            self.service_resync_interval = constants.RESYNC_INTERVAL
        LOG.debug(_('setting service resync interval to %d seconds'
                    % self.service_resync_interval))

        try:
            LOG.debug(_('loading LBaaS driver %s'
                        % conf.f5_bigip_lbaas_device_driver))
            #self.lbdriver = importutils.import_object(
            #    conf.f5_bigip_lbaas_device_driver, self.conf)
            #if self.lbdriver.agent_id:
            #    self.agent_host = conf.host + ":" + self.lbdriver.agent_id
            #    LOG.debug('setting agent host to %s' % self.agent_host)
            #else:
            #    self.agent_host = None
            #    LOG.error(_('Driver did not initialize. Fix the driver config '
            #                'and restart the agent.'))
            return
        except ImportError as ie:
            msg = _('Error importing loadbalancer device driver: %s error %s'
                    % (conf.f5_bigip_lbaas_device_driver,  repr(ie)))
            LOG.error(msg)
            raise SystemExit(msg)

        agent_configurations = \
            {'environment_prefix': self.conf.environment_prefix,
             'environment_group_number': self.conf.environment_group_number,
             'global_routed_mode': self.conf.f5_global_routed_mode}

        if self.conf.static_agent_configuration_data:
            entries = \
                str(self.conf.static_agent_configuration_data).split(',')
            for entry in entries:
                nv = entry.strip().split(':')
                if len(nv) > 1:
                    agent_configurations[nv[0]] = nv[1]

        #self.admin_state_up = True

        self.context = context.get_admin_context_without_session()
        # pass context to driver
        #self.lbdriver.set_context(self.context)

        # allow driver to run post init process now that
        # rpc is all setup
        #self.lbdriver.post_init()

        # cause a sync of what Neutron believes
        # needs to be handled by this agent
        #self.needs_resync = True

    @classmethod
    def get_name(self):
        return DRIVER_NAME

    @log.log
    def get_service_by_pool_id(self, pool_id):
        lb_config = self.plugin_rpc.get_logical_device(pool_id)
        return lb_config

    @log.log
    def _get_driver_name(self, tenant_id):
        return '%s_f5' % tenant_id

    @log.log
    def get_f5_driver(self, tenant_id):
        try:
            driver_name = self._get_driver_name(tenant_id)
            return self.lbdriver[driver_name]
        except KeyError:
            LOG.error(_("F5 Driver : %s does'nt exist" % (driver_name)))
            raise Exception('Driver not exists.')

    def _update_service(self, service):
        # Update with global routed mode parameters.
        service['pool']['subnet_id'] = None
        service['pool']['network'] = None
        for member in service['members']:
            member['network'] = None
            member['subnet'] = None
            member['port'] = None
        if 'vip' not in service:
            service['vip'] = {}
            service['vip']['port'] = {}
        service['vip']['network'] = None
        service['vip']['subnet'] = None
        service['vip']['port']['network'] = None
        service['vip']['port']['subnet'] = None
        if 'healthmonitors' in service:
            hm = service.pop('healthmonitors')
        else:
            hm = {}

        service['health_monitors'] = hm

    def _get_service_vm_info(self, vip):
        if vip['description']:
            vip_desc = json.loads(vip['description'])
            fip = vip_desc['floating_ip']
            provider_mac = vip_desc['provider_interface_mac']
            return {"fip": fip, "provider_mac": provider_mac}

    @log.log
    def create_vip(self, vip):
        """Handle RPC cast from plugin to create_vip"""
        try:
            service = self.get_service_by_pool_id(vip['pool_id'])
            self._update_service(service)
            driver = self.get_f5_driver(vip['tenant_id'])
            driver.create_vip(vip, service)
            vm_info = self._get_service_vm_info(vip)
            vip_ip = vip['address']
            fip = vm_info["fip"]
            provider_mac = vm_info["provider_mac"]
            send_arp.send_garp(fip, vip_ip, provider_mac)
        except NeutronException as exc:
            LOG.error("NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("Exception: %s" % exc.message)

    @log.log
    def update_vip(self, old_vip, vip):
        """Handle RPC cast from plugin to update_vip"""
        try:
            service = self.get_service_by_pool_id(vip['pool_id'])
            self._update_service(service)
            driver = self.get_f5_driver(vip['tenant_id'])
            driver.update_vip(old_vip, vip, service)
        except NeutronException as exc:
            LOG.error("NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("Exception: %s" % exc.message)

    @log.log
    def delete_vip(self, vip):
        """Handle RPC cast from plugin to delete_vip"""
        try:
            service = self.get_service_by_pool_id(vip['pool_id'])
            self._update_service(service)
            driver = self.get_f5_driver(vip['tenant_id'])
            driver.delete_vip(vip, service)
        except NeutronException as exc:
            LOG.error("NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("Exception: %s" % exc.message)

    @log.log
    def create_pool(self, pool):
        """Handle RPC cast from plugin to create_pool"""
        try:
            service = self.get_service_by_pool_id(pool['id'])
            self._update_service(service)
            driver = self.get_f5_driver(pool['tenant_id'])
            driver.create_pool(pool, service)
        except NeutronException as exc:
            LOG.error("NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("Exception: %s" % exc.message)

    @log.log
    def update_pool(self, old_pool, pool):
        """Handle RPC cast from plugin to update_pool"""
        try:
            service = self.get_service_by_pool_id(pool['id'])
            self._update_service(service)
            driver = self.get_f5_driver(pool['tenant_id'])
            driver.update_pool(old_pool, pool, service)
        except NeutronException as exc:
            LOG.error("NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("Exception: %s" % exc.message)

    @log.log
    def delete_pool(self, pool):
        """Handle RPC cast from plugin to delete_pool"""
        try:
            service = self.get_service_by_pool_id(pool['id'])
            self._update_service(service)
            driver = self.get_f5_driver(pool['tenant_id'])
            driver.delete_pool(pool, service)
        except NeutronException as exc:
            LOG.error("delete_pool: NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("delete_pool: Exception: %s" % exc.message)

    @log.log
    def create_member(self, member):
        """Handle RPC cast from plugin to create_member"""
        try:
            service = self.get_service_by_pool_id(member['pool_id'])
            self._update_service(service)
            driver = self.get_f5_driver(member['tenant_id'])
            driver.create_member(member, service)
        except NeutronException as exc:
            LOG.error("create_member: NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("create_member: Exception: %s" % exc.message)

    @log.log
    def update_member(self, old_member, member):
        """Handle RPC cast from plugin to update_member"""
        try:
            service = self.get_service_by_pool_id(member['pool_id'])
            self._update_service(service)
            driver = self.get_f5_driver(member['tenant_id'])
            driver.update_member(old_member, member, service)
        except NeutronException as exc:
            LOG.error("update_member: NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("update_member: Exception: %s" % exc.message)

    @log.log
    def delete_member(self, member):
        """Handle RPC cast from plugin to delete_member"""
        try:
            service = self.get_service_by_pool_id(member['pool_id'])
            self._update_service(service)
            driver = self.get_f5_driver(member['tenant_id'])
            driver.delete_member(member, service)
        except NeutronException as exc:
            LOG.error("delete_member: NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("delete_member: Exception: %s" % exc.message)

    @log.log
    def create_pool_health_monitor(self, health_monitor,
                                   pool):
        """Handle RPC cast from plugin to create_pool_health_monitor"""
        try:
            service = self.get_service_by_pool_id(pool)
            self._update_service(service)
            driver = self.get_f5_driver(health_monitor['tenant_id'])
            driver.create_health_monitor(health_monitor, pool, service)
        except NeutronException as exc:
            LOG.error(_("create_pool_health_monitor: NeutronException: %s"
                        % exc.msg))
        except Exception as exc:
            LOG.error(_("create_pool_health_monitor: Exception: %s"
                        % exc.message))

    @log.log
    def update_health_monitor(self, old_health_monitor,
                              health_monitor, pool):
        """Handle RPC cast from plugin to update_health_monitor"""
        try:
            service = self.get_service_by_pool_id(pool)
            self._update_service(service)
            driver = self.get_f5_driver(health_monitor['tenant_id'])
            driver.update_health_monitor(old_health_monitor, health_monitor,
                                         pool, service)
        except NeutronException as exc:
            LOG.error("update_health_monitor: NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("update_health_monitor: Exception: %s" % exc.message)

    @log.log
    def delete_pool_health_monitor(self, health_monitor,
                                   pool):
        """Handle RPC cast from plugin to delete_pool_health_monitor"""
        try:
            service = self.get_service_by_pool_id(pool)
            self._update_service(service)
            driver = self.get_f5_driver(health_monitor['tenant_id'])
            driver.delete_health_monitor(health_monitor, pool, service)
        except NeutronException as exc:
            LOG.error(_("delete_pool_health_monitor: NeutronException: %s"
                        % exc.msg))
        except Exception as exc:
            LOG.error(_("delete_pool_health_monitor: Exception: %s"
                      % exc.message))

    @log.log
    def tunnel_update(self, context, **kwargs):
        """Handle RPC cast from core to update tunnel definitions"""
        try:
            LOG.debug(_('received tunnel_update: %s' % kwargs))
            self.lbdriver.tunnel_update(**kwargs)
        except NeutronException as exc:
            LOG.error("tunnel_update: NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("tunnel_update: Exception: %s" % exc.message)

    @log.log
    def add_fdb_entries(self, context, fdb_entries, host=None):
        """Handle RPC cast from core to update tunnel definitions"""
        try:
            LOG.debug(_('received add_fdb_entries: %s host: %s'
                        % (fdb_entries, host)))
            self.lbdriver.fdb_add(fdb_entries)
        except NeutronException as exc:
            LOG.error("fdb_add: NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("fdb_add: Exception: %s" % exc.message)

    @log.log
    def remove_fdb_entries(self, context, fdb_entries, host=None):
        """Handle RPC cast from core to update tunnel definitions"""
        try:
            LOG.debug(_('received remove_fdb_entries: %s host: %s'
                        % (fdb_entries, host)))
            self.lbdriver.fdb_remove(fdb_entries)
        except NeutronException as exc:
            LOG.error("remove_fdb_entries: NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("remove_fdb_entries: Exception: %s" % exc.message)

    @log.log
    def update_fdb_entries(self, context, fdb_entries, host=None):
        """Handle RPC cast from core to update tunnel definitions"""
        try:
            LOG.debug(_('received update_fdb_entries: %s host: %s'
                        % (fdb_entries, host)))
            self.lbdriver.fdb_update(fdb_entries)
        except NeutronException as exc:
            LOG.error("update_fdb_entrie: NeutronException: %s" % exc.msg)
        except Exception as exc:
            LOG.error("update_fdb_entrie: Exception: %s" % exc.message)

    @log.log
    def get_stats(self, pool_id):
        pass

    @log.log
    def remove_orphans(self):
        pass



