import eventlet
eventlet.monkey_patch()

import sys
from oslo.config import cfg
from neutron.agent.common import config
from neutron.common import config as common_config
from neutron import service as neutron_service
from oslo_service import service
from neutron_fwaas.services.firewall.agents import firewall_agent_api as api
from neutron import manager
import fw_agent_const

Opts = [
    cfg.StrOpt('driver',
               default='neutron_fwass.services.firewall.agents.nfp_fw.drivers.'
                       'noop_driver.NoopFwDriver',
               help=_("Metering driver")),
    cfg.IntOpt('report_interval', default=300,
               help=_("Interval between two firewall heartbeat")),
]


class NFPFirewallAgentService(manager.Manager):

    def __init__(self, host=None):
        self.drivers = dict()
        self.host = host
        super(NFPFirewallAgentService, self).__init__(host=self.host)
        self.fwaas_drivers = cfg.CONF.ocfwaas.driver
        self.oc_fw_plugin_rpc = api.FWaaSPluginApiMixin(
            local_constants.OC_FW_PLUGIN_TOPIC, cfg.CONF.host)
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



def main():
    conf = cfg.CONF
    conf.register_opts(Opts)
    config.register_agent_state_opts_helper(conf)
    common_config.init(sys.argv[1:])
    config.setup_logging()
    server = neutron_service.Service.create(
        binary='nfp-fw-agent',
        topic=fw_agent_const.NFP_FW_AGENT,
        report_interval=cfg.CONF.AGENT.report_interval,
        manager='neutron_fwass.services.firewall.agents.nfp_fw.nfp_fw_agent.'
                'NFPFirewallAgentService')
    service.launch(cfg.CONF, server).wait()
