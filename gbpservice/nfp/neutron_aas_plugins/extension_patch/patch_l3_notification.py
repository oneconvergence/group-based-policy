from copy import deepcopy

import neutron.api.rpc.agentnotifiers.l3_rpc_agent_api
from neutron.db.l3_db import L3RpcNotifierMixin
from neutron.common import rpc as n_rpc
import random
from neutron import manager
from neutron_lib import constants
from neutron.plugins.common import constants as service_constants
from neutron.common import topics, utils
from neutron import context as plugin_context
from neutron._i18n import _LE, _LI
from oslo_log import log

LOG = log.getLogger(__name__)

NFP_L3_AGENT = "nfp-l3-agent"
REMOVE_ROUTER_INTERFACE = 'remove_router_interface'
ADD_ROUTER_INTERFACE = 'add_router_interface'


def _agent_notification(self, context, method, router_ids, operation,
                        shuffle_agents, data=None):
    """Notify changed routers to hosting l3 agents."""
    adminContext = context if context.is_admin else context.elevated()
    plugins = manager.NeutronManager.get_service_plugins()
    _l3_plugin = plugins.get(service_constants.L3_ROUTER_NAT)
    fw_plugin = plugins.get(service_constants.FIREWALL)
    core_plugin = manager.NeutronManager.get_plugin()
    send_rpc_to_nfp = True
    if not (_l3_plugin or fw_plugin):
        LOG.error(_LE("One of the l3 plugin or fw plugin is not currently "
                      "initialized."))
        send_rpc_to_nfp = False
    for router_id in router_ids:
        hosts = _l3_plugin.get_hosts_to_notify(adminContext, router_id)
        if shuffle_agents:
            random.shuffle(hosts)
        for host in hosts:
            LOG.debug('Notify agent at %(topic)s.%(host)s the message '
                      '%(method)s',
                      {'topic': topics.L3_AGENT,
                       'host': host,
                       'method': method})
            cctxt = self.client.prepare(topic=topics.L3_AGENT,
                                        server=host,
                                        version='1.1')
            cctxt.cast(context, method, routers=[router_id])

    if not send_rpc_to_nfp or not operation or operation.lower() == REMOVE_ROUTER_INTERFACE:
        return
    subnet_id = data.get('subnet_id')
    if subnet_id:
        subnet_name = core_plugin.get_subnet(context, subnet_id)[
            'name']
        if subnet_name.startswith("stitching"):
            return
    firewalls_list = fw_plugin.get_firewalls(context)
    fw_routers, fws = list(), list()
    for fw in firewalls_list:
        if not fw['status'] == "ACTIVE":
            continue
        routers = set(router_ids) & set(fw['router_ids'])
        if not routers:
            continue
        fw_routers.extend(routers)
        fws.append(fw)
    # REVISIT(VK):  Wacky Wacky !!!
    firewalls = [fw_plugin._make_firewall_dict_with_rules(context, fw['id'])
                 for fw in fws]
    if fw_routers:
        (active_routers, interfaces, floating_ips) = \
            _l3_plugin._get_router_info_list(
            context, router_ids=list(set(fw_routers)), active=True)
        if data:
            interfaces = [_int for _int in interfaces if data.get('port_id')
                          == _int['id']]
            if interfaces:
                port_list = list()
                for interface in interfaces:
                    _l3_plugin.remove_router_interface(
                        context, interface['device_id'], {'port_id':
                                                          interface['id']})
                    core_plugin.delete_port(context, interface['id'])
                    new_interface = deepcopy(interface)
                    name = "oc_owned_prov_%s" % new_interface['id'].split(
                            '-')[0]
                    del new_interface['id']
                    del new_interface['status']
                    del new_interface['tenant_id']
                    new_interface.update(
                            name=name, admin_state_up=True,
                            device_id='', device_owner='',
                            description=new_interface['device_id'],
                            tenant_id='ef89412b8e1840a293899476112f9298')
                    _context = plugin_context.get_admin_context()
                    _context.tenant_id = new_interface['tenant_id']
                    port_list.append(core_plugin.create_port(
                            _context, {'port': new_interface}))
            # Can't react to delete.
            # if operation == 'remove_router_interface':
            #     _interfaces = [{'port_id': data['port_id']}]
        routers_info = {'routers': active_routers, 'interfaces': port_list,
                        'floating_ips': floating_ips, 'operation': operation,
                        'firewalls': firewalls}
        cctxt = self.client.prepare(topic=NFP_L3_AGENT)
        cctxt.cast(context, 'routers_updated',
                   routers_info=routers_info)


neutron.api.rpc.agentnotifiers.l3_rpc_agent_api.L3AgentNotifyAPI\
    ._agent_notification = _agent_notification


def routers_updated(self, context, router_ids, operation=None, data=None,
                    shuffle_agents=False, schedule_routers=True):
    if router_ids:
        self._notification(context, 'routers_updated', router_ids,
                           operation, shuffle_agents, schedule_routers,
                           data=data)

neutron.api.rpc.agentnotifiers.l3_rpc_agent_api.L3AgentNotifyAPI\
    .routers_updated = routers_updated


def _notification(self, context, method, router_ids, operation, shuffle_agents,
                  schedule_routers=True, data=None):
    """Notify all the agents that are hosting the routers."""
    plugin = manager.NeutronManager.get_service_plugins().get(
            service_constants.L3_ROUTER_NAT)
    if not plugin:
        LOG.error(_LE('No plugin for L3 routing registered. Cannot notify '
                      'agents with the message %s'), method)
        return
    if utils.is_extension_supported(
            plugin, constants.L3_AGENT_SCHEDULER_EXT_ALIAS):
        adminContext = (context.is_admin and
                        context or context.elevated())
        if schedule_routers:
            plugin.schedule_routers(adminContext, router_ids)
        self._agent_notification(
                context, method, router_ids, operation, shuffle_agents,
                data=data)
    else:
        cctxt = self.client.prepare(fanout=True)
        cctxt.cast(context, method, routers=router_ids)

neutron.api.rpc.agentnotifiers.l3_rpc_agent_api.L3AgentNotifyAPI\
    ._notification = _notification


def notify_router_interface_action(
        self, context, router_interface_info, action):
    l3_method = '%s_router_interface' % action
    L3RpcNotifierMixin().notify_routers_updated(
            context, [router_interface_info['id']], l3_method,
            {'subnet_id': router_interface_info['subnet_id'],
             'port_id': router_interface_info['port_id']})

    mapping = {'add': 'create', 'remove': 'delete'}
    notifier = n_rpc.get_notifier('network')
    router_event = 'router.interface.%s' % mapping[action]
    notifier.info(context, router_event,
                  {'router_interface': router_interface_info})

neutron.db.l3_db.L3_NAT_db_mixin.notify_router_interface_action = \
    notify_router_interface_action

