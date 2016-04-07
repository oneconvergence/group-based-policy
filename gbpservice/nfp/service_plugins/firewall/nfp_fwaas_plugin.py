from oslo_config import cfg

from gbpservice.nfp.config_orchestrator.agent import topics
import neutron_fwaas.extensions
from neutron_fwaas.services.firewall import fwaas_plugin as ref_fw_plugin


class NFPFirewallPlugin(ref_fw_plugin.FirewallPlugin):
    def __init__(self):
        # Monkey patch L3 agent topic
        # L3 agent was where reference firewall agent runs
        # patch that topic to the NFP firewall agent's topic name
        ref_fw_plugin.f_const.L3_AGENT = topics.FW_NFP_CONFIGAGENT_TOPIC

        # Ensure neutron fwaas extensions are loaded
        ext_path = neutron_fwaas.extensions.__path__[0]
        if ext_path not in cfg.CONF.api_extensions_path.split(':'):
            cfg.CONF.set_override(
                'api_extensions_path',
                cfg.CONF.api_extensions_path + ':' + ext_path)

        super(NFPFirewallPlugin, self).__init__()
