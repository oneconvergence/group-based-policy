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

import copy
import yaml

from keystoneclient.v2_0 import client as keyclient
from keystoneclient.v3 import client as keyclientv3
from neutron.api.rpc.agentnotifiers import dhcp_rpc_agent_api
from neutron.api.v2 import attributes
from neutron.common import constants as const
from neutron.common import exceptions as n_exc
from neutron.common import log
from neutron import context as n_context
from neutron.openstack.common import jsonutils
from neutron.openstack.common import log as logging
from neutron.plugins.common import constants as pconst
from neutron.services.oc_service_manager.oc_service_manager_client import (
                                                        SvcManagerClientApi)
from oslo.config import cfg

from gbpservice.neutron.services.grouppolicy.common import constants
from gbpservice.neutron.services.servicechain.plugins.ncp import (
                                                    exceptions as exc)
from gbpservice.neutron.services.servicechain.plugins.ncp import model
from gbpservice.neutron.services.servicechain.plugins.ncp.node_drivers import (
                                heat_node_driver as heat_node_driver)
from gbpservice.neutron.services.servicechain.plugins.ncp.node_drivers import (
                                openstack_heat_api_client as heat_api_client)


oneconvergence_driver_opts = [
    cfg.StrOpt('svc_management_ptg_name',
               default='svc_management_ptg',
               help=_("Name of the PTG that is associated with the "
                      "service management network")),
    cfg.StrOpt('remote_vpn_client_pool_cidr',
               default='192.168.254.0/24',
               help=_("CIDR pool for remote vpn clients")),
    cfg.StrOpt('heat_uri',
               default='http://localhost:8004/v1',
               help=_("Heat API server address to instantiate services "
                      "specified in the service chain.")),
]

cfg.CONF.register_opts(oneconvergence_driver_opts, "oneconvergence_node_driver")

SC_METADATA = '{"sc_instance":"%s", "insert_type":"%s", "floating_ip": "%s", "provider_interface_mac": "%s"}'
SVC_MGMT_PTG_NAME = cfg.CONF.oneconvergence_node_driver.svc_management_ptg_name
STITCHING_PTG_NAME = "traffic-stitching-gbp-internal"

POOL_MEMBER_PARAMETER_AWS = {"Description": "Pool Member IP Address",
                             "Type": "String"}
POOL_MEMBER_PARAMETER = {"description": "Pool Member IP Address",
                         "type": "string"}

LOG = logging.getLogger(__name__)


class InvalidServiceType(exc.NodeCompositionPluginBadRequest):
    message = _("The OneConvergence Node driver only supports the services "
                "VPN, Firewall and LB in a Service Chain")

class ServiceInfoNotAvailableOnUpdate(n_exc.NeutronException):
    message = _("Service information is not available with Service Manager "
                "on node update")

# REVISIT(Magesh): The Port and PT names have to be changed
class TrafficStitchingDriver(object):

    def __init__(self):
        self._cached_agent_notifier = None

    def reclaim_gw_port_for_servicevm(self, context, subnet_id,
                                      admin_context=None):
        """
        First remove the router interface.
        Then create a new port with the same ip address
        """
        subnet = context.core_plugin.get_subnet(context._plugin_context,
                                                subnet_id)
        network_id = subnet['network_id']
        # REVISIT(Magesh): The next for loop can be avoided if we can
        # pass subnetid also as filter in fixed_ips
        ports = context.core_plugin.get_ports(
            context._plugin_context,
            filters={'device_owner': ['network:router_interface'],
                     'fixed_ips':  {'subnet_id': [subnet_id]}})
        router_port = ports and ports[0] or {}
        router_id = router_port.get('device_id')

        if router_id:
            context.l3_plugin.remove_router_interface(
                context._plugin_context,
                router_id,
                {"subnet_id": subnet_id})
            context._plugin_context.session.expunge_all()
            self._notify_port_action(context, router_port, 'delete')

        ip_address = subnet['gateway_ip']
        port_name = "hotplug-" + ip_address
        if admin_context:
            tenant_id = admin_context.tenant_id
        else:
            tenant_id = context._plugin_context.tenant_id

        hotplug_port = self._create_port(
                context, admin_context, tenant_id,
                port_name, network_id, ip_address=ip_address)

        if hotplug_port:
            return hotplug_port['id'], hotplug_port['mac_address']
        else:
            LOG.error(_("Unable to create hotplug port"))
        # FIXME(Magesh): Temporary Workaround for FW-VPN sharing
        filters={'fixed_ips': {'subnet_id': [subnet_id],
                               'ip_address': [ip_address]}}
        ports = context.core_plugin.get_ports(admin_context, filters=filters)
        if not ports:
            raise
        port = ports and ports[0]
        return port['id'], port['mac_address']

    def setup_stitching(self, context, admin_context, service_type,
                        provider=None, stitching_port_id=None):
        stitching_subnet_id = self._get_stitching_subnet_id(
                                context, create_if_not_present=True)
        if not stitching_port_id:
            stitching_port_id, stitching_port_ip = (
                self._create_stitching_port(
                                context, admin_context,
                                service_type, stitching_subnet_id))
        else:
            stitching_port_ip = context.core_plugin.get_port(
                    admin_context,
                    stitching_port_id)['fixed_ips'][0]['ip_address']
        if context.is_consumer_external:
            self._add_extra_route(
                context, stitching_port_ip, stitching_subnet_id,
                provider['subnets'][0])
        return stitching_port_id, stitching_subnet_id

    def create_lb_port(self, admin_context, network_id,
                       provider_ptg_subnet_id, context):
        port = self._create_port(
            context, admin_context, admin_context.tenant_id,
            'LB_provider_port', network_id, subnet_id=provider_ptg_subnet_id)
        return port

    def create_service_management_port(self, context, admin_context):
        # REVISIT(Magesh): Retrieving management PTG by name will not be
        # required when the service_ptg patch is merged
        filters = {'name': [SVC_MGMT_PTG_NAME]}
        svc_mgmt_ptgs = context.gbp_plugin.get_policy_target_groups(
                                                admin_context, filters)
        if not svc_mgmt_ptgs:
            LOG.error(_("Service Management Group is not created by "
                        "Admin"))
            raise
        svc_mgmt_pt = self._create_pt(
                context, svc_mgmt_ptgs[0]['id'], "mgmt-pt",
                admin_context=admin_context)
        svc_mgmt_port = svc_mgmt_pt['port_id']
        filters = {'port_id': [svc_mgmt_pt['port_id']]}
        floatingips = context.l3_plugin.get_floatingips(
                            admin_context, filters=filters)
        if not floatingips:
            LOG.error(_("Floating IP is not allocated for Service "
                        "Port"))
            raise
        #model.set_service_target(context, svc_mgmt_pt['id'], 'management')
        return (svc_mgmt_port, floatingips[0])

    def revert_stitching(self, context, provider_subnet):
        stitching_subnet_id = self._get_stitching_subnet_id(context)
        if not stitching_subnet_id:
            LOG.error(_("Stitching network is not present"))
            return
        try:
            self._delete_extra_route(
                context, stitching_subnet_id, provider_subnet)
        except Exception as err:
            LOG.error(_("Removing extra route failed : %s"), err)

    def delete_port(self, context, port_id, admin_required):
        admin_context = n_context.get_admin_context()
        if admin_required:
            delete_context = admin_context
        else:
            delete_context = context.plugin_context
        try:
            port = context.core_plugin.get_port(delete_context, port_id)
            context.core_plugin.delete_port(delete_context, port_id)
            self._notify_port_action(context, port, 'delete')
        except n_exc.PortNotFound:
            LOG.warn(_("Port %s is missing") % port_id)
            return

    def _get_stitching_subnet_id(self, context, create_if_not_present=False):
        group = {"name": STITCHING_PTG_NAME,
                 "description": "",
                 "subnets": [],
                 'l2_policy_id': None,
                 'provided_policy_rule_sets': {},
                 'consumed_policy_rule_sets': {},
                 'network_service_policy_id': None,
                 'shared': False}
        filters = {'name': [STITCHING_PTG_NAME],
                   'tenant_id': [context.provider['tenant_id']]}
        stitching_ptgs = context.gbp_plugin.get_policy_target_groups(
                                        context._plugin_context, filters)
        if stitching_ptgs:
            stitching_group = stitching_ptgs[0]
        elif create_if_not_present:
            stitching_group = context.gbp_plugin.create_policy_target_group(
                    context._plugin_context, {"policy_target_group": group})
        else:
            return None
        return stitching_group['subnets'][0]

    def _create_stitching_port(self, context, admin_context, service_type,
                               stitching_subnet_id):
        stitching_port_id = None
        stitching_port_ip = None
        stitching_port = None
        if stitching_subnet_id:
            port_name = "stitching-port" + service_type
            subnet = context.core_plugin.get_subnet(
                                admin_context, stitching_subnet_id)
            network_id = subnet['network_id']
            stitching_port = self._create_port(
                context, admin_context, admin_context.tenant_id,
                port_name, network_id, subnet_id=stitching_subnet_id)

            stitching_port_id = stitching_port['id']
            stitching_port_ip = stitching_port[
                                    'fixed_ips'][0]['ip_address']
            return (stitching_port_id, stitching_port_ip)

    def _add_extra_route(self, context, stitching_interface_ip,
                         stitching_subnet_id, provider_subnet_id):
        # TODO(Magesh): Pass subnet ID in filters
        ports = context.core_plugin.get_ports(
            context._plugin_context,
            filters={'device_owner': ['network:router_interface'],
                     'fixed_ips':  {'subnet_id': [stitching_subnet_id]}})
        router_port = ports and ports[0] or {}
        router_id = router_port.get('device_id')

        if not router_id:
            LOG.error(_("Router not attached to stitching network"))
            return

        subnet = context.core_plugin.get_subnet(
            context._plugin_context, provider_subnet_id)
        provider_subnet_cidr = subnet['cidr']
        route_to_add = {"nexthop": stitching_interface_ip,
                        "destination": provider_subnet_cidr}
        self._add_router_route(context, router_id, route_to_add)

    def _delete_extra_route(self, context, stitching_subnet_id,
                           provider_subnet_id):
        ports = context.core_plugin.get_ports(
            context._plugin_context,
            filters={'device_owner': ['network:router_interface'],
                     'fixed_ips':  {'subnet_id': [stitching_subnet_id]}})
        router_port = ports and ports[0] or {}
        router_id = router_port.get('device_id')

        if not router_id:
            LOG.error(_("Router not attached to stitching network"))
            return

        provider_subnet = context.core_plugin.get_subnet(
            context._plugin_context, provider_subnet_id)
        provider_subnet_cidr = provider_subnet['cidr']
        route_to_remove = {"destination": provider_subnet_cidr}
        self._remove_router_route(context, router_id, route_to_remove)

    def _create_pt(self, context, ptg_id, name,
                   port_id=None, admin_context=None):
        if admin_context:
            ctx = admin_context
        else:
            ctx = context._plugin_context
        pt = {'name': name,
              'description': '',
              'tenant_id': ctx.tenant_id,
              'policy_target_group_id': ptg_id,
              'port_id': port_id}
        return context.gbp_plugin.create_policy_target(
            ctx, {"policy_target": pt})

    def _add_router_route(self, context, router_id, route_to_add):
        router = context.l3_plugin.get_router(context._plugin_context,
                                              router_id)
        new_routes = router['routes']
        if route_to_add not in new_routes:
            new_routes.insert(0, route_to_add)  # insert in the begining
            self._update_router_routes(context, router_id, new_routes)

    def _remove_router_route(self, context, router_id, route_to_remove):
        router = context.l3_plugin.get_router(context._plugin_context,
                                              router_id)
        routes = router['routes']
        route_list_to_remove = []
        for route in routes:
            if route_to_remove['destination'] == route['destination']:
                route_list_to_remove.append(route)
        new_routes = [x for x in routes if x not in route_list_to_remove]
        self._update_router_routes(context, router_id, new_routes)

    def _update_router_routes(self, context, router_id, new_routes):
        """
        Adds extra routes to the router resource.

        :param router_id: uuid of the router,
        :param new_routes: list of new routes in this format
                          "routes": [
                                       {
                                            "nexthop": "10.1.0.10",
                                            "destination": "40.0.1.0/24"
                                       },....
                                    ]
        """
        admin_context = n_context.get_admin_context()
        router_info = {"router": {"routes": new_routes}}
        context.l3_plugin.update_router(admin_context, router_id, router_info)

    def _create_port(self, context, admin_context, tenant_id, port_name,
                     network_id, ip_address=None, subnet_id=None):
        if subnet_id:
            fixed_ips = [{"subnet_id": subnet_id}]
        elif ip_address:
            fixed_ips = [{"ip_address": ip_address}]
        else:
            # TODO(Magesh): Test if ATTR_NOT_SPECIFIED works fine
            fixed_ips = attributes.ATTR_NOT_SPECIFIED

        attrs = {'port': {'tenant_id': tenant_id,
                          'name': port_name,
                          'network_id': network_id,
                          'fixed_ips': fixed_ips,
                          'port_security_enabled': False,
                          'admin_state_up': True,
                          'mac_address': attributes.ATTR_NOT_SPECIFIED,
                          'device_id': '',
                          'device_owner': ''
                          }
                 }

        try:
            port = context.core_plugin.create_port(
                admin_context, attrs)
            self._notify_port_action(context, port, 'create')
        except Exception:
            LOG.exception(_("create port failed."))
            return
        return port

    def _dhcp_agent_notifier(self, context):
        # REVISIT(Magesh): Need initialization method after all
        # plugins are loaded to grab and store notifier.
        if not self._cached_agent_notifier:
            agent_notifiers = getattr(
                    context.core_plugin, 'agent_notifiers', {})
            self._cached_agent_notifier = (
                agent_notifiers.get(const.AGENT_TYPE_DHCP) or
                dhcp_rpc_agent_api.DhcpAgentNotifyAPI())
        return self._cached_agent_notifier

    def _notify_port_action(self, context, port, action):
        if cfg.CONF.dhcp_agent_notification:
            self._dhcp_agent_notifier(context).notify(
                context.plugin_context, {'port': port},
                'port.' + action + '.end')


class OneConvergenceServiceNodeDriver(heat_node_driver.HeatNodeDriver):

    sc_supported_type = [pconst.LOADBALANCER, pconst.FIREWALL, pconst.VPN]
    vendor_name = 'oneconvergence'
    # REVISIT(Magesh): Check if VPN validation is fine
    required_heat_resources = {pconst.LOADBALANCER: [
                                            'OS::Neutron::LoadBalancer',
                                            'OS::Neutron::Pool'],
                               pconst.FIREWALL: [
                                            'OS::Neutron::Firewall',
                                            'OS::Neutron::FirewallPolicy'],
                               pconst.VPN: ['OS::Neutron::VPNService']}
    initialized = False

    def __init__(self):
        super(OneConvergenceServiceNodeDriver, self).__init__()
        self.svc_mgr = SvcManagerClientApi(cfg.CONF.host)
        self.ts_driver = TrafficStitchingDriver()

    @log.log
    def initialize(self, name):
        self.initialized = True
        self._name = name

    @log.log
    def get_plumbing_info(self, context):
        return False

    @log.log
    def validate_create(self, context):
        # Heat Node driver in Juno supports non service-profile based model
        if not context.current_profile:
            raise heat_node_driver.ServiceProfileRequired()
        super(OneConvergenceServiceNodeDriver, self).validate_create(context)

    @log.log
    def validate_update(self, context):
        # Heat Node driver in Juno supports non service-profile based model
        if not context.original_node:  # PT create/delete notifications
            return
        if context.current_node and not context.current_profile:
            raise heat_node_driver.ServiceProfileRequired()
        super(OneConvergenceServiceNodeDriver, self).validate_update(context)

    @log.log
    def update_policy_target_added(self, context, policy_target):
        if context.current_node['service_profile_id']:
            service_type = context.current_profile['service_type']
        else:
            service_type = context.current_node['service_type']

        if service_type != pconst.LOADBALANCER:
            return

        self.update(context)

    @log.log
    def update_policy_target_removed(self, context, policy_target):
        if context.current_node['service_profile_id']:
            service_type = context.current_profile['service_type']
        else:
            service_type = context.current_node['service_type']

        if service_type != pconst.LOADBALANCER:
            return

        self.update(context)

    @log.log
    def update(self, context):
        heatclient = self._get_heat_client(context.plugin_context)
        stack_template, stack_params = (
                        self._fetch_template_and_params_for_update(context))
        stack_ids = self._get_node_instance_stacks(context.plugin_session,
                                                   context.current_node['id'],
                                                   context.instance['id'])
        for stack in stack_ids:
            self._wait_for_stack_operation_complete(
                                heatclient, stack.stack_id, 'update')
            heatclient.update(stack.stack_id, stack_template, stack_params)

    def _get_admin_context(self):
        admin_context = n_context.get_admin_context()
        admin_context._plugin_context = copy.copy(admin_context)
        admin_tenant = self.get_admin_tenant_object()
        admin_context.tenant_name = admin_tenant.name
        admin_context.tenant_id = admin_tenant.id
        return admin_context

    # REVISIT(Magesh): This method shares a lot of common code with the next
    # one, club the common code together
    def _fetch_template_and_params_for_update(self, context):
        sc_instance = context.instance
        sc_node = context.current_node
        provider_ptg = context.provider

        # TODO(Magesh): Handle multiple subnets
        provider_ptg_subnet_id = provider_ptg['subnets'][0]
        provider_subnet = context.core_plugin.get_subnet(
                            context._plugin_context, provider_ptg_subnet_id)
        service_type = context.current_profile['service_type']

        stack_template = sc_node.get('config')
        stack_template = (jsonutils.loads(stack_template) if
                          stack_template.startswith('{') else
                          yaml.load(stack_template))
        config_param_values = sc_instance.get('config_param_values', {})
        stack_params = {}

        if config_param_values:
            config_param_values = jsonutils.loads(config_param_values)

        is_template_aws_version = stack_template.get(
                                        'AWSTemplateFormatVersion', False)
        resources_key = ('Resources' if is_template_aws_version
                         else 'resources')
        parameters_key = ('Parameters' if is_template_aws_version
                          else 'parameters')
        properties_key = ('Properties' if is_template_aws_version
                          else 'properties')

        insert_type = ('north_south' if context.is_consumer_external else
                       'east_west')

        if service_type == pconst.LOADBALANCER:
            self._generate_pool_members(context, stack_template,
                                        config_param_values,
                                        provider_ptg,
                                        is_template_aws_version)

        # copying to _plugin_context should not be required if we are not
        # mixing service chain context with plugin context anywhere
        admin_context = self._get_admin_context()
        service_info = self.svc_mgr.get_service_info_with_srvc_type(
                context=context.plugin_context, service_type=service_type,
                tenant_id=context.plugin_context.tenant_id,
                insert_type=insert_type)

        # If we are going to share an already launched VM, we do not have
        # to create new ports/PTs for management and stitching
        if service_info:
            floating_ip = service_info['floating_ip']
            provider_port_id = service_info['provider_port_id']
            provider_port_mac = context.core_plugin.get_port(
                    admin_context, provider_port_id)['mac_address']
        else:
            raise ServiceInfoNotAvailableOnUpdate()

        if service_type != pconst.LOADBALANCER:
            if service_type == pconst.FIREWALL:
                if not context.is_consumer_external:
                    consumer_ptg_subnet_id = context.consumer['subnets'][0]
                    consumer_subnet = context.core_plugin.get_subnet(
                        context._plugin_context, consumer_ptg_subnet_id)
                    consumer_cidr = consumer_subnet['cidr']
                else:
                    consumer_cidr = '0.0.0.0/0'

                provider_cidr = provider_subnet['cidr']
                stack_template = self._update_template_with_firewall_rules(
                    context, provider_ptg, provider_cidr, consumer_cidr,
                    stack_template, is_template_aws_version)
                firewall_desc = {'vm_management_ip': floating_ip,
                                 'provider_ptg_info': [provider_port_mac],
                                 'insert_type': insert_type}
                stack_template[resources_key]['Firewall'][properties_key][
                    'description'] = str(firewall_desc)
            elif service_type == pconst.VPN:
                stitching_subnet_id = self.ts_driver._get_stitching_subnet_id(
                                context, create_if_not_present=False)
                config_param_values['Subnet'] = stitching_subnet_id
                l2p = context.gbp_plugin.get_l2_policy(
                        context.plugin_context, provider_ptg['l2_policy_id'])
                l3p = context.gbp_plugin.get_l3_policy(
                        context.plugin_context, l2p['l3_policy_id'])
                config_param_values['RouterId'] = l3p['routers'][0]
                desc = 'fip=' + floating_ip + ";" + "tunnel_local_cidr=" + provider_subnet['cidr']
                stack_params['ServiceDescription'] = desc
        else:
            config_param_values['service_chain_metadata'] = (
                SC_METADATA % (sc_instance['id'], insert_type, floating_ip,
                               provider_port_mac))

        node_params = (stack_template.get(parameters_key) or [])
        for parameter in node_params:
            if parameter == "Subnet":
                stack_params[parameter] = provider_ptg_subnet_id
            elif parameter in config_param_values:
                stack_params[parameter] = config_param_values[parameter]

        LOG.info(_("Final stack_template : %(template)s, stack_params : "
                   "%(param)s"), {'template': stack_template,
                                  'param': stack_params})
        return (stack_template, stack_params)

    def _fetch_template_and_params(self, context, update=False):
        sc_instance = context.instance
        sc_node = context.current_node
        provider_ptg = context.provider

        # TODO(Magesh): Handle multiple subnets
        provider_ptg_subnet_id = provider_ptg['subnets'][0]
        provider_subnet = context.core_plugin.get_subnet(
                            context._plugin_context, provider_ptg_subnet_id)
        service_type = context.current_profile['service_type']

        stack_template = sc_node.get('config')
        stack_template = (jsonutils.loads(stack_template) if
                          stack_template.startswith('{') else
                          yaml.load(stack_template))
        config_param_values = sc_instance.get('config_param_values', {})
        stack_params = {}

        if config_param_values:
            config_param_values = jsonutils.loads(config_param_values)

        is_template_aws_version = stack_template.get(
                                        'AWSTemplateFormatVersion', False)
        resources_key = ('Resources' if is_template_aws_version
                         else 'resources')
        parameters_key = ('Parameters' if is_template_aws_version
                          else 'parameters')
        properties_key = ('Properties' if is_template_aws_version
                          else 'properties')

        insert_type = 'north_south' if context.is_consumer_external else 'east_west'

        if service_type == pconst.LOADBALANCER:
            self._generate_pool_members(context, stack_template,
                                        config_param_values,
                                        provider_ptg,
                                        is_template_aws_version)

        consumer_port_id = None
        stitching_port_id = None
        rvpn_client_pool_cidr = None

        # copying to _plugin_context should not be required if we are not
        # mixing service chain context with plugin context anywhere
        admin_context = self._get_admin_context()
        service_info = self.svc_mgr.get_existing_service_for_sharing(
                context=context.plugin_context, service_type=service_type,
                tenant_id=context.plugin_context.tenant_id,
                insert_type=insert_type)

        LOG.info(_("Sharing service info: %s") %(service_info))
        # If we are going to share an already launched VM, we do not have
        # to create new ports/PTs for management and stitching
        if service_info:
            svc_mgmt_port = None
            floatingip_id = None
            floating_ip = service_info['floating_ip']
            if service_type != pconst.LOADBALANCER:
                stitching_port_id = service_info['stitching_port_id']
        else:
            svc_mgmt_port, floatingip = (
                    self.ts_driver.create_service_management_port(
                                            context, admin_context))
            floatingip_id = floatingip['id']
            floating_ip = floatingip['floating_ip_address']

        if service_type != pconst.LOADBALANCER:
            stitching_port_id, stitching_subnet_id = (
                self.ts_driver.setup_stitching(
                    context, admin_context, service_type,
                    stitching_port_id=stitching_port_id,
                    provider=provider_ptg))
            # TODO(Magesh): Handle VPN-FW sharing here itself
            provider_port_id, provider_port_mac = (
                self.ts_driver.reclaim_gw_port_for_servicevm(
                    context, provider_ptg_subnet_id,
                    admin_context=admin_context))
            if service_type != pconst.VPN:
                if not context.is_consumer_external:
                    consumer_ptg_subnet_id = context.consumer['subnets'][0]
                    consumer_subnet = context.core_plugin.get_subnet(
                        context._plugin_context, consumer_ptg_subnet_id)
                    consumer_cidr = consumer_subnet['cidr']
                    consumer_port_id, consumer_port_mac = (
                        self.ts_driver.reclaim_gw_port_for_servicevm(
                                        context, consumer_ptg_subnet_id,
                                        admin_context=admin_context))
                else:
                    consumer_cidr = '0.0.0.0/0'

                provider_cidr = provider_subnet['cidr']
                stack_template = self._update_template_with_firewall_rules(
                    context, provider_ptg, provider_cidr, consumer_cidr,
                    stack_template, is_template_aws_version)
        else:
            subnet = context.core_plugin.get_subnet(context._plugin_context,
                                                    provider_ptg_subnet_id)
            network_id = subnet['network_id']
            provider_port = self.ts_driver.create_lb_port(
                admin_context, network_id, provider_ptg_subnet_id, context)
            provider_port_id = provider_port['id']

        self.svc_mgr.create_service_instance(
                        context=context._plugin_context,
                        tenant_id=context._plugin_context.tenant_id,
                        service_chain_instance_id=sc_instance['id'],
                        service_type=service_type,
                        provider_network_port=provider_port_id,
                        consumer_network_port=consumer_port_id,
                        stitching_network_port=stitching_port_id,
                        management_port=svc_mgmt_port,
                        insert_type=insert_type,
                        management_fip_id=floatingip_id)

        if service_type != pconst.LOADBALANCER:
            if service_type != pconst.VPN:
                firewall_desc = {'vm_management_ip': floating_ip,
                                 'provider_ptg_info': [provider_port_mac],
                                 'insert_type': insert_type}
                stack_template[resources_key]['Firewall'][properties_key][
                    'description'] = str(firewall_desc)
            else:
                #For remote vpn - we need to create a implicit l3 policy
                #for client pool cidr, to avoid this cidr being reused.
                #a) Check for this tenant if this l3 policy is defined.
                #   1) If yes, get the cidr
                #   2) Else, goto b)
                #b) Create one for this tenant and do step a.1)
                rvpn_l3policy_filter = {
                    'tenant_id': [context.plugin_context.tenant_id],
                    'name': ["remote-vpn-client-pool-cidr-l3policy"]}
                rvpn_l3_policy = context.gbp_plugin.get_l3_policies(
                    context._plugin_context,
                    rvpn_l3policy_filter)

                if not rvpn_l3_policy:
                    rvpn_l3_policy = {
                        'l3_policy':{
                        'name': "remote-vpn-client-pool-cidr-l3policy",
                        'description': "L3 Policy for \
                            remote vpn client pool cidr",
                        'ip_pool': cfg.CONF.oneconvergence_node_driver.\
                            remote_vpn_client_pool_cidr,
                        'ip_version': 4,
                        'subnet_prefix_length': 24,
                        'tenant_id': context.plugin_context.tenant_id}}

                    rvpn_l3_policy = context.gbp_plugin.create_l3_policy(
                            context.plugin_context,
                            rvpn_l3_policy)
                else:
                    rvpn_l3_policy = rvpn_l3_policy[0]
                rvpn_client_pool_cidr = rvpn_l3_policy['ip_pool']

                config_param_values['ClientAddressPoolCidr'] = \
                    rvpn_client_pool_cidr

                config_param_values['Subnet'] = stitching_subnet_id
                l2p = context.gbp_plugin.get_l2_policy(
                        context.plugin_context, provider_ptg['l2_policy_id'])
                l3p = context.gbp_plugin.get_l3_policy(
                        context.plugin_context, l2p['l3_policy_id'])
                config_param_values['RouterId'] = l3p['routers'][0]
                desc = 'fip=' + floating_ip + ";" + "tunnel_local_cidr=" + provider_subnet['cidr']
                stack_params['ServiceDescription'] = desc
        else:
            # FIXME(Magesh): Raise error or autocorrect template if the key
            # is not present or use description instead
            config_param_values['service_chain_metadata'] = (
                SC_METADATA % (sc_instance['id'], insert_type, floating_ip,
                               provider_port['mac_address']))

        node_params = (stack_template.get(parameters_key) or [])
        for parameter in node_params:
            # For VPN, we are filling in Subnet as Stitching Subnet as
            # stitching already
            if parameter == "Subnet" and service_type != pconst.VPN:
                stack_params[parameter] = provider_ptg_subnet_id
            elif parameter in config_param_values:
                stack_params[parameter] = config_param_values[parameter]

        LOG.info(_("Final stack_template : %(template)s, stack_params : "
                   "%(param)s"), {'template': stack_template,
                                  'param': stack_params})
        return (stack_template, stack_params)

    # FIXME(Magesh): Redirect is implicit Allow for GBP, but we are not adding
    # allow rules in Firewall for redirect classifier
    def _update_template_with_firewall_rules(self, context, provider_ptg,
                                             provider_cidr, consumer_cidr,
                                             stack_template,
                                             is_template_aws_version):
        resources_key = 'Resources' if is_template_aws_version else 'resources'
        properties_key = ('Properties' if is_template_aws_version
                          else 'properties')
        fw_rule_key = self._get_heat_resource_key(
                            stack_template[resources_key],
                            is_template_aws_version,
                            'OS::Neutron::FirewallRule')
        provider_policy_rule_sets_list = provider_ptg[
            "provided_policy_rule_sets"]
        provider_policy_rule_sets = context.gbp_plugin.get_policy_rule_sets(
                    context._plugin_context,
                    filters={'id': provider_policy_rule_sets_list})
        policy_rule_ids = list()
        for rule_set in provider_policy_rule_sets:
            policy_rule_ids.extend(rule_set.get("policy_rules"))

        policy_rules = context.gbp_plugin.get_policy_rules(
            context._plugin_context, filters={'id': policy_rule_ids})

        i = 0
        fw_rule_list = []
        for policy_rule in policy_rules:
            policy_action_ids = policy_rule.get("policy_actions")
            policy_actions_detail = context.gbp_plugin.get_policy_actions(
                    context._plugin_context, filters={'id': policy_action_ids})
            for policy_action in policy_actions_detail:
                if policy_action["action_type"] == constants.GP_ACTION_ALLOW:
                    classifier = context.gbp_plugin.get_policy_classifier(
                            context._plugin_context,
                            policy_rule.get("policy_classifier_id"))

                    rule_name = "Rule_%s" % i
                    stack_template[resources_key][rule_name] = (
                                            self._generate_firewall_rule(
                                                is_template_aws_version,
                                                classifier.get("protocol"),
                                                classifier.get("port_range"),
                                                provider_cidr, consumer_cidr))

                    fw_rule_list.append({'get_resource': rule_name})
                    i += 1

        if consumer_cidr != '0.0.0.0/0' or not fw_rule_key:
            stack_template[resources_key]['Firewall_Policy'][properties_key][
                'firewall_rules'] = fw_rule_list
        return stack_template

    def _generate_firewall_rule(self, is_template_aws_version, protocol,
                                destination_port, destination_cidr,
                                source_cidr):
        type_key = 'Type' if is_template_aws_version else 'type'
        properties_key = ('Properties' if is_template_aws_version
                          else 'properties')
        fw_rule_obj = {type_key: "OS::Neutron::FirewallRule",
                       properties_key: {
                           "protocol": protocol,
                           "enabled": True,
                           "action": "allow"
                       }
                       }
        if destination_port:
            fw_rule_obj[properties_key].update(
                {"destination_port": destination_port})
        if destination_cidr:
            fw_rule_obj[properties_key].update(
                {"destination_ip_address": destination_cidr})
        if source_cidr:
            fw_rule_obj[properties_key].update(
                {"source_ip_address": source_cidr})

        return fw_rule_obj

    @log.log
    def delete(self, context):
        service_type = context.current_profile['service_type']
        insert_type = ('north_south' if context.is_consumer_external else
                       'east_west')
        admin_context = n_context.get_admin_context()

        self.ts_driver.revert_stitching(
                        context, context.provider['subnets'][0])
        ports_to_cleanup = self.svc_mgr.delete_service_instance(
                            context=context._plugin_context,
                            tenant_id=context._plugin_context.tenant_id,
                            insert_type=insert_type,
                            service_chain_instance_id=context.instance['id'],
                            service_type=service_type)

        for key in ports_to_cleanup or {}:
            if ports_to_cleanup.get(key):
                filters = {'port_id': [ports_to_cleanup[key]]}
                admin_required = True
                policy_targets = context.gbp_plugin.get_policy_targets(
                            context.admin_context, filters)
                if policy_targets:
                    for policy_target in policy_targets:
                        try:
                            context.gbp_plugin.delete_policy_target(
                                admin_context, policy_target['id'],
                                notify_sc=False)
                        except Exception:
                            # Mysql deadlock was detected once. Investigation
                            # is required
                            LOG.exception(_("Failed to delete Policy Target"))
                else:
                    self.ts_driver.delete_port(
                        context, ports_to_cleanup[key], admin_required)

                # Workaround for Mgmt PT cleanup. In Juno, instance delete
                # deletes the user created port also. So we cant retrieve the
                # exact PT unless we extend DB
                if key == 'mgmt_port_id':
                    filters = {'name': ['mgmt-pt']}
                    policy_targets = context.gbp_plugin.get_policy_targets(
                            context.admin_context, filters)
                    for policy_target in policy_targets:
                        if policy_target['port_id']:
                            continue
                        try:
                            context.gbp_plugin.delete_policy_target(
                                admin_context, policy_target['id'],
                                notify_sc=False)
                        except Exception:
                            # Mysql deadlock was detected once. Investigation
                            # is required
                            LOG.exception(_("Failed to delete Policy Target"))

                #if key == 'mgmt_port_id':
                #    self._delete_service_targets(context, admin_context)
        super(OneConvergenceServiceNodeDriver, self).delete(context)

    def _delete_service_targets(self, context, admin_context):
        policy_targets = model.get_service_targets(
                            context.session,
                            servicechain_instance_id=context.instance['id'],
                            servicechain_node_id=context.current_node['id'])
        for policy_target in policy_targets:
            try:
                context.gbp_plugin.delete_policy_target(
                    admin_context, policy_target.policy_target_id,
                    notify_sc=False)
            except Exception as err:
                LOG.warn(_("Cleaning up Service PT failed. Error: %(err)s"),
                         {'err': err.message})

    def _get_heat_client(self, plugin_context):
        self.assign_admin_user_to_project(plugin_context.tenant)
        admin_token = self.keystone(tenant_id=plugin_context.tenant).get_token(
                                                        plugin_context.tenant)
        return heat_api_client.HeatClient(
                                plugin_context,
                                cfg.CONF.oneconvergence_node_driver.heat_uri,
                                auth_token=admin_token)

    def keystone(self, tenant_id=None):
        keystone_conf = cfg.CONF.keystone_authtoken
        if keystone_conf.get('auth_uri'):
            auth_url = keystone_conf.auth_uri
            if not auth_url.endswith('/v2.0/'):
                auth_url += '/v2.0/'
        else:
            auth_url = ('%s://%s:%s/v2.0/' % (
                keystone_conf.auth_protocol,
                keystone_conf.auth_host,
                keystone_conf.auth_port))
        user = (keystone_conf.get('admin_user') or keystone_conf.username)
        pw = (keystone_conf.get('admin_password') or
              keystone_conf.password)
        if tenant_id:
            return keyclient.Client(
                username=user, password=pw, auth_url=auth_url,
                tenant_id=tenant_id)
        else:
            tenant_name = keystone_conf.get('admin_tenant_name')
            return keyclient.Client(
                username=user, password=pw, auth_url=auth_url,
                tenant_name=tenant_name)

    def get_v3_keystone_admin_client(self):
        """ Returns keystone v3 client with admin credentials
            Using this client one can perform CRUD operations over
            keystone resources.
        """
        keystone_conf = cfg.CONF.keystone_authtoken
        user = (keystone_conf.get('admin_user') or keystone_conf.username)
        pw = (keystone_conf.get('admin_password') or
              keystone_conf.password)
        v3_auth_url = ('%s://%s:%s/v3/' % (
            keystone_conf.auth_protocol, keystone_conf.auth_host,
            keystone_conf.auth_port))
        v3client = keyclientv3.Client(
            username=user, password=pw, project_domain_name="default",
            project_name="admin", user_domain_name="default",
            auth_url=v3_auth_url)
        return v3client

    def get_role_by_name(self, v3client, name):
        '''returns role object by this name
        '''
        role = v3client.roles.list(name=name)
        if role:
            return role[0]

    def assign_admin_user_to_project(self, project_id):
        v3client = self.get_v3_keystone_admin_client()
        keystone_conf = cfg.CONF.keystone_authtoken
        admin_id = v3client.users.list(domain='default',
            name=keystone_conf.get('admin_user'))[0].id
        neutron_admin_role = self.get_role_by_name(v3client, "neutron_admin")
        v3client.roles.grant(neutron_admin_role.id, user=admin_id,
                             project=project_id)
        heat_role = self.get_role_by_name(v3client, "heat_stack_owner")
        v3client.roles.grant(heat_role.id, user=admin_id, project=project_id)

    def get_admin_tenant_object(self):
        v3client = self.get_v3_keystone_admin_client()
        keystone_conf = cfg.CONF.keystone_authtoken
        admin_tenant = v3client.projects.find(
            name=keystone_conf.get('admin_tenant_name'))
        return admin_tenant
