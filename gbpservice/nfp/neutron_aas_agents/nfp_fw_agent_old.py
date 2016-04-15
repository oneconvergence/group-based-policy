import ast

import eventlet

eventlet.monkey_patch()

import sys
from oslo_config import cfg
from neutron.agent.common import config
from neutron.common import config as common_config
from neutron import service as neutron_service
from oslo_service import service
from neutron_fwaas.services.firewall.agents import firewall_agent_api as api
from neutron import manager, context
from neutron.agent import rpc as agent_rpc
from oslo_log import log as logging
import fw_agent_const

LOG = logging.getLogger(__name__)

OPTS = [
    cfg.StrOpt('driver',
               default='neutron_fwass.services.firewall.agents.nfp_fw.drivers.'
                       'noop_driver.NoopFwDriver',
               help=_("Firewall driver")),
    cfg.IntOpt('report_interval', default=300,
               help=_("Interval between two firewall heartbeat")),
]

GROUP_OPTS = cfg.OptGroup(name='ocfwaas', title='OC FW OPTIONS')


class OCNFPFirewallAgentApi(api.FWaaSPluginApiMixin):
    def __init__(self, topic, host):
        super(OCNFPFirewallAgentApi, self).__init__(topic, host)

    def get_router_details(self, context, router_ids):
        kwargs = {'router_ids': router_ids}
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_router_interfaces_details',
                          host=self.host, **kwargs)


class NFPFirewallAgentService(manager.Manager):
    RPC_API_VERSION = '1.2'

    def __init__(self, host=None):
        self.drivers = dict()
        self.host = host
        super(NFPFirewallAgentService, self).__init__(host=self.host)
        self.fwaas_drivers = cfg.CONF.ocfwaas.driver
        # self.oc_fw_plugin_rpc = api.FWaaSPluginApiMixin(
        #     fw_agent_const.OC_FW_PLUGIN_TOPIC, cfg.CONF.host)
        self.oc_fw_plugin_rpc = OCNFPFirewallAgentApi(
            fw_agent_const.OC_FW_PLUGIN_TOPIC, cfg.CONF.host)
        self.context = context.get_admin_context_without_session()
        self.oc_fwaas_enabled = cfg.CONF.ocfwaas.enabled
        self.agent_state = None
        self.use_call = True
        self.state_rpc = agent_rpc.PluginReportStateAPI(
            fw_agent_const.OC_FW_PLUGIN_TOPIC)
        self.report_interval = cfg.CONF.ocfwaas.oc_report_interval

        if not self.oc_fwaas_enabled:
            msg = "FWaaS not enabled in configuration file"
            LOG.error(_(msg))
            raise SystemExit(1)
        else:
            # self.driver = importutils.import_object(fwaas_driver_class_path)
            self.load_driver()

            # first handle all firewalls in PEDNING_DELETE state to avoid
            # race with
            # new firewall create requests which consumers will receive
            # self.sync_firewalls()
            # self.endpoints = [FwAgent_SM_Callbacks(self)]
            # self.conn = n_rpc.create_connection(new=True)
            # self.conn.create_consumer(
            #     local_constants.SM_RPC_TOPIC, self.endpoints, fanout=False)
            # self.conn.consume_in_threads()

    def init_host(self):
        pass

    def load_driver(self):
        pass
        # for fw_driver in self.fwaas_drivers.split(","):
        #     driver, vendor = fw_driver.split(":")
        #     self.drivers[vendor] = importutils.import_object(driver)

    def after_start(self):
        LOG.debug(_(" OC FW agent started "))

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
            # Added to handle in service vm agents. VM agent will add
            # default DROP rule.
            # if not self._is_firewall_rule_exists(fw):
            #     self.oc_fw_plugin_rpc.set_firewall_status(
            #         context, fw['id'], constants.STATUS_ACTIVE)
            try:
                floating_ip, vendor = self.get_firewall_attributes(fw)
                status = self.drivers[vendor].configure_firewall(
                    floating_ip, fw)
            except Exception:
                self.oc_fw_plugin_rpc.set_firewall_status(
                    context, fw['id'], constants.STATUS_ERROR)
            else:
                self.oc_fw_plugin_rpc.set_firewall_status(
                    context, fw['id'], status)

        elif func_name.lower() == 'delete_firewall':
            if not self._is_firewall_rule_exists(fw):
                return self.oc_fw_plugin_rpc.firewall_deleted(context,
                                                              fw['id'])
            try:
                floating_ip, vendor = self.get_firewall_attributes(fw)
                status = self.drivers[vendor].delete_firewall(
                    floating_ip, fw)
            except ConnectionError:
                # FIXME(Vikash) It can't be correct everytime
                LOG.warn("There is a connection error for firewall %r of "
                         "tenant %r. Assuming either there is serious issue "
                         "with VM or data path is completely broken. For now "
                         "marking that as delete." % (fw['id'],
                                                      fw['tenant_id']))
                self.oc_fw_plugin_rpc.firewall_deleted(context, fw['id'])

            except Exception as e:
                # TODO(Vikash) Is it correct to raise ? As the subsequent
                # attempt to clean will only re-raise the last one.And it
                # can go on and on and may not be ever recovered.
                self.oc_fw_plugin_rpc.set_firewall_status(
                    context, fw['id'], constants.STATUS_ERROR)
                # raise(e)
            else:
                if status == constants.STATUS_ERROR:
                    self.oc_fw_plugin_rpc.set_firewall_status(
                        context, fw['id'], status)
                else:
                    LOG.info("Firewall %r deleted of tenant: %r" % (
                        fw['id'], fw['tenant_id']))
                    self.oc_fw_plugin_rpc.firewall_deleted(context, fw['id'])

        elif func_name.lower() == 'update_firewall':
            if not self._is_firewall_rule_exists(fw):
                return self.oc_fw_plugin_rpc.set_firewall_status(
                    context, fw['id'], constants.STATUS_ACTIVE)
            try:
                floating_ip, vendor = self.get_firewall_attributes(fw)
                status = self.drivers[vendor].update_firewall(
                    floating_ip, fw)
            except:

                self.oc_fw_plugin_rpc.set_firewall_status(context, fw['id'],
                                                          'ERROR')
            else:
                self.oc_fw_plugin_rpc.set_firewall_status(context, fw['id'],
                                                          status)
        else:
            raise Exception("Wrong call")

    def get_firewall_attributes(self, firewall):
        description = ast.literal_eval(firewall["description"])
        if not description.get('vm_management_ip'):
            raise

        if not description.get('service_vendor'):
            raise

        return description['vm_management_ip'], description[
            'service_vendor'].upper()

    def _is_firewall_rule_exists(self, fw):
        if not fw['firewall_rule_list']:
            return False
        else:
            return True

    def get_routers_details(self, router_ids):
        interfaces = self.oc_fw_plugin_rpc.get_router_interfaces_details(
            router_ids)

    def agent_updated(self, context, admin_state_up, host):
        pass

    def router_deleted(self, context, router_id):
        pass

    def routers_updated(self, context, routers):
        pass

    def add_arp_entry(self, context, payload):
        pass

    def del_arp_entry(self, context, payload):
        pass

    def router_removed_from_agent(self, context, payload):
        pass

    def router_added_to_agent(self, context, payload):
        pass

    def get_router(self, context, router_id, host):
        pass


def main():
    conf = cfg.CONF
    cfg.CONF.register_group(GROUP_OPTS)
    cfg.CONF.register_opts(OPTS, group=GROUP_OPTS)
    config.register_agent_state_opts_helper(conf)
    common_config.init(sys.argv[1:])
    config.setup_logging()
    server = neutron_service.Service.create(
        binary='nfp-fw-agent',
        topic=fw_agent_const.NFP_FW_AGENT,
        report_interval=cfg.CONF.AGENT.report_interval,
        manager='neutron_fwaas.services.firewall.agents.nfp_fw.nfp_fw_agent.'
                'NFPFirewallAgentService')
    service.launch(cfg.CONF, server).wait()
