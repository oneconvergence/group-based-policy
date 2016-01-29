import eventlet
eventlet.monkey_patch()

import sys
import ast
from oslo.config import cfg

from requests import ConnectionError
from sc.services.fw.agent import constants as local_constants
from sc.services.fw.lib import constants
from sc.services.fw.agent.fw_agent_sm_rpc import FwAgent_SM_Callbacks

from neutron import manager
from neutron.agent.common import config
from neutron.services.firewall.agents import firewall_agent_api as api
from neutron.openstack.common import importutils
from neutron.openstack.common import log as logging
from neutron.common import config as common_config
from neutron import service
from neutron import context
from neutron.agent import rpc as agent_rpc
from neutron.common import rpc as n_rpc
from neutron.openstack.common import loopingcall
from neutron.openstack.common import service as svc
from neutron.common.rpc import MessagingTimeout
from neutron.db.firewall import firewall_db
from neutron_fwaas.db.firewall import firewall_router_insertion_db
from neutron.services.firewall import RestClientOverUnix as rest_client

LOG = logging.getLogger(__name__)

rest_timeout = [
    cfg.IntOpt(
        'rest_timeout',
        default=30,
        help=_("rest api timeout"))]
cfg.CONF.register_opts(rest_timeout)

OPTS = [
    cfg.IntOpt('oc_periodic_interval', default=10, help='Define periodic '
                                                        'interval for tasks'),
    cfg.IntOpt('oc_report_interval', default=10,
               help='Reporting interval from agent to firewall plugin'),
    cfg.StrOpt('driver', required=True,
               help='driver to be used for firewall configuration'),
    cfg.StrOpt('enabled', required=True,
               help='flag to indicate firewall enabled or disabled')
]

GROUP_OPTS = cfg.OptGroup(name='ocfwaas', title='OC FW OPTIONS')
rest_timeout = [
    cfg.IntOpt(
        'rest_timeout',
        default=30,
        help=_("rest api timeout"))]
cfg.CONF.register_opts(rest_timeout)

class OCFWAgent(manager.Manager, firewall_db.Firewall_db_mixin,
                firewall_router_insertion_db.FirewallRouterInsertionDbMixin):

    RPC_API_VERSION = '1.2'

    def __init__(self, host=None):
        self.drivers = dict()
        self.host = cfg.CONF.host
        super(OCFWAgent, self).__init__(host=self.host)
        self.fwaas_drivers = cfg.CONF.ocfwaas.driver
        self.context = context.get_admin_context_without_session()
        self.oc_fwaas_enabled = cfg.CONF.ocfwaas.enabled
        self.agent_state = None
        self.use_call = True
        self.state_rpc = agent_rpc.PluginReportStateAPI(
            local_constants.OC_FW_PLUGIN_TOPIC)
        self.report_interval = cfg.CONF.ocfwaas.oc_report_interval

        if not self.oc_fwaas_enabled:
            msg = "FWaaS not enabled in configuration file"
            LOG.error(_(msg))
            raise SystemExit(1)
        else:
            # self.driver = importutils.import_object(fwaas_driver_class_path)
            self.load_driver()

        # first handle all firewalls in PEDNING_DELETE state to avoid race with
        # new firewall create requests which consumers will receive
        self.sync_firewalls()
        self.endpoints = [FwAgent_SM_Callbacks(self)]
        self.conn = n_rpc.create_connection(new=True)
        self.conn.create_consumer(
            local_constants.SM_RPC_TOPIC, self.endpoints, fanout=False)
        self.conn.consume_in_threads()

    def init_host(self):
        LOG.debug(_("OC FW agent starting on host - %s " % cfg.CONF.host))
        self.agent_state = {
            'start_flag': True,
            'binary': local_constants.OC_FW_AGENT_BINARY,
            'host': cfg.CONF.host,
            'topic': local_constants.OC_FW_AGENT_TOPIC,
            'agent_type': local_constants.OC_AGENT_TYPE,
            'configurations': {
                'driver': local_constants.OC_FIREWALL_DRIVER
            },
            'report_interval': self.report_interval,
            'description': 'oc firewall agent '

        }

        if self.report_interval:
            self.heartbeat = loopingcall.FixedIntervalLoopingCall(
                self._report_state)
            self.heartbeat.start(interval=self.report_interval)

    def load_driver(self):
        for fw_driver in self.fwaas_drivers.split(","):
            driver, vendor = fw_driver.split(":")
            self.drivers[vendor] = importutils.import_object(driver)

    def after_start(self):
        LOG.debug(_(" OC FW agent started "))


    def _report_state(self):
        try:
            self.state_rpc.report_state(self.context, self.agent_state,
                                        self.use_call)
            self.agent_state.pop('start_flag', None)
            self.use_call = False
        except AttributeError:
            # This means the server does not support report_state
            LOG.warn(_("Neutron server does not support state report."
                       " State report for OC FIREWALL AGENT will be "
                       "disabled."))
            self.heartbeat.stop()
            return
        except Exception:
            LOG.exception(_("OC Firewall agent failed reporting state!"))

    def get_firewalls_for_tenant(self, context):
        """Agent uses this to get all firewalls and rules for a tenant."""
        LOG.debug("get_firewalls_for_tenant() called")
        fw_list = []
        tmp_fw_list = super(OCFWAgent, self).\
            get_firewalls(context)
        for fw in tmp_fw_list:
            fw_with_rules = super(OCFWAgent, self).\
                _make_firewall_dict_with_rules(context, fw['id'])
            if fw['status'] == n_const.PENDING_DELETE:
                fw_with_rules['add-router-ids'] = []
                fw_with_rules['del-router-ids'] = (
                    super(OCFWAgent, self).get_firewall_routers(context, fw['id']))
            else:
                fw_with_rules['add-router-ids'] = (
                    super(OCFWAgent, self)..get_firewall_routers(context, fw['id']))
                fw_with_rules['del-router-ids'] = []
            fw_list.append(fw_with_rules)
        return fw_list

    def sync_firewalls(self):
        fw_list = []
        try:
            fw_list = self.get_firewalls_for_tenant(self.context)
        except MessagingTimeout as e:
            LOG.error(" Connection to firewall plugin failed with "
                      " MessagingTimeout exception.Some stale fw service "
                      " resources will not be cleaned." )
            #raise SystemExit

        for fw in fw_list:
            if fw['status'] == 'PENDING_DELETE':
                self.invoke_driver_for_plugin_api(self.context, fw,
                                                  'delete_firewall')

    def create_firewall(self, context, firewall, host):
        LOG.debug(_("create firewall called"))
        LOG.debug(_("Firewall - %r" % firewall))
        return self.invoke_driver_for_plugin_api(context, firewall,
                                                 'create_firewall')

    def update_firewall(self, context, firewall, host):
        LOG.debug(_("update firewall called"))
        LOG.debug(_("Firewall - %r" % firewall))
        return self.invoke_driver_for_plugin_api(context, firewall,
                                                 'update_firewall')

    def delete_firewall(self, context, firewall, host):
        LOG.debug(_("delete firewall called"))
        LOG.debug(_("Firewall - %r" % firewall))
        return self.invoke_driver_for_plugin_api(context, firewall,
                                                 'delete_firewall')

    def invoke_driver_for_plugin_api(self, context, fw, func_name):
        """
        :param context:
        :param fw:
        :param func_name:
        :return:
        """
        if func_name.lower() == 'create_firewall':
            data_context = self._get_all_context_for_given_tenant(context)
            body = {'resource_data': fw,
                    'tenant_data': data_context}
            rest_client.send_request(REQUEST_METHOD,
                                     SERVER_IP_ADDR,
                                     'fw/create_firewall',
                                     'POST',
                                     headers = 'application/json',
                                     body = body)

        elif func_name.lower() == 'delete_firewall':
            data_context = self._get_all_context_for_given_tenant(context)
            body = {'resource_data': fw,
                    'tenant_data': data_context}
            rest_client.send_request(REQUEST_METHOD,
                                     SERVER_IP_ADDR,
                                     'fw/delete_firewall',
                                     'DELETE',
                                     headers = 'application/json',
                                     body = body)

        elif func_name.lower() == 'update_firewall':
            data_context = self._get_all_context_for_given_tenant(context)
            body = {'resource_data': fw,
                    'tenant_data': data_context}
            rest_client.send_request(REQUEST_METHOD,
                                     SERVER_IP_ADDR,
                                     'fw/update_firewall',
                                     'PUT',
                                     headers = 'application/json',
                                     body = body)


    def _get_firewall_context(self, context, filters):

        firewalls = super(OCFWAgent, self).\
            get_firewalls(context, filters)

        firewall_policies = super(OCFWAgent, self).\
            get_firewall_policies(context, filters)

        firewall_rules = super(OCFWAgent, self).\
            get_firewall_rules(context, filters)

        return {'firewalls': firewalls,
                'firewall_policies': firewall_policies,
                'firewall_rules': firewall_rules}

    def _get_core_context(self, context, filters):
        core_plugin = self.core_plugin
        subnets = core_plugin.get_subnets(
                      context,
                      filters)

        routers = core_plugin.get_routers(
                      context,
                      filters)

        ports = core_plugin.get_ports(
                    context,
                    filters)

        return {'subnets':subnets,
                'routers':routers,
                'ports':ports}

    def _get_all_context_for_given_tenant(self, context, tenant_id=None):
        if tenant_id == None and context.is_admin :
            tenant_id = context.tenant_id
        if tenant_id == None :
            raise TenantNotFound()
        filters = {'tenant_id':tenant_id}
        data_context = self._get_firewall_context(context, filters)
        data_context.update(self._get_core_context(context, filters))
        return data_context

def launch(binary, svcmanager, topic=None):
    cfg.CONF.register_group(GROUP_OPTS)
    cfg.CONF.register_opts(OPTS, group=GROUP_OPTS)

    common_config.init(sys.argv[1:])
    config.setup_logging()
    # poll_period = cfg.CONF.ocfwaas.oc_periodic_interval
    report_interval = cfg.CONF.ocfwaas.oc_report_interval
    server = service.Service.create(
        binary=binary, manager=svcmanager, topic=topic,
        report_interval=report_interval)
    svc.launch(server).wait()


def launch_agent():
    launch('oc-fw-agent',
           'sc.services.fw.agent.oc_fw_agent_service'
           '.OCFWAgent', topic=(local_constants.OC_FW_AGENT_TOPIC))

