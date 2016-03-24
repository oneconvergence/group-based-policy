from neutron_fwaas.services.firewall.fwaas_plugin import (FirewallAgentApi,
                                                          FirewallCallbacks,
                                                          FirewallPlugin)
from oslo_config import cfg
import fw_constants


class NFPFirewallCallbacks(FirewallCallbacks):
    def get_router_interfaces_details(self, context, **kwargs):
        return []


class NFPFirewallPlugin(FirewallPlugin):

    def __init__(self):
        self.agent_rpc = FirewallAgentApi(
            fw_constants.NFP_FW_AGENT,
            cfg.CONF.host
        )
