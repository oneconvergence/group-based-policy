
from neutron.api.v2 import attributes as attr

from neutron import context as neutron_context
from neutron import manager
from neutron.plugins.common import constants as n_const
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

    def _get_routers_for_create_firewall(self, tenant_id, context, firewall):

        # pop router_id as this goes in the router association db
        # and not firewall db
        router_ids = firewall['firewall'].pop('router_ids', None)
        if router_ids == attr.ATTR_NOT_SPECIFIED:
            # old semantics router-ids keyword not specified pick up
            # all routers on tenant.
            l3_plugin = manager.NeutronManager.get_service_plugins().get(
                n_const.L3_ROUTER_NAT)
            ctx = neutron_context.get_admin_context()
            routers = l3_plugin.get_routers(ctx)
            router_ids = [
                router['id']
                for router in routers
                if router['tenant_id'] == tenant_id]
            # validation can still fail this if there is another fw
            # which is associated with one of these routers.
            return router_ids
        else:
            if not router_ids:
                # This indicates that user specifies no routers.
                return []
            else:
                # some router(s) provided.
                return router_ids


