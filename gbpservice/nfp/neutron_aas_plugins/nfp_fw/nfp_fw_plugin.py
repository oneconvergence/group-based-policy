from copy import deepcopy

from gbpservice.nfp.config_orchestrator.agent.topics import \
    FW_NFP_CONFIGAGENT_TOPIC
from neutron_fwaas.services.firewall.fwaas_plugin import (FirewallAgentApi,
                                                          FirewallCallbacks,
                                                          FirewallPlugin)
from neutron_fwaas.common.fwaas_constants import FIREWALL_PLUGIN
from neutron.common import rpc as n_rpc
from oslo_config import cfg
from neutron_fwaas.db.firewall import firewall_db
from neutron.plugins.common import constants as plugin_const
from neutron import context as plugin_context
from neutron import manager


class NFPFirewallCallbacks(FirewallCallbacks):
    def __init__(self, plugin):
        super(NFPFirewallCallbacks, self).__init__(plugin)

    @property
    def _core_plugin(self):
        return manager.NeutronManager.get_plugin()

    @property
    def _l3_plugin(self):
        return manager.NeutronManager.get_service_plugins().get(
            plugin_const.L3_ROUTER_NAT)

    def get_router_interfaces_details(self, context, **kwargs):
        if not kwargs['router_ids']:
            return []
        # routers = self._l3_plugin.get_routers(context, kwargs['router_ids'])
        ports = self._core_plugin.get_ports(
            context, filters={'device_id': kwargs['router_ids'],
                              'device_owner': ['network:router_interface']})
        filter_ports = list()

        for port in ports:
            subnet_id = port['fixed_ips'][0]['subnet_id']
            subnet_name = self._core_plugin.get_subnet(context, subnet_id)[
                'name']
            if subnet_name.startswith("stitching"):
                continue
            else:
                _id = port['id']
                self._l3_plugin.remove_router_interface(
                        context, port['device_id'], {'port_id': _id})
                self._core_plugin.delete_port(context, _id)
                new_port = deepcopy(port)
                del new_port['id']
                del new_port['status']
                del new_port['tenant_id']
                new_port.update(name="oc_owned_prov_%s" % _id.split('-')[
                    0], admin_state_up=True, device_id='', device_owner='',
                            description=new_port['device_id'],
                            tenant_id='ef89412b8e1840a293899476112f9298')
                _context = plugin_context.get_admin_context()
                _context.tenant_id = port['tenant_id']
                _port = self._core_plugin.create_port(
                        _context, {'port': new_port})
                filter_ports.append(_port)
        return filter_ports

    def delete_router_port(self, context, **kwargs):
        port_id = kwargs['port']['id']
        # port = kwargs.get('port')
        self._core_plugin.delete_port(context, port_id)
        return


class NFPFirewallPlugin(FirewallPlugin):
    """
    For mitaka.
    """
    def __init__(self):
        self.start_rpc_listeners()
        self.agent_rpc = FirewallAgentApi(
                    FW_NFP_CONFIGAGENT_TOPIC,
                    cfg.CONF.host)
        firewall_db.subscribe()

    def start_rpc_listeners(self):
        self.endpoints = [NFPFirewallCallbacks(self)]
        self.conn = n_rpc.create_connection()
        self.conn.create_consumer(
            FIREWALL_PLUGIN, self.endpoints, fanout=False)
        return self.conn.consume_in_threads()


