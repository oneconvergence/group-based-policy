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
from neutron.openstack.common import uuidutils
from neutron.openstack.common import log as logging
from neutron.plugins.common import constants as pconst
from neutron.services.oc_service_manager.oc_service_manager_client import (
                                                        SvcManagerClientApi)
from oslo.config import cfg
import time

from gbpservice.neutron.services.grouppolicy.common import constants
from gbpservice.neutron.services.servicechain.plugins.ncp import (
                                                    exceptions as exc)
from gbpservice.neutron.services.servicechain.plugins.ncp import model
from gbpservice.neutron.services.servicechain.plugins.ncp.node_drivers import (
                                heat_node_driver as heat_node_driver)
from gbpservice.neutron.services.servicechain.plugins.ncp.node_drivers import (
                                openstack_heat_api_client as heat_api_client)
from copy import deepcopy


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
    cfg.IntOpt('stack_action_wait_time',
               default=60,
               help=_("Seconds to wait for pending stack operation "
                      "to complete")),
]

cfg.CONF.register_opts(oneconvergence_driver_opts, "oneconvergence_node_driver")

SC_METADATA = '{"sc_instance":"%s", "insert_type":"%s", "floating_ip": "%s", "provider_interface_mac": "%s"}'
SVC_MGMT_PTG_NAME = cfg.CONF.oneconvergence_node_driver.svc_management_ptg_name
STITCHING_PTG_NAME = "traffic-stitching-gbp-internal"

POOL_MEMBER_PARAMETER_AWS = {"Description": "Pool Member IP Address",
                             "Type": "String"}
POOL_MEMBER_PARAMETER = {"description": "Pool Member IP Address",
                         "type": "string"}

STACK_ACTION_WAIT_TIME = cfg.CONF.oneconvergence_node_driver.stack_action_wait_time
STACK_ACTION_RETRY_WAIT = 5  # Retry after every 5 seconds

LOG = logging.getLogger(__name__)


class InvalidServiceType(exc.NodeCompositionPluginBadRequest):
    message = _("The OneConvergence Node driver only supports the services "
                "VPN, Firewall and LB in a Service Chain")

class ServiceInfoNotAvailableOnUpdate(n_exc.NeutronException):
    message = _("Service information is not available with Service Manager "
                "on node update")


class StackCreateFailedException(n_exc.NeutronException):
    message = _("Stack : %(stack_name)s creation failed for tenant : "
                "%(stack_owner)s ")


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
                 'service_management': False,
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

        self.update(context, pt_added_or_removed=True)

    @log.log
    def update_policy_target_removed(self, context, policy_target):
        if context.current_node['service_profile_id']:
            service_type = context.current_profile['service_type']
        else:
            service_type = context.current_node['service_type']

        if service_type != pconst.LOADBALANCER:
            return

        self.update(context, pt_added_or_removed=True)

    @log.log
    def notify_chain_parameters_updated(self, context):
        pass # We are not using the classifier specified in redirect Rule

    @log.log
    def check_for_existing_service(self, context):
        if context._provider_group['provided_policy_rule_sets']:
            provided_policy_rule_set_id = context._provider_group[
                'provided_policy_rule_sets'][0]
        else:
            return True, None, True
        provided_policy_rule_set = context._gbp_plugin.get_policy_rule_set(
            context.plugin_context, provided_policy_rule_set_id)
        cons_policy_target_groups = provided_policy_rule_set[
            'consuming_policy_target_groups']

        stack, sc_instances = self.get_firewall_stack_id(context,
                                             cons_policy_target_groups)

        if context.consumer['id'] in cons_policy_target_groups:
            cons_policy_target_groups.remove(context.consumer['id'])

        if stack:
            return True, cons_policy_target_groups, False
        else:
             return False, cons_policy_target_groups, False
        #
        # if cons_policy_target_groups:
        #     return True, cons_policy_target_groups, False
        # else:
        #     return False, cons_policy_target_groups, False

    @log.log
    def append_firewall_rule(self, context, stack_template, provider_cidr,
                             consumer_cidr, fw_template_properties):
        resources_key = fw_template_properties['resources_key']
        properties_key = fw_template_properties['properties_key']
        fw_rule_keys = fw_template_properties['fw_rule_keys']
        rule_name = fw_template_properties['name']
        fw_policy_key = fw_template_properties['fw_policy_key']
        i = 1
        for fw_rule_key in fw_rule_keys:
            fw_rule_name = (rule_name + '_' + str(i))
            rule = deepcopy(stack_template[resources_key][fw_rule_key])
            stack_template[resources_key][fw_rule_name] = rule
            # Considering only for E-W case
            fw_rule_resource = stack_template[resources_key][fw_rule_name][
                properties_key]
            fw_rule_resource['destination_ip_address'] = provider_cidr
            fw_rule_resource['source_ip_address'] = consumer_cidr
            if stack_template[resources_key][fw_policy_key][
                properties_key].get('firewall_rules'):
                stack_template[resources_key][fw_policy_key][
                    properties_key]['firewall_rules'].append({
                    'get_resource': fw_rule_name})
            i += 1

    @log.log
    def update_firewall_template(self, context, stack_template,
                                 ptg_to_not_configure=None):
        _exist, consumer_ptgs, prov_unset = self.check_for_existing_service(
            context)

        # if not _exist:
        #     return
        filters = {'id': consumer_ptgs}
        consumer_ptgs_details = context._gbp_plugin.get_policy_target_groups(
            context.plugin_context, filters)

        provider_cidr = context.core_plugin._get_subnet(
            context._plugin_context, context.provider['subnets'][0])['cidr']

        is_template_aws_version = stack_template.get(
                                        'AWSTemplateFormatVersion', False)
        resources_key = 'Resources' if is_template_aws_version else 'resources'
        properties_key = ('Properties' if is_template_aws_version
                          else 'properties')
        fw_rule_keys = self._get_all_heat_resource_keys(
            stack_template[resources_key], is_template_aws_version,
            'OS::Neutron::FirewallRule')
        fw_policy_key = self._get_all_heat_resource_keys(
            stack_template['resources'], is_template_aws_version,
            'OS::Neutron::FirewallPolicy')[0]
        fw_template_properties = dict(
            resources_key=resources_key, properties_key=properties_key,
            is_template_aws_version=is_template_aws_version,
            fw_rule_keys=fw_rule_keys,
            fw_policy_key=fw_policy_key)

        for consumer in consumer_ptgs_details:
            if consumer['id'] == ptg_to_not_configure:
                continue
            fw_template_properties.update({'name': consumer['id'][:3]})
            consumer_cidr = context.core_plugin._get_subnet(
                context.plugin_context, consumer['subnets'][0])['cidr']
            self.append_firewall_rule(context, stack_template, provider_cidr,
                                      consumer_cidr, fw_template_properties)
        return stack_template

    @log.log
    def create(self, context):
        heatclient = self._get_heat_client(context.plugin_context)

        stack_name = ("stack_" + context.instance['name'] +
                      context.current_node['name'] +
                      context.instance['id'][:8] +
                      context.current_node['id'][:8])
        # Heat does not accept space in stack name
        stack_name = stack_name.replace(" ", "")
        stack_template, stack_params = self._fetch_template_and_params(
            context)

        service_type = context.current_profile["service_type"]
        if (service_type == pconst.LOADBALANCER or
                (service_type == pconst.FIREWALL and
                 not context.is_consumer_external)
            ):
            _exist, cons_ptgs, prov_unset = \
                self.check_for_existing_service(context)
            if _exist:
                return
            else:
                if service_type == pconst.FIREWALL:
                    self.update_firewall_template(context, stack_template)
        stack = heatclient.create(stack_name, stack_template, stack_params)
        stack_id = stack['stack']['id']
        self._insert_node_instance_stack_in_db(
            context.plugin_session, context.current_node['id'],
            context.instance['id'], stack_id)
        self._wait_for_stack_operation_complete(heatclient, stack_id, "create")

    @log.log
    def update(self, context, pt_added_or_removed=False):
        # If it is not a Node config update or PT change for LB, no op
        if (not pt_added_or_removed and (not context.original_node or
            context.original_node == context.current_node)):
            return
        heatclient = self._get_heat_client(context.plugin_context)
        stack_template, stack_params = (
            self._fetch_template_and_params_for_update(context))
        stack_ids = self._get_node_instance_stacks(context.plugin_session,
                                                   context.current_node['id'],
                                                   context.instance['id'])
        service_type = context.current_profile['service_type']
        for stack in stack_ids:
            # Wait for any previous update to complete
            self._wait_for_stack_operation_complete(
                heatclient, stack.stack_id, 'update')
            if (service_type == pconst.LOADBALANCER or
                    (service_type == pconst.FIREWALL and
                     not context.is_consumer_external)
                ):
                heatclient.delete(stack.stack_id)
                self._wait_for_stack_operation_complete(heatclient,
                                                        stack.stack_id,
                                                        'delete')
                self._delete_node_instance_stack_in_db(
                    context.plugin_session, context.current_node['id'],
                    context.instance['id'])
                # REVISIT(VK) Can this be a issue?
                stack_name = ("stack_" + context.instance['name'] +
                              context.current_node['name'] +
                              context.instance['id'][:8] +
                              context.current_node['id'][:8])
                # Update template
                if service_type == pconst.FIREWALL:
                    self.update_firewall_template(context, stack_template)
                stack = heatclient.create(stack_name, stack_template,
                                          stack_params)
                self._wait_for_stack_operation_complete(
                    heatclient, stack["stack"]["id"], "create")
                self._insert_node_instance_stack_in_db(
                    context.plugin_session, context.current_node['id'],
                    context.instance['id'], stack['stack']['id'])
            else:
                heatclient.update(stack.stack_id, stack_template, stack_params)
                # Wait for the current update to complete
                self._wait_for_stack_operation_complete(
                    heatclient, stack.stack_id, 'update')

    def _wait_for_stack_operation_complete(self, heatclient, stack_id, action):
        time_waited = 0
        create_failed = False
        while True:
            try:
                stack = heatclient.get(stack_id)
                if stack.stack_status == 'DELETE_FAILED':
                    heatclient.delete(stack_id)
                elif stack.stack_status == 'CREATE_COMPLETE':
                    return
                elif stack.stack_status == 'CREATE_FAILED':
                    create_failed = True
                    raise
                elif stack.stack_status not in ['UPDATE_IN_PROGRESS',
                    'CREATE_IN_PROGRESS', 'DELETE_IN_PROGRESS']:
                    return
            except Exception:
                if create_failed:
                    LOG.exception(_("Stack %(stack_name)s creation failed "
                                    "for tenant %(stack_owner)s"),
                                  {'stack_name': stack.stack_name,
                                   'stack_owner': stack.stack_owner})
                    raise StackCreateFailedException(
                        stack_name=stack.stack_name,
                        stack_owner=stack.stack_owner)
                LOG.exception(_("Retrieving the stack %(stack)s failed."),
                              {'stack': stack_id})
                return
            else:
                time.sleep(STACK_ACTION_RETRY_WAIT)
                time_waited = time_waited + STACK_ACTION_RETRY_WAIT
                if time_waited >= STACK_ACTION_WAIT_TIME:
                    LOG.error(_("Stack %(action)s not completed within "
                                "%(wait)s seconds"),
                              {'action': action,
                               'wait': STACK_ACTION_WAIT_TIME,
                               'stack': stack_id})
                    # Some times, a second delete request succeeds in cleaning
                    # up the stack when the first request is stuck forever in
                    #  Pending state
                    if action == 'delete':
                        heatclient.delete(stack_id)
                    return

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
            stitching_port_id = service_info['stitching_port_id']
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
                stack_template = self._update_firewall_template(
                    context, provider_ptg, provider_cidr, consumer_cidr,
                    stack_template, is_template_aws_version)
                firewall_desc = {'vm_management_ip': floating_ip,
                                 'provider_ptg_info': [provider_port_mac],
                                 'insert_type': insert_type}
                fw_key = self._get_heat_resource_key(
                    stack_template[resources_key],
                    is_template_aws_version,
                    'OS::Neutron::Firewall')
                stack_template[resources_key][fw_key][properties_key][
                    'description'] = str(firewall_desc)
            elif service_type == pconst.VPN:
                rvpn_l3policy_filter = {
                    'tenant_id': [context.plugin_context.tenant_id],
                    'name': ["remote-vpn-client-pool-cidr-l3policy"]}
                rvpn_l3_policy = context.gbp_plugin.get_l3_policies(
                    context._plugin_context,
                    rvpn_l3policy_filter)

                if not rvpn_l3_policy:
                    raise

                rvpn_l3_policy = rvpn_l3_policy[0]
                config_param_values['ClientAddressPoolCidr'] = rvpn_l3_policy[
                    'ip_pool']

                stitching_subnet_id = self.ts_driver._get_stitching_subnet_id(
                                context, create_if_not_present=False)
                config_param_values['Subnet'] = stitching_subnet_id
                l2p = context.gbp_plugin.get_l2_policy(
                        context.plugin_context, provider_ptg['l2_policy_id'])
                l3p = context.gbp_plugin.get_l3_policy(
                        context.plugin_context, l2p['l3_policy_id'])
                config_param_values['RouterId'] = l3p['routers'][0]

                filters = {'port_id': [stitching_port_id]}
                floatingips = context.l3_plugin.get_floatingips(admin_context,
                                                                filters=filters)
                if not floatingips:
                    LOG.error(_("Floating IP is not allocated for Service "
                                "Port"))
                    raise
                stitching_port_fip = context.l3_plugin.get_floatingip(
                    admin_context,
                    floatingips[0]['id'])['floating_ip_address']

                desc = ('fip=' + floating_ip + ";tunnel_local_cidr=" +
                        provider_subnet['cidr']+";user_access_ip=" + stitching_port_fip)
                stack_params['ServiceDescription'] = desc
        else:
            config_param_values['service_chain_metadata'] = (
                SC_METADATA % (sc_instance['id'], insert_type, floating_ip,
                               provider_port_mac))

        node_params = (stack_template.get(parameters_key) or [])
        for parameter in node_params:
            if parameter == "Subnet" and service_type != pconst.VPN:
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
                stack_template = self._update_firewall_template(
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
                fw_key = self._get_heat_resource_key(
                    stack_template[resources_key],
                    is_template_aws_version,
                    'OS::Neutron::Firewall')
                stack_template[resources_key][fw_key][properties_key][
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
                access_ip = self.svc_mgr.get_vpn_access_ip(
                    context._plugin_context, stitching_port_id)
                desc = ('fip=' + floating_ip + ";tunnel_local_cidr=" +
                        provider_subnet['cidr']+";user_access_ip=" + access_ip)
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

    def _get_all_heat_resource_keys(self, template_resource_dict,
                                    is_template_aws_version, resource_name):
        type_key = 'Type' if is_template_aws_version else 'type'
        resource_keys = []
        for key in template_resource_dict:
            if template_resource_dict[key].get(type_key) == resource_name:
                resource_keys.append(key)
        return resource_keys

    def _update_cidr_in_fw_rules(self, stack_template, provider_cidr,
                                         consumer_cidr,
                                         is_template_aws_version):
        resources_key = 'Resources' if is_template_aws_version else 'resources'
        properties_key = ('Properties' if is_template_aws_version
                          else 'properties')
        fw_rule_keys = self._get_all_heat_resource_keys(
            stack_template[resources_key],
            is_template_aws_version,
            'OS::Neutron::FirewallRule')
        for fw_rule_key in fw_rule_keys:
            fw_rule_resource = stack_template[resources_key][fw_rule_key][
                properties_key]
            if not fw_rule_resource.get('destination_ip_address'):
                fw_rule_resource['destination_ip_address'] = provider_cidr
            if (not fw_rule_resource.get('source_ip_address')
                and consumer_cidr != '0.0.0.0/0'):
                fw_rule_resource['source_ip_address'] = consumer_cidr

    # Updates CIDR when "PTG" is specified as source or destination in Firewall
    # rule. Firewall rules are not derived from PRS. This is different from
    # what Cisco plans to have. For us, the Firewall rules only come from Node
    # config
    def _update_firewall_template(self, context, provider_ptg, provider_cidr,
                                  consumer_cidr, stack_template,
                                  is_template_aws_version):
        self._update_cidr_in_fw_rules(stack_template, provider_cidr,
                                      consumer_cidr, is_template_aws_version)
        self._modify_fw_resources_name(
            context, stack_template, provider_ptg, is_template_aws_version)
        return stack_template

    def _modify_fw_resources_name(self, context, stack_template,
                                  provider_ptg, is_template_aws_version):
        resources_key = 'Resources' if is_template_aws_version else 'resources'
        properties_key = ('Properties' if is_template_aws_version
                          else 'properties')

        resource_name = 'OS::Neutron::FirewallPolicy'
        fw_policy_key = self._get_heat_resource_key(
                        stack_template[resources_key],
                        is_template_aws_version,
                        resource_name)
        fw_resource_name = 'OS::Neutron::Firewall'
        fw_key = self._get_heat_resource_key(
                        stack_template[resources_key],
                        is_template_aws_version,
                        fw_resource_name)
        # Include provider name in firewall, firewall policy.
        ptg_name = '-' + provider_ptg['name']
        stack_template[resources_key][fw_policy_key][
                                    properties_key]['name'] += ptg_name
        stack_template[resources_key][fw_key][
                                    properties_key]['name'] += ptg_name

    def _modify_lb_resources_name(self, context, stack_template,
                                  provider_ptg, is_template_aws_version):
        resources_key = 'Resources' if is_template_aws_version else 'resources'
        type_key = 'Type' if is_template_aws_version else 'type'
        properties_key = ('Properties' if is_template_aws_version
                          else 'properties')

        for resource in stack_template[resources_key]:
            if stack_template[resources_key][resource][type_key] == (
                                                    'OS::Neutron::Pool'):
                # Include provider name in Pool, VIP name.
                ptg_name = '-' + provider_ptg['name']
                stack_template[resources_key][resource][
                                    properties_key]['name'] += ptg_name
                stack_template[resources_key][resource][
                                    properties_key]['vip']['name'] += ptg_name

    def _generate_pool_members(self, context, stack_template,
                               config_param_values, provider_ptg,
                               is_template_aws_version):
        resources_key = 'Resources' if is_template_aws_version else 'resources'
        type_key = 'Type' if is_template_aws_version else 'type'
        self._modify_lb_resources_name(context, stack_template,
                                       provider_ptg, is_template_aws_version)
        member_ips = self._get_member_ips(context, provider_ptg)
        if not member_ips:
            return

        pool_res_name = None
        for resource in stack_template[resources_key]:
            if stack_template[resources_key][resource][type_key] == (
                                                    'OS::Neutron::Pool'):
                pool_res_name = resource
                break

        for member_ip in member_ips:
            member_name = 'mem-' + member_ip
            stack_template[resources_key][member_name] = (
                self._generate_pool_member_template(
                    context, is_template_aws_version,
                    pool_res_name, member_ip, stack_template))

    # REVISIT(Magesh): The protocol port should ideally come from the user.
    # For now, we are using the same port as VIP
    def _generate_pool_member_template(self, context,
                                       is_template_aws_version,
                                       pool_res_name, member_ip,
                                       stack_template):
        type_key = 'Type' if is_template_aws_version else 'type'
        properties_key = ('Properties' if is_template_aws_version
                          else 'properties')
        resources_key = 'Resources' if is_template_aws_version else 'resources'
        res_key = 'Ref' if is_template_aws_version else 'get_resource'

        lbaas_pool_key = self._get_heat_resource_key(
            stack_template[resources_key],
            is_template_aws_version,
            "OS::Neutron::Pool")
        protocol_port = stack_template[resources_key][lbaas_pool_key][
            properties_key]['vip']['protocol_port']

        return {type_key: "OS::Neutron::PoolMember",
                properties_key: {
                    "address": member_ip,
                    "admin_state_up": True,
                    "pool_id": {res_key: pool_res_name},
                    "protocol_port": protocol_port,
                    "weight": 1}}

    @log.log
    def update_firewall(self, context, cons_ptgs):
        heatclient = self._get_heat_client(context.plugin_context)
        sc_instance_id = None
        # sc_instances = context._sc_plugin.get_servicechain_instances(
        #     context._plugin_context, {'consumer_ptg_id': context.consumer[
        #         'id']})[0]
        # stacks = self._get_node_instance_stacks(
        #     context.plugin_session,context.current_node['id'], sc_instances[
        #         'id'])
        # if not stacks:
        stacks, sc_instances = self.get_firewall_stack_id(context)
        stack_id = stacks[0].stack_id
        sc_instance_id = sc_instances['id']

        self._wait_for_stack_operation_complete(heatclient, stack_id, 'update')
        heatclient.delete(stacks[0].stack_id)
        self._wait_for_stack_operation_complete(heatclient, stack_id,
                                                'delete')
        self._delete_node_instance_stack_in_db(
            context.plugin_session, context.current_node['id'],
            sc_instance_id)

        sc_node = context.current_node
        provider_ptg = context.provider
        stack_template = sc_node.get('config')
        stack_template = (jsonutils.loads(stack_template) if
                          stack_template.startswith('{') else
                          yaml.load(stack_template))
        provider_cidr = context.core_plugin.get_subnet(
            context._plugin_context, provider_ptg['subnets'][0])['cidr']

        new_consumer = context._gbp_plugin.get_policy_target_group(
            context.plugin_context, cons_ptgs[0])
        consumer_cidr = context.core_plugin.get_subnet(
            context._plugin_context, new_consumer['subnets'][0])['cidr']

        is_template_aws_version = stack_template.get(
                                        'AWSTemplateFormatVersion', False)

        resources_key = ('Resources' if is_template_aws_version
                         else 'resources')
        properties_key = ('Properties' if is_template_aws_version
                          else 'properties')
        insert_type = ('north_south' if context.is_consumer_external else
                       'east_west')

        service_info = self.svc_mgr.get_service_info_with_srvc_type(
            context=context.plugin_context,
            service_type=context.current_profile["service_type"],
            tenant_id=context.plugin_context.tenant_id,
            insert_type=insert_type)
        if service_info:
            floating_ip = service_info['floating_ip']
            provider_port_id = service_info['provider_port_id']
            provider_port_mac = context.core_plugin.get_port(
                n_context.get_admin_context(), provider_port_id)[
                'mac_address']

        stack_template = self._update_firewall_template(
            context, provider_ptg, provider_cidr, consumer_cidr,
            stack_template, is_template_aws_version)
        firewall_desc = {'vm_management_ip': floating_ip,
                         'provider_ptg_info': [provider_port_mac],
                         'insert_type': insert_type}
        fw_key = self._get_heat_resource_key(
                    stack_template[resources_key],
                    is_template_aws_version,
                    'OS::Neutron::Firewall')
        stack_template[resources_key][fw_key][properties_key][
                    'description'] = str(firewall_desc)

        new_cons_sc_instance = context._sc_plugin.get_servicechain_instances(
            context._plugin_context, {'consumer_ptg_id': [new_consumer[
                'id']]})[0]
        # REVISIT(VK) Can this be a issue?
        stack_name = ("stack_" + context.instance['name'] +
                      context.current_node['name'] +
                      new_cons_sc_instance['id'][:8] +
                      context.current_node['id'][:8])
        # Update template
        self.update_firewall_template(context, stack_template,
                                      ptg_to_not_configure=new_consumer['id'])
        stack = heatclient.create(stack_name, stack_template, {})
        self._wait_for_stack_operation_complete(
            heatclient, stack["stack"]["id"], "create")
        self._insert_node_instance_stack_in_db(
            context.plugin_session, context.current_node['id'],
            new_cons_sc_instance['id'], stack['stack']['id'])

    @log.log
    def get_firewall_stack_id(self, context, cons_ptgs=None):
        if not cons_ptgs:
            sc_instances = context._sc_plugin.get_servicechain_instances(
                context._plugin_context, {'provider_ptg_id': [context.provider[
                    'id']]})
        else:
            for cons_ptg in cons_ptgs:
                sc_instances = \
                    context._sc_plugin.get_servicechain_instances(
                        context._plugin_context,
                        {'consumer_ptg_id': [cons_ptg]})
                for sc_instance in sc_instances:
                    stacks = self._get_node_instance_stacks(
                        context.plugin_session, context.current_node['id'],
                        sc_instance['id'])
                    if stacks:
                        return stacks, sc_instance
            return None, None
        for sc_instance in sc_instances:
            stacks = self._get_node_instance_stacks(
                context.plugin_session, context.current_node['id'],
                sc_instance['id'])
            if stacks:
                return stacks, sc_instance

    @log.log
    def delete(self, context):
        _exist = None
        try:
            _exist, cons_ptgs, provider_unset = \
                    self.check_for_existing_service(context)
            service_type = context.current_profile["service_type"]
            if service_type in [pconst.FIREWALL, pconst.LOADBALANCER]:
                # if provider_unset:
                #     super(OneConvergenceServiceNodeDriver, self).delete(
                #         context)
                if _exist and service_type == pconst.LOADBALANCER:
                    super(OneConvergenceServiceNodeDriver, self).delete(
                        context)
                if (_exist and service_type == pconst.FIREWALL and
                      not context.is_consumer_external and not provider_unset):
                    self.update_firewall(context, cons_ptgs)
                else:
                    super(OneConvergenceServiceNodeDriver, self).delete(
                        context)
            # To handle VPN case, we need to delete stack and its DB entry.
            else:
                super(OneConvergenceServiceNodeDriver, self).delete(
                        context)
                self._delete_node_instance_stack_in_db(context.plugin_session,
                                               context.current_node['id'],
                                               context.instance['id'])
                LOG.info(_("Not deleting LOADBALANCER stack, stack is "
                           "in use by: %(group)s"),
                         {'group': context.provider['id']})
        except Exception:
            # Log the error and continue with VM delete in case if *aas
            # cleanup failure
            LOG.exception(_("Cleaning up the service chain stack failed"))

        service_type = context.current_profile['service_type']
        insert_type = ('north_south' if context.is_consumer_external else
                       'east_west')
        admin_context = n_context.get_admin_context()
        clean_provider_port = False
        # Allow VPN to go through.
        if not _exist or provider_unset or service_type == pconst.VPN:
            self.ts_driver.revert_stitching(
                        context, context.provider['subnets'][0])
            clean_provider_port = True
        ports_to_cleanup = self.svc_mgr.delete_service_instance(
                            context=context._plugin_context,
                            tenant_id=context._plugin_context.tenant_id,
                            insert_type=insert_type,
                            service_chain_instance_id=context.instance['id'],
                            service_type=service_type,
                            clean_provider_port=clean_provider_port)

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
            username=user, password=pw, domain_name="default",
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
        admin_id = v3client.users.find(name=keystone_conf.get('admin_user')).id
        admin_role = self.get_role_by_name(v3client, "admin")
        v3client.roles.grant(admin_role.id, user=admin_id,
                             project=project_id)
        heat_role = self.get_role_by_name(v3client, "heat_stack_owner")
        v3client.roles.grant(heat_role.id, user=admin_id, project=project_id)

    def get_admin_tenant_object(self):
        v3client = self.get_v3_keystone_admin_client()
        keystone_conf = cfg.CONF.keystone_authtoken
        admin_tenant = v3client.projects.find(
            name=keystone_conf.get('admin_tenant_name'))
        return admin_tenant

