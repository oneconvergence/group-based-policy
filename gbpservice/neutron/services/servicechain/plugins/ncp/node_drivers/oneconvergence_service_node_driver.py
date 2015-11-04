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
import time

from keystoneclient import exceptions as k_exceptions
from keystoneclient.v2_0 import client as keyclient
from keystoneclient.v3 import client as keyclientv3
from neutron.common import exceptions as n_exc
from neutron.common import log
from neutron import context as n_context
from neutron import manager
from neutron.openstack.common import log as logging
from neutron.plugins.common import constants as pconst
from oslo.config import cfg
from oslo.serialization import jsonutils
from oslo.utils import excutils
import yaml

from gbpservice.common import utils
from gbpservice.neutron.services.grouppolicy.common import constants as gconst
from gbpservice.neutron.services.servicechain.plugins.ncp import (
    exceptions as exc)
from gbpservice.neutron.services.servicechain.plugins.ncp.node_drivers import (
    heat_node_driver as heat_node_driver)
from gbpservice.neutron.services.servicechain.plugins.ncp.node_drivers import (
    openstack_heat_api_client as heat_api_client)
from gbpservice.neutron.services.servicechain.plugins.ncp.node_drivers.\
    oc_service_manager_client import SvcManagerClientApi
from gbpservice.neutron.services.servicechain.plugins.ncp import model
from gbpservice.neutron.services.servicechain.plugins.ncp import plumber_base


ONECONVERGENCE_DRIVER_OPTS = [
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
               default=120,
               help=_("Seconds to wait for pending stack operation "
                      "to complete")),
    cfg.BoolOpt('is_service_admin_owned',
               help=_("Parameter to indicate whether the Service VM has to be "
                      "owned by the Admin"),
               default=False),
]

cfg.CONF.register_opts(ONECONVERGENCE_DRIVER_OPTS,
                       "oneconvergence_node_driver")

SC_METADATA = ('{"sc_instance":"%s", "floating_ip": "%s", '
               '"provider_interface_mac": "%s", '
               '"standby_floating_ip": "%s"}')
SVC_MGMT_PTG_NAME = (
    cfg.CONF.oneconvergence_node_driver.svc_management_ptg_name)

POOL_MEMBER_PARAMETER_AWS = {"Description": "Pool Member IP Address",
                             "Type": "String"}
POOL_MEMBER_PARAMETER = {"description": "Pool Member IP Address",
                         "type": "string"}

STACK_ACTION_WAIT_TIME = (
    cfg.CONF.oneconvergence_node_driver.stack_action_wait_time)
STACK_ACTION_RETRY_WAIT = 5  # Retry after every 5 seconds
APIC_OWNED_RES = 'apic_owned_res_'

LOG = logging.getLogger(__name__)


class InvalidServiceType(exc.NodeCompositionPluginBadRequest):
    message = _("The OneConvergence Node driver only supports the services "
                "VPN, Firewall and LB in a Service Chain")


class DuplicateServiceTypeInChain(exc.NodeCompositionPluginBadRequest):
    message = _("The OneConvergence Node driver does not support duplicate "
                "service types in same chain")


class RequiredProfileAttributesNotSet(exc.NodeCompositionPluginBadRequest):
    message = _("The required attributes in service profile are not present")


class InvalidNodeOrderInChain(exc.NodeCompositionPluginBadRequest):
    message = _("The OneConvergence Node driver does not support the order "
                "of nodes defined in the current service chain spec")


class UnSupportedServiceProfile(exc.NodeCompositionPluginBadRequest):
    message = _("The OneConvergence Node driver does not support this service "
                "profile with service type %(service_type)s and vendor "
                "%(vendor)s")


class UnSupportedInsertionMode(exc.NodeCompositionPluginBadRequest):
    message = _("The OneConvergence Node driver supports only L3 Insertion "
                "mode")


class ServiceInfoNotAvailableOnUpdate(n_exc.NeutronException):
    message = _("Service information is not available with Service Manager "
                "on node update")


class StackCreateFailedException(n_exc.NeutronException):
    message = _("Stack : %(stack_name)s creation failed for tenant : "
                "%(stack_owner)s ")


class RequiredRoleNotCreated(n_exc.NeutronException):
    message = _("The role : %(role_name)s is not available in keystone")


class FloatingIPCreationFailedForVPN(n_exc.NeutronException):
    message = _("Allocating a Floating IP for VPN Service Failed")


class L3PolicyNotAssociatedWithES(n_exc.NeutronException):
    message = _("The L3Policy on Provider Group is not associated with an "
                "External Segment")


class FloatingIPForVPNRemovedManually(n_exc.NeutronException):
    message = _("Floating IP for VPN Service has been disassociated Manually")


class VipNspNotSetonProvider(n_exc.NeutronException):
    message = _("Network Service policy for VIP IP address is not configured "
                "on the Providing Group")


class OneConvergenceServiceNodeDriver(heat_node_driver.HeatNodeDriver):
    FIREWALL_HA = pconst.FIREWALL + "_HA"
    VPN_HA = pconst.VPN + "_HA"
    SUPPORTED_SERVICE_TYPES = [pconst.LOADBALANCER, pconst.FIREWALL, pconst.VPN,
                               #FIREWALL_HA, VPN_HA
                               ]
    SUPPORTED_SERVICE_VENDOR_MAPPING = {pconst.LOADBALANCER: ["haproxy"],
                                        pconst.FIREWALL: ["vyos", "asav", "vyos"],
                                        pconst.VPN: ["vyos", "asav"],
                                        #FIREWALL_HA: ["asav"],
                                        #VPN_HA: ["vyos", "asav"]
                                        }
    vendor_name = 'oneconvergence'
    required_heat_resources = {
        pconst.LOADBALANCER: ['OS::Neutron::LoadBalancer',
                              'OS::Neutron::Pool'],
        pconst.FIREWALL: ['OS::Neutron::Firewall',
                          'OS::Neutron::FirewallPolicy'],
        pconst.VPN: ['OS::Neutron::VPNService'],
        FIREWALL_HA: ['OS::Neutron::Firewall',
                      'OS::Neutron::FirewallPolicy'],
        VPN_HA: ['OS::Neutron::VPNService']
        }
    initialized = False

    def __init__(self):
        super(OneConvergenceServiceNodeDriver, self).__init__()
        self.svc_mgr = SvcManagerClientApi(cfg.CONF.host)
        self._lbaas_plugin = None

    @log.log
    def initialize(self, name):
        self.initialized = True
        self._name = name
        if cfg.CONF.oneconvergence_node_driver.is_service_admin_owned:
            self.resource_owner_tenant_id = self._resource_owner_tenant_id()
        else:
            self.resource_owner_tenant_id = None

    @log.log
    def get_plumbing_info(self, context):
        context._plugin_context = self._get_resource_owner_context(
            context._plugin_context)
        service_type = self._get_service_type(context.current_profile)
        service_vendor, ha_enabled = self._get_vendor_ha_enabled(
            context.current_profile)
        if ha_enabled:
            plumber_pt_request = {'management': [],
                                  'provider': [{}, {}, {}, {}],
                                  'consumer': [{}, {}, {}, {}]}
        else:
            plumber_pt_request = {'management': [], 'provider': [{}],
                                  'consumer': [{}]}
        if service_type in [pconst.FIREWALL, pconst.VPN]:
            # plumber will return stitching network PT instead of consumer
            # as chain is instantiated while creating provider group.
            if (self._check_for_fw_vpn_sharing(context, service_type) and
                service_type == pconst.VPN):
                LOG.info(_("Not requesting plumber for PTs for service type "
                           "%s") %(service_type))
                return False
            plumber_pt_request['plumbing_type'] = 'gateway'
        else:  # Loadbalancer
            plumber_pt_request['consumer'] = []
            plumber_pt_request['plumbing_type'] = 'endpoint'

        LOG.info(_("Requesting plumber for %s PTs for service type "
                   "%s") %(plumber_pt_request, service_type))
        return plumber_pt_request

    # FIXME(Magesh): Raise an error somehow if for same chain, FW is HA
    # while VPN is not
    @log.log
    def validate_create(self, context):
        # Heat Node driver in Juno supports non service-profile based model
        if not context.current_profile:
            raise heat_node_driver.ServiceProfileRequired()
        if (not context.current_profile['vendor'] or not
            context.current_profile['insertion_mode'] or not
            context.current_profile['service_type'] or not
            context.current_profile['service_flavor']):
            raise RequiredProfileAttributesNotSet()
        if context.current_profile['vendor'] != self.vendor_name:
            raise heat_node_driver.NodeVendorMismatch(vendor=self.vendor_name)
        if context.current_profile['insertion_mode'].lower() != "l3":
            raise UnSupportedInsertionMode()
        if context.current_profile['service_type'] not in self.SUPPORTED_SERVICE_TYPES:
            raise InvalidServiceType()
        if (context.current_profile['service_flavor'].lower() not in
            self.SUPPORTED_SERVICE_VENDOR_MAPPING[
                context.current_profile['service_type']]):
            raise UnSupportedServiceProfile(
                service_type=context.current_profile['service_type'],
                vendor=context.current_profile['vendor'])
        self._is_node_order_in_spec_supported(context)

    @log.log
    def validate_update(self, context):
        # Heat Node driver in Juno supports non service-profile based model
        if not context.original_node:  # PT create/delete notifications
            return
        if context.current_node and not context.current_profile:
            raise heat_node_driver.ServiceProfileRequired()
        if context.current_profile['vendor'] != self.vendor_name:
            raise heat_node_driver.NodeVendorMismatch(vendor=self.vendor_name)
        if context.current_profile['insertion_mode'].lower() != "l3":
            raise UnSupportedInsertionMode()
        if context.current_profile['service_type'] not in self.SUPPORTED_SERVICE_TYPES:
            raise InvalidServiceType()
        if (context.current_profile['service_flavor'].lower() not in
            self.SUPPORTED_SERVICE_VENDOR_MAPPING[
                context.current_profile['service_type']]):
            raise UnSupportedServiceProfile(
                service_type=context.current_profile['service_type'],
                vendor=context.current_profile['vendor'])

    @log.log
    def update_policy_target_added(self, context, policy_target):
        if self._get_service_type(context.current_profile) == pconst.LOADBALANCER:
            context._plugin_context = self._get_resource_owner_context(
                context._plugin_context)
            self._update(context, pt_added_or_removed=True)

    @log.log
    def update_policy_target_removed(self, context, policy_target):
        if self._get_service_type(context.current_profile) == pconst.LOADBALANCER:
            context._plugin_context = self._get_resource_owner_context(
                context._plugin_context)
            try:
                self._update(context, pt_added_or_removed=True)
            except Exception:
                LOG.exception(_("Processing policy target delete failed"))

    @log.log
    def notify_chain_parameters_updated(self, context):
        pass  # We are not using the classifier specified in redirect Rule

    @log.log
    def update_node_consumer_ptg_added(self, context, policy_target_group):
        if self._get_service_type(context.current_profile) == pconst.FIREWALL:
            context._plugin_context = self._get_resource_owner_context(
                context._plugin_context)
            self._update(context)

    @log.log
    def update_node_consumer_ptg_removed(self, context, policy_target_group):
        if self._get_service_type(context.current_profile) == pconst.FIREWALL:
            context._plugin_context = self._get_resource_owner_context(
                context._plugin_context)
            self._update(context)

    @log.log
    def create(self, context):
        context._plugin_context = self._get_resource_owner_context(
            context._plugin_context)
        provider_tenant_id = context.provider['tenant_id']
        heatclient = self._get_heat_client(context.plugin_context,
                                           tenant_id=provider_tenant_id)
        stack_name = ("stack_" + context.instance['name'] +
                      context.current_node['name'] +
                      context.instance['id'][:8] +
                      context.current_node['id'][:8])
        # Heat does not accept space in stack name
        stack_name = stack_name.replace(" ", "")
        mgmt_fips = self._instantiate_servicevm(context)
        # Raise error, if we do not have the proper fips
        stack_template, stack_params = self._update_node_config(
            context, mgmt_fips=mgmt_fips)

        stack = heatclient.create(stack_name, stack_template, stack_params)
        stack_id = stack['stack']['id']
        self._insert_node_instance_stack_in_db(
            context.plugin_session, context.current_node['id'],
            context.instance['id'], stack_id)
        self._wait_for_stack_operation_complete(heatclient, stack_id, "create")
        if self._get_service_type(context.current_profile) == pconst.LOADBALANCER:
            self._create_policy_target_for_vip(context)

    @log.log
    def update(self, context):
        context._plugin_context = self._get_resource_owner_context(
            context._plugin_context)
        self._update(context)

    @log.log
    def delete(self, context):
        context._plugin_context = self._get_resource_owner_context(
            context._plugin_context)
        _, ha_enabled = self._get_vendor_ha_enabled(
            context.current_profile)
        if ha_enabled:
            try:
                service_targets = self._get_service_targets(context)
                self._clear_service_target_cluster(context, service_targets)
            except Exception:
                LOG.exception(_("Clearing Policy Target cluster information "
                                "failed"))
        provider_tenant_id = context.provider['tenant_id']
        try:
            stack_ids = self._get_node_instance_stacks(
                context.plugin_session, context.current_node['id'],
                context.instance['id'])
            heatclient = self._get_heat_client(context.plugin_context,
                                               tenant_id=provider_tenant_id)
            for stack in stack_ids:
                heatclient.delete(stack.stack_id)
            for stack in stack_ids:
                self._wait_for_stack_operation_complete(
                    heatclient, stack.stack_id, 'delete')
            self._delete_node_instance_stack_in_db(context.plugin_session,
                                                   context.current_node['id'],
                                                   context.instance['id'])
        except Exception:
            # Log the error and continue with VM delete in case of *aas
            # cleanup failure
            LOG.exception(_("Cleaning up the service chain stack failed"))

        try:
            self.svc_mgr.delete_service(
                context=context.plugin_context,
                tenant_id=provider_tenant_id,
                service_chain_instance_id=context.instance['id'],
                service_node_id=context.current_node['id'])
        except Exception:
            LOG.exception(_("Delete service in One Convergence Service "
                            "controller Failed"))

    @property
    def lbaas_plugin(self):
        if self._lbaas_plugin:
            return self._lbaas_plugin
        self._lbaas_plugin = manager.NeutronManager.get_service_plugins().get(
            pconst.LOADBALANCER)
        return self._lbaas_plugin

    def _get_service_type(self, profile):
        if profile['service_type'].endswith('_HA'):
            service_type = profile['service_type'][:-3]
        else:
            service_type = profile['service_type']
        return service_type

    def _get_vendor_ha_enabled(self, service_profile):
        if "_HA" in service_profile['service_type']:
            ha_enabled = True
        else:
            ha_enabled = False
        return service_profile['service_flavor'], ha_enabled

    def _resource_owner_tenant_id(self):
        user, pwd, tenant, auth_url = utils.get_keystone_creds()
        keystoneclient = keyclient.Client(username=user, password=pwd,
                                          auth_url=auth_url)
        try:
            tenant = keystoneclient.tenants.find(name=tenant)
            return tenant.id
        except k_exceptions.NotFound:
            with excutils.save_and_reraise_exception(reraise=True):
                LOG.error(_('No tenant with name %s exists.'), tenant)
        except k_exceptions.NoUniqueMatch:
            with excutils.save_and_reraise_exception(reraise=True):
                LOG.error(_('Multiple tenants matches found for %s'), tenant)

    def _get_resource_owner_context(self, plugin_context):
        if cfg.CONF.oneconvergence_node_driver.is_service_admin_owned:
            resource_owner_context = plugin_context.elevated()
            resource_owner_context.tenant_id = self.resource_owner_tenant_id
            user, pwd, _, auth_url = utils.get_keystone_creds()
            keystoneclient = keyclient.Client(username=user, password=pwd,
                                              auth_url=auth_url)
            resource_owner_context.auth_token = keystoneclient.get_token(
                self.resource_owner_tenant_id)
            return resource_owner_context
        else:
            return plugin_context

    def _create_pt(self, context, ptg_id, name, port_id=None):
        policy_target = {'name': name,
                         'description': '',
                         'tenant_id': context.plugin_context.tenant_id,
                         'policy_target_group_id': ptg_id,
                         'port_id': port_id,
                         'proxy_gateway': False,
                         'group_default_gateway': False,
			 'cluster_id': ""}
        return context.gbp_plugin.create_policy_target(
            context.plugin_context, {"policy_target": policy_target})

    def _create_policy_target_for_vip(self, context):
        provider_subnet = None
        provider_l2p_subnets = context.core_plugin.get_subnets(
            context.plugin_context,
            filters={'id': context.provider['subnets']})
        for subnet in provider_l2p_subnets:
            if not subnet['name'].startswith(APIC_OWNED_RES):
                provider_subnet = subnet
                break
        if provider_subnet:
            lb_pool_ids = self.lbaas_plugin.get_pools(
                context.plugin_context,
                filters={'subnet_id': [provider_subnet['id']]})
            if lb_pool_ids and lb_pool_ids[0]['vip_id']:
                lb_vip =  self.lbaas_plugin.get_vip(
                    context.plugin_context, lb_pool_ids[0]['vip_id'])
                self._create_pt(context, context.provider['id'], "vip_pt",
                                port_id=lb_vip['port_id'])

    def _update(self, context, pt_added_or_removed=False):
        # If it is not a Node config update or PT change for LB, no op
        # FIXME(Magesh): Why are we invoking heat update for FW and VPN
        # in Phase 1 even when there was no config change ??
        service_type = self._get_service_type(context.current_profile)
        if service_type == pconst.LOADBALANCER:
            if (not pt_added_or_removed and (
                not context.original_node or
                context.original_node == context.current_node)):
                LOG.info(_("No action to take on update"))
                return
        provider_tenant_id = context.provider['tenant_id']
        heatclient = self._get_heat_client(context.plugin_context,
                                           tenant_id=provider_tenant_id)

        mgmt_fips = self.svc_mgr.get_management_ips(
            context=context.plugin_context,
            tenant_id=provider_tenant_id,
            service_chain_instance_id=context.instance['id'],
            service_node_id=context.current_node['id'])
        if not mgmt_fips:
            raise ServiceInfoNotAvailableOnUpdate()

        stack_template, stack_params = self._update_node_config(
            context, update=True, mgmt_fips=mgmt_fips)
        stack_ids = self._get_node_instance_stacks(context.plugin_session,
                                                   context.current_node['id'],
                                                   context.instance['id'])
        for stack in stack_ids:
            # FIXME(Magesh): Fix the update stack issue on Heat/*aas driver
            self._wait_for_stack_operation_complete(
                heatclient, stack.stack_id, 'update')  # or create !!
            if service_type == pconst.VPN or service_type == pconst.FIREWALL:
                heatclient.delete(stack.stack_id)
                self._wait_for_stack_operation_complete(heatclient,
                                                        stack.stack_id,
                                                        'delete')
                self._delete_node_instance_stack_in_db(
                    context.plugin_session, context.current_node['id'],
                    context.instance['id'])
                stack_name = ("stack_" + context.instance['name'] +
                              context.current_node['name'] +
                              context.instance['id'][:8] +
                              context.current_node['id'][:8])
                stack = heatclient.create(stack_name, stack_template,
                                          stack_params)
                self._wait_for_stack_operation_complete(
                    heatclient, stack["stack"]["id"], "create")
                self._insert_node_instance_stack_in_db(
                    context.plugin_session, context.current_node['id'],
                    context.instance['id'], stack['stack']['id'])
            else:
                heatclient.update(stack.stack_id, stack_template, stack_params)
                self._wait_for_stack_operation_complete(
                    heatclient, stack.stack_id, 'update')

    def _get_management_ptg_id(self, context):
        # REVISIT(Magesh): Retrieving management PTG by name will not be
        # required when the service_ptg patch is merged
        filters = {'name': [SVC_MGMT_PTG_NAME]}
        svc_mgmt_ptgs = context.gbp_plugin.get_policy_target_groups(
            context.plugin_context, filters)
        if not svc_mgmt_ptgs:
            LOG.error(_("Service Management Group is not created by Admin"))
            raise Exception()
        else:
            return svc_mgmt_ptgs[0]['id']

    def _get_service_target_from_relations(self, context, relationship):
        LOG.debug("Relation: %s instance_id: %s node_id: %s tenant_id: %s"
                 %(relationship, context.instance['id'],
                   context.current_node['id'],
                   context._plugin_context.tenant_id))
        service_targets = model.get_service_targets(
            context.session,
            servicechain_instance_id=context.instance['id'],
            servicechain_node_id=context.current_node['id'],
            relationship=relationship)
        service_type = self._get_service_type(context.current_profile)
        shared_service_type = {pconst.FIREWALL: pconst.VPN,
                               pconst.VPN: pconst.FIREWALL}
        if (not service_targets and service_type in
            [pconst.FIREWALL, pconst.VPN]):
                shared_service_type = shared_service_type[service_type]
                service_targets = self._get_shared_service_targets(
                    context, shared_service_type, relationship)
        LOG.debug("service_type %s service_targets: %s" %(service_type, service_targets))
        return service_targets

    def _get_service_targets(self, context):
        service_type = self._get_service_type(context.current_profile)
        service_vendor, is_ha_enabled = self._get_vendor_ha_enabled(
            context.current_profile)
        provider_service_targets = self._get_service_target_from_relations(
            context, 'provider')
        consumer_service_targets = self._get_service_target_from_relations(
            context, 'consumer')
        LOG.debug("provider targets: %s consumer targets %s" % (
            provider_service_targets, consumer_service_targets))
        if (not provider_service_targets or (service_type in
            [pconst.FIREWALL, pconst.VPN] and not consumer_service_targets)):
                LOG.error(_("Service Targets are not created for the Node "
                            "of service_type %(service_type)s"),
                          {'service_type': service_type})
                raise Exception("Service Targets are not created for the Node")

        if is_ha_enabled:
            if len(provider_service_targets) != 4:
                LOG.error(_("Service Targets are not created for the Node"))
                raise Exception("Service Targets are not created for the Node")
            if (service_type in [pconst.FIREWALL, pconst.VPN] and
                len(consumer_service_targets) != 4):
                LOG.error(_("Service Targets are not created for the Node"))
                raise Exception("Service Targets are not created for the Node")

        service_target_info = {'provider_ports': [], 'provider_pts': [],
                               'consumer_ports': [], 'consumer_pts': []}
        for service_target in provider_service_targets:
            policy_target = context.gbp_plugin.get_policy_target(
                context.plugin_context, service_target.policy_target_id)
            port = context.core_plugin.get_port(
                context.plugin_context, policy_target['port_id'])
            if policy_target['group_default_gateway'] is True and is_ha_enabled:
                service_target_info['provider_vip_port'] = port
                service_target_info['provider_vip_pt'] = policy_target['id']
            else:
                service_target_info['provider_ports'].append(port)
                service_target_info['provider_pts'].append(policy_target['id'])

        ha_port_processed = False
        for service_target in consumer_service_targets:
            policy_target = context.gbp_plugin.get_policy_target(
                context.plugin_context, service_target.policy_target_id)
            port = context.core_plugin.get_port(
                context.plugin_context, policy_target['port_id'])
            if is_ha_enabled and not ha_port_processed:
                ha_port_processed = True
                service_target_info['consumer_vip_port'] = port
                service_target_info['consumer_vip_pt'] = policy_target['id']
            else:
                service_target_info['consumer_ports'].append(port)
                service_target_info['consumer_pts'].append(policy_target['id'])

        return service_target_info

    def _get_shared_service_targets(self, context, service_type, relationship):
        current_specs = context.relevant_specs
        for spec in current_specs:
            filters = {'id': spec['nodes']}
            nodes = context.sc_plugin.get_servicechain_nodes(
                context.plugin_context, filters)
            for node in nodes:
                profile = context.sc_plugin.get_service_profile(
                    context.plugin_context, node['service_profile_id'])
                if self._get_service_type(profile) == service_type:
                    service_targets = model.get_service_targets(
                        context.session,
                        servicechain_instance_id=context.instance['id'],
                        servicechain_node_id=node['id'],
                        relationship=relationship)
                    return service_targets

    def _check_for_fw_vpn_sharing(self, context, service_type):
        shared_svc_type = pconst.FIREWALL
        if service_type == pconst.FIREWALL:
            shared_svc_type = pconst.VPN
        return self._is_service_type_in_chain(context, shared_svc_type)

    # Needs a better algorithm
    def _is_node_order_in_spec_supported(self, context):
        current_specs = context.relevant_specs
        service_type_list_in_chain = []
        node_list = []
        for spec in current_specs:
            node_list.extend(spec['nodes'])

        for node_id in node_list:
            node_info = context.sc_plugin.get_servicechain_node(
                context.plugin_context, node_id)
            profile = context.sc_plugin.get_service_profile(
                context.plugin_context, node_info['service_profile_id'])
            service_type = self._get_service_type(profile)
            service_type_list_in_chain.append(service_type)

        if len(service_type_list_in_chain) != len(
            set(service_type_list_in_chain)):
            raise DuplicateServiceTypeInChain()

        allowed_chain_combinations = [
            [pconst.VPN],
            [pconst.VPN, pconst.FIREWALL],
            [pconst.VPN, pconst.FIREWALL, pconst.LOADBALANCER],
            [pconst.FIREWALL],
            [pconst.FIREWALL, pconst.LOADBALANCER],
            [pconst.LOADBALANCER]]
        if service_type_list_in_chain not in allowed_chain_combinations:
            raise InvalidNodeOrderInChain()

    def _is_service_type_in_chain(self, context, service_type):
        if service_type == self._get_service_type(context.current_profile):
            return True
        else:
            current_specs = context.relevant_specs
            service_profiles = []
            for spec in current_specs:
                filters = {'id': spec['nodes']}
                nodes = context.sc_plugin.get_servicechain_nodes(
                    context.plugin_context, filters)
                for node in nodes:
                    service_profiles.append(node['service_profile_id'])
            service_type_ha = "%s%s" %(service_type, "_HA")
            filters = {'id': service_profiles,
                       'service_type': [service_type, service_type_ha]}
            service_profiles = context.sc_plugin.get_service_profiles(
                context.plugin_context, filters)
            return True if service_profiles else False

    def _get_consumers_for_chain(self, context):
        filters = {'id': context.provider['provided_policy_rule_sets']}
        provided_prs = context.gbp_plugin.get_policy_rule_sets(
            context.plugin_context, filters=filters)
        redirect_prs = None
        for prs in provided_prs:
            filters = {'id': prs['policy_rules']}
            policy_rules = context.gbp_plugin.get_policy_rules(
                context.plugin_context, filters=filters)
            for policy_rule in policy_rules:
                filters = {'id': policy_rule['policy_actions'],
                           'action_type': [gconst.GP_ACTION_REDIRECT]}
                policy_actions = context.gbp_plugin.get_policy_actions(
                    context.plugin_context, filters=filters)
                if policy_actions:
                    redirect_prs = prs
                    break

        if not redirect_prs:
            raise
        return (redirect_prs['consuming_policy_target_groups'],
                redirect_prs['consuming_external_policies'])

    def _append_firewall_rule(self, stack_template, provider_cidr,
                              consumer_cidr, fw_template_properties,
                              consumer_id):
        resources_key = fw_template_properties['resources_key']
        properties_key = fw_template_properties['properties_key']
        fw_rule_keys = fw_template_properties['fw_rule_keys']
        rule_name = "%s_%s" % ("node_driver_rule", consumer_id[:16])
        fw_policy_key = fw_template_properties['fw_policy_key']
        i = 1
        for fw_rule_key in fw_rule_keys:
            fw_rule_name = (rule_name + '_' + str(i))
            stack_template[resources_key][fw_rule_name] = (
                copy.deepcopy(stack_template[resources_key][fw_rule_key]))
            stack_template[resources_key][fw_rule_name][
                properties_key]['destination_ip_address'] = provider_cidr
            # Use user provided Source for N-S
            if consumer_cidr != "0.0.0.0/0":
                stack_template[resources_key][fw_rule_name][
                    properties_key]['source_ip_address'] = consumer_cidr

            if stack_template[resources_key][fw_policy_key][
                properties_key].get('firewall_rules'):
                stack_template[resources_key][fw_policy_key][
                    properties_key]['firewall_rules'].append({
                        'get_resource': fw_rule_name})
            i += 1

    def _update_firewall_template(self, context, stack_template):
        consumer_ptgs, consumer_eps = self._get_consumers_for_chain(context)
        provider_cidr = None
        filters = {'id': consumer_ptgs}
        consumer_ptgs_details = context.gbp_plugin.get_policy_target_groups(
            context.plugin_context, filters)
        provider_l2p_subnets = context.core_plugin.get_subnets(
            context.plugin_context, filters = {'id': context.provider['subnets']})
        for subnet in provider_l2p_subnets:
            if not subnet['name'].startswith(APIC_OWNED_RES):
                provider_cidr = subnet['cidr']
                break
        if not provider_cidr:
            raise #TODO(Magesh): Raise proper exception class

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

        # Revisit(Magesh): What is the name updated below ?? FW or Rule?
        # This seems to have no effect in UTs
        for consumer in consumer_ptgs_details:
            fw_template_properties.update({'name': consumer['id'][:3]})
            consumer_cidr = context.core_plugin.get_subnet(
                context.plugin_context, consumer['subnets'][0])['cidr']
            self._append_firewall_rule(stack_template, provider_cidr,
                                       consumer_cidr, fw_template_properties,
                                       consumer['id'])

        filters = {'id': consumer_eps}
        consumer_eps_details = context.gbp_plugin.get_external_policies(
            context.plugin_context, filters)
        for consumer_ep in consumer_eps_details:
            fw_template_properties.update({'name': consumer_ep['id'][:3]})
            self._append_firewall_rule(stack_template, provider_cidr,
                                       "0.0.0.0/0", fw_template_properties,
                                       consumer_ep['id'])

        for rule_key in fw_rule_keys:
            del stack_template[resources_key][rule_key]
            stack_template[resources_key][fw_policy_key][
                properties_key]['firewall_rules'].remove(
                    {'get_resource': rule_key})

        return stack_template

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
                elif stack.stack_status not in [
                    'UPDATE_IN_PROGRESS', 'CREATE_IN_PROGRESS',
                    'DELETE_IN_PROGRESS']:
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
                    # Pending state
                    if action == 'delete':
                        heatclient.delete(stack_id)
                    return

    def _clear_service_target_cluster(self, context, service_targets):
        for pt_id in service_targets['provider_pts']:
            updated_pt = {'cluster_id': ""}
            context.gbp_plugin.update_policy_target(
                context.plugin_context, pt_id,
                {'policy_target': updated_pt})
        for pt_id in service_targets['consumer_pts']:
            updated_pt = {'cluster_id': ""}
            context.gbp_plugin.update_policy_target(
                context.plugin_context, pt_id,
                {'policy_target': updated_pt})

    def _set_cluster_in_pts(self, context, service_targets):
        # Setting Allowed address pairs should ideally happen in RMD
        # This is really confusing, but Allowed address pairs has to allow
        # traffic from the VIP port IP and Mac, in ASAv case both active and
        # standby VMs will have IP and Mac assigned from VIP port which is not
        # the one mapped to the dummy port for hotplug workaround. The mapped
        # port should have allowed address pairs allowing traffic from the
        # active and standby VIP ports.
        # This code is not tested. May need changes
        standby_provider_vip_pairs = []
        standby_consumer_vip_pairs = []
        standby_provider_vip_port = service_targets['provider_ports'][2]
        standby_consumer_vip_port = service_targets['consumer_ports'][2]
        standby_provider_vip_mac = standby_provider_vip_port['mac_address']
        standby_provider_vip_ips = [x['ip_address'] for x in
                                    standby_provider_vip_port['fixed_ips']]
        standby_provider_vip_pairs += [
            {'mac_address': standby_provider_vip_mac,
             'ip_address': x} for x in standby_provider_vip_ips]

        standby_consumer_vip_mac = standby_consumer_vip_port['mac_address']
        standby_consumer_vip_ips = [x['ip_address'] for x in
                                    standby_consumer_vip_port['fixed_ips']]
        standby_consumer_vip_pairs += [
            {'mac_address': standby_consumer_vip_mac,
             'ip_address': x} for x in standby_consumer_vip_ips]
        for port in [service_targets['consumer_ports'][0],
                     service_targets['consumer_ports'][1]]:
            port['allowed_address_pairs'] = standby_consumer_vip_pairs
            context.core_plugin.update_port(
                context.plugin_context, port['id'], {'port': port})
        for port in [service_targets['provider_ports'][0],
                     service_targets['provider_ports'][1]]:
            port['allowed_address_pairs'] = standby_provider_vip_pairs
            context.core_plugin.update_port(
                context.plugin_context, port['id'], {'port': port})

        for pt_id in service_targets['provider_pts']:
            updated_pt = {'cluster_id': service_targets['provider_vip_pt']}
            context.gbp_plugin.update_policy_target(
                context.plugin_context, pt_id,
                {'policy_target': updated_pt})
        for pt_id in service_targets['consumer_pts']:
            updated_pt = {'cluster_id': service_targets['consumer_vip_pt']}
            context.gbp_plugin.update_policy_target(
                context.plugin_context, pt_id,
                {'policy_target': updated_pt})

    def _instantiate_servicevm(self, context):
        service_type = self._get_service_type(context.current_profile)
        sc_instance = context.instance
        service_targets = self._get_service_targets(context)
        if service_type == pconst.LOADBALANCER:
            config_param_values = sc_instance.get('config_param_values', {})
            if config_param_values:
                config_param_values = jsonutils.loads(config_param_values)
            vip_ip = config_param_values.get('vip_ip')
            if not vip_ip:
                raise VipNspNotSetonProvider()

            for provider_port in service_targets['provider_ports']:
                provider_port['allowed_address_pairs'] = [
                    {'ip_address': vip_ip}]
                port = {}
                port['port'] = provider_port
                context.core_plugin.update_port(
                    context.plugin_context, provider_port['id'], port)

        service_vendor, ha_enabled = self._get_vendor_ha_enabled(
            context.current_profile)
        if ha_enabled:
            self._set_cluster_in_pts(context, service_targets)
        provider_l2p_subnets = context.core_plugin.get_subnets(
            context.plugin_context, filters={'id': context.provider['subnets']})
        provider_cidr = None
        for subnet in provider_l2p_subnets:
            if not subnet['name'].startswith(APIC_OWNED_RES):
                provider_cidr = subnet['cidr']
                break
        if not provider_cidr:
            raise # Raise proper exception object

        service_create_req = {
            "tenant_id": context.provider['tenant_id'],
            "service_chain_instance_id": sc_instance['id'],
            "service_node_id": context.current_node['id'],
            "order_in_chain": context.current_position,
            "service_type": service_type,
            "service_vendor": service_vendor,
            "ha_enabled": ha_enabled,
            "management_ptg_id": self._get_management_ptg_id(context),
            'provider_cidr': provider_cidr,
            'is_vpn_in_chain': self._is_service_type_in_chain(
                context, pconst.VPN),
        }

        active_service_ports = {}
        standby_service_ports = {}
        active_service_ports['provider_port_id'] = service_targets[
            'provider_ports'][0]['id']
        if service_targets.get('consumer_ports'):
            active_service_ports['stitching_port_id'] = service_targets[
                'consumer_ports'][0]['id']
            if not ha_enabled:
                service_create_req['stitching_port_ip'] = service_targets[
                    'consumer_ports'][0]['fixed_ips'][0]['ip_address']
                stitching_subnet = context.core_plugin.get_subnet(
                    context.plugin_context, service_targets[
                    'consumer_ports'][0]['fixed_ips'][0]['subnet_id'])
                service_create_req['stitching_gateway_ip'] = stitching_subnet['gateway_ip']
        service_create_req['active_service'] = active_service_ports
        if ha_enabled:
            service_create_req['provider_vip_port_id'] = service_targets[
                'provider_vip_port']['id']
            standby_service_ports['provider_port_id'] = service_targets[
                'provider_ports'][1]['id']
            service_create_req['standby_provider_vip_port_id'] = service_targets[
                'provider_ports'][2]['id']
            if service_targets.get('consumer_vip_port'):
                service_create_req['stitching_vip_port_id'] = service_targets[
                    'consumer_vip_port']['id']
                service_create_req['stitching_port_ip'] = service_targets[
                    'consumer_vip_port']['fixed_ips'][0]['ip_address']
                stitching_subnet = context.core_plugin.get_subnet(
                    context.plugin_context, service_targets[
                    'consumer_vip_port']['fixed_ips'][0]['subnet_id'])
                service_create_req['stitching_gateway_ip'] = stitching_subnet['gateway_ip']
                standby_service_ports['stitching_port_id'] = service_targets[
                    'consumer_ports'][1]['id']
                service_create_req['standby_stitching_vip_port_id'] = service_targets[
                    'consumer_ports'][2]['id']
            service_create_req['standby_service'] = standby_service_ports

        mgmt_fips = self.svc_mgr.create_service(
            context=context.plugin_context, service_info=service_create_req)
        return mgmt_fips

    # REVISIT(Magesh): Is this required ?? In a proper deployment, the
    # L3 IP Pool configured is not supposed to conflict with this VPN cidr.
    # Also what happens when GBP supports overlapping L3 pools ?? Why cant
    # this just be a configuration parameter
    def _get_rvpn_l3_policy(self, context, node_update):
        # For remote vpn - we need to create a implicit l3 policy
        # for client pool cidr, to avoid this cidr being reused.
        # Check for this tenant if this l3 policy is defined.
        # 1) If yes, get the cidr
        # 2) Else Create one for this tenant with the user provided cidr
        rvpn_l3policy_filter = {
            'tenant_id': [context.provider['tenant_id']],
            'name': ["remote-vpn-client-pool-cidr-l3policy"]}
        rvpn_l3_policy = context.gbp_plugin.get_l3_policies(
            context.plugin_context,
            rvpn_l3policy_filter)

        if node_update and not rvpn_l3_policy:
            raise

        if not rvpn_l3_policy:
            remote_vpn_client_pool_cidr = (
                cfg.CONF.oneconvergence_node_driver.
                remote_vpn_client_pool_cidr)
            rvpn_l3_policy = {
                'l3_policy': {
                    'name': "remote-vpn-client-pool-cidr-l3policy",
                    'description': ("L3 Policy for remote vpn "
                                    "client pool cidr"),
                    'ip_pool': remote_vpn_client_pool_cidr,
                    'ip_version': 4,
                    'subnet_prefix_length': 24,
                    'proxy_ip_pool': remote_vpn_client_pool_cidr,
                    'proxy_subnet_prefix_length': 24,
                    'external_segments': {},
                    'tenant_id': context.provider['tenant_id']}}
            rvpn_l3_policy = context.gbp_plugin.create_l3_policy(
                context.plugin_context, rvpn_l3_policy)
        else:
            rvpn_l3_policy = rvpn_l3_policy[0]
        return rvpn_l3_policy

    def _get_management_gw_ip(self, context):

        filters = {'name':[SVC_MGMT_PTG_NAME]}
        svc_mgmt_ptgs = context.gbp_plugin.get_policy_target_groups(
                                        context.plugin_context, filters)
        if not svc_mgmt_ptgs:
            LOG.error(_("Service Management Group is not created by Admin"))
            raise Exception()
        else:
            mgmt_subnet_id = svc_mgmt_ptgs[0]['subnets'][0]
            mgmt_subnet = context.core_plugin.get_subnet(
            context._plugin_context, mgmt_subnet_id)
            mgmt_gw_ip = mgmt_subnet['gateway_ip']
            return mgmt_gw_ip

    # TODO(Magesh): Validate that the Plumber returned what we asked for
    def _update_node_config(self, context, update=False, mgmt_fips={}):
        provider_cidr = provider_subnet = None
        provider_l2p_subnets = context.core_plugin.get_subnets(
            context.plugin_context, filters={'id': context.provider['subnets']})
        for subnet in provider_l2p_subnets:
            if not subnet['name'].startswith(APIC_OWNED_RES):
                provider_cidr = subnet['cidr']
                provider_subnet = subnet
                break
        if not provider_cidr:
            raise # Raise proper exception object
        service_type = self._get_service_type(context.current_profile)
        service_vendor, _ = self._get_vendor_ha_enabled(
            context.current_profile)

        stack_template = context.current_node.get('config')
        stack_template = (jsonutils.loads(stack_template) if
                          stack_template.startswith('{') else
                          yaml.load(stack_template))
        config_param_values = context.instance.get('config_param_values', '{}')
        stack_params = {}
        config_param_values = jsonutils.loads(config_param_values)

        is_template_aws_version = stack_template.get(
            'AWSTemplateFormatVersion', False)
        resources_key = ('Resources' if is_template_aws_version
                         else 'resources')
        parameters_key = ('Parameters' if is_template_aws_version
                          else 'parameters')
        properties_key = ('Properties' if is_template_aws_version
                          else 'properties')

        # FIXME(Magesh): Adapt to the new model with HA
        # Is this okay just using the first entry
        service_targets = self._get_service_targets(context)
        provider_port = service_targets['provider_ports'][0]
        provider_port_mac = provider_port['mac_address']
        provider_cidr = context.core_plugin.get_subnet(
            context.plugin_context, provider_port['fixed_ips'][0][
                'subnet_id'])['cidr']
        service_vendor, ha_enabled = self._get_vendor_ha_enabled(
            context.current_profile)
        if service_type == pconst.LOADBALANCER:
            self._generate_pool_members(
                context, stack_template, config_param_values,
                context.provider, is_template_aws_version)
            config_param_values['Subnet'] = provider_subnet['id']
            config_param_values['service_chain_metadata'] = (
                SC_METADATA % (context.instance['id'],
                               mgmt_fips['active_mgmt_fip'],
                               provider_port_mac,
                               mgmt_fips.get('standby_mgmt_fip')))
        elif service_type == pconst.FIREWALL:
            stack_template = self._update_firewall_template(
                context, stack_template)
            self._modify_fw_resources_name(
                stack_template, context.provider, is_template_aws_version)
            firewall_desc = {'vm_management_ip': mgmt_fips['active_mgmt_fip'],
                             'provider_ptg_info': [provider_port_mac],
                             'standby_vm_management_ip': mgmt_fips.get(
                                'standby_mgmt_fip'),
                             'provider_cidr': provider_cidr,
                             'service_vendor': service_vendor}
            fw_key = self._get_heat_resource_key(
                stack_template[resources_key],
                is_template_aws_version,
                'OS::Neutron::Firewall')
            stack_template[resources_key][fw_key][properties_key][
                'description'] = str(firewall_desc)
        elif service_type == pconst.VPN:
            rvpn_l3_policy = self._get_rvpn_l3_policy(context, update)
            config_param_values['ClientAddressPoolCidr'] = rvpn_l3_policy[
                'ip_pool']
            consumer_port = service_targets['consumer_ports'][0]
            config_param_values['Subnet'] = (
                consumer_port['fixed_ips'][0]['subnet_id']
                if consumer_port else None)
            l2p = context.gbp_plugin.get_l2_policy(
                context.plugin_context, context.provider['l2_policy_id'])
            l3p = context.gbp_plugin.get_l3_policy(
                context.plugin_context, l2p['l3_policy_id'])
            config_param_values['RouterId'] = l3p['routers'][0]
            stitching_subnet = context.core_plugin.get_subnet(
                context._plugin_context,
                consumer_port['fixed_ips'][0]['subnet_id'])
            stitching_cidr = stitching_subnet['cidr']
            mgmt_gw_ip = self._get_management_gw_ip(context)

            if not update:
                services_nsp = context.gbp_plugin.get_network_service_policies(
                    context.plugin_context,
                    filters={'name': ['oneconvergence_services_nsp']})
                if not services_nsp:
                    fip_nsp = {
                    'network_service_policy': {
                        'name': 'oneconvergence_services_nsp',
                        'description': 'oneconvergence_implicit_resource',
                        'shared': False,
                        'tenant_id': context._plugin_context.tenant_id,
                        'network_service_params': [
                            {"type": "ip_pool", "value": "nat_pool",
                             "name": "vpn_svc_external_access"}]
                        }
                    }
                    nsp = context.gbp_plugin.create_network_service_policy(
                        context.plugin_context, fip_nsp)
                else:
                    nsp = services_nsp[0]
                stitching_pts = context.gbp_plugin.get_policy_targets(
                    context.plugin_context,
                    filters={'port_id': [consumer_port['id']]})
                if not stitching_pts:
                    LOG.error(_("Policy target is not created for the "
                                "stitching port"))
                    raise Exception()
                stitching_ptg_id = stitching_pts[0]['policy_target_group_id']
                context.gbp_plugin.update_policy_target_group(
                    context.plugin_context, stitching_ptg_id,
                    {'policy_target_group': {
                        'network_service_policy_id': nsp['id']}})
            filters = {'port_id': [consumer_port['id']]}
            floatingips = context.l3_plugin.get_floatingips(
                context.plugin_context, filters=filters)
            if not floatingips:
                raise FloatingIPForVPNRemovedManually()
            stitching_port_fip = floatingips[0]['floating_ip_address']
            desc = ('fip=' + mgmt_fips['active_mgmt_fip'] +
                    ";tunnel_local_cidr=" +
                    provider_cidr + ";user_access_ip=" +
                    stitching_port_fip + ";fixed_ip=" +
                    consumer_port['fixed_ips'][0]['ip_address'] +
                    ';standby_fip=' + mgmt_fips.get('standby_mgmt_fip', "") +
                    ';service_vendor=' + service_vendor +
                    ';stitching_cidr=' + stitching_cidr +
                    ';stitching_gateway=' + stitching_subnet['gateway_ip'] +
                    ';mgmt_gw_ip=' + mgmt_gw_ip)
            stack_params['ServiceDescription'] = desc
            siteconn_keys = self._get_site_conn_keys(
                stack_template[resources_key],
                is_template_aws_version,
                'OS::Neutron::IPsecSiteConnection')
            for siteconn_key in siteconn_keys:
                stack_template[resources_key][siteconn_key][properties_key][
                'description'] = desc

        for parameter in stack_template.get(parameters_key) or []:
            if parameter in config_param_values:
                stack_params[parameter] = config_param_values[parameter]

        #LOG.info(_("Final stack_template : %(template)s, stack_params : "
        #           "%(param)s"), {'template': stack_template,
        #                          'param': stack_params})
        LOG.info("Final stack_template : %s, stack_params : %s" %
                     (stack_template, stack_params))
        return (stack_template, stack_params)

    def _get_site_conn_keys(self, template_resource_dict,
                               is_template_aws_version, resource_name):
        keys = []
        type_key = 'Type' if is_template_aws_version else 'type'
        for key in template_resource_dict:
            if template_resource_dict[key].get(type_key) == resource_name:
                keys.append(key)
        return keys

    def _get_all_heat_resource_keys(self, template_resource_dict,
                                    is_template_aws_version, resource_name):
        type_key = 'Type' if is_template_aws_version else 'type'
        resource_keys = []
        for key in template_resource_dict:
            if template_resource_dict[key].get(type_key) == resource_name:
                resource_keys.append(key)
        return resource_keys

    def _update_cidr_in_fw_rules(self, stack_template, provider_cidr,
                                 consumer_cidr, is_template_aws_version):
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

    def _modify_fw_resources_name(self, stack_template, provider_ptg,
                                  is_template_aws_version):
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

    def _modify_lb_resources_name(self, stack_template, provider_ptg,
                                  is_template_aws_version):
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
        self._modify_lb_resources_name(
            stack_template, provider_ptg, is_template_aws_version)
        member_ips = self._get_member_ips(context, provider_ptg)
        if not member_ips:
            return

        pool_res_name = self._get_heat_resource_key(
            stack_template[resources_key],
            is_template_aws_version,
            "OS::Neutron::Pool")
        for member_ip in member_ips:
            member_name = 'mem-' + member_ip
            stack_template[resources_key][member_name] = (
                self._generate_lb_member_template(
                    is_template_aws_version, pool_res_name,
                    member_ip, stack_template))

    def _get_member_ips(self, context, ptg):
        member_addresses = []
        policy_targets = context.gbp_plugin.get_policy_targets(
            context.plugin_context,
            filters={'id': ptg.get("policy_targets")})
        for policy_target in policy_targets:
            if (plumber_base.SERVICE_TARGET_NAME_PREFIX not in
                policy_target['name'] and "tscp_endpoint_service_" not in
                policy_target['name'] and "vip_pt" not in
                policy_target['name']):
                port_id = policy_target.get("port_id")
                if port_id:
                    port = context.core_plugin.get_port(
                        context.plugin_context, port_id)
                    ip_address = port.get('fixed_ips')[0].get("ip_address")
                    member_addresses.append(ip_address)
        return member_addresses

    def _generate_lb_member_template(self, is_template_aws_version,
                                     pool_res_name, member_ip, stack_template):
        type_key = 'Type' if is_template_aws_version else 'type'
        properties_key = ('Properties' if is_template_aws_version
                          else 'properties')
        resources_key = 'Resources' if is_template_aws_version else 'resources'
        res_key = 'Ref' if is_template_aws_version else 'get_resource'

        lbaas_pool_key = self._get_heat_resource_key(
            stack_template[resources_key],
            is_template_aws_version,
            "OS::Neutron::Pool")
        lbaas_vip_key = self._get_heat_resource_key(
            stack_template[resources_key],
            is_template_aws_version,
            "OS::Neutron::LoadBalancer")
        vip_port = stack_template[resources_key][lbaas_pool_key][
            properties_key]['vip']['protocol_port']
        member_port = stack_template[resources_key][lbaas_vip_key][
            properties_key].get('protocol_port')
        protocol_port = member_port if member_port else vip_port

        return {type_key: "OS::Neutron::PoolMember",
                properties_key: {
                    "address": member_ip,
                    "admin_state_up": True,
                    "pool_id": {res_key: pool_res_name},
                    "protocol_port": protocol_port,
                    "weight": 1}}

    def _get_heat_client(self, plugin_context, tenant_id=None):
        user_tenant_id = tenant_id or plugin_context.tenant
        self._assign_admin_user_to_project(user_tenant_id)
        admin_token = self.keystone(tenant_id=user_tenant_id).get_token(
            user_tenant_id)
        # This method is not consistent. We are not really using username
        # from context
        context = n_context.ContextBase(user_id=None, tenant_id=user_tenant_id)
        return heat_api_client.HeatClient(
            context,
            cfg.CONF.oneconvergence_node_driver.heat_uri,
            auth_token=admin_token)

    def keystone(self, tenant_id=None):
        user, password, tenant, auth_url = utils.get_keystone_creds()
        if tenant_id:
            return keyclient.Client(
                username=user, password=password,
                auth_url=auth_url, tenant_id=tenant_id)
        else:
            return keyclient.Client(
                username=user, password=password,
                auth_url=auth_url, tenant_name=tenant)

    def _get_v3_keystone_admin_client(self):
        """ Returns keystone v3 client with admin credentials
            Using this client one can perform CRUD operations over
            keystone resources.
        """
        keystone_conf = cfg.CONF.keystone_authtoken
        v3_auth_url = ('%s://%s:%s/v3/' % (
            keystone_conf.auth_protocol, keystone_conf.auth_host,
            keystone_conf.auth_port))
        v3client = keyclientv3.Client(
            username=keystone_conf.admin_user,
            password=keystone_conf.admin_password,
            domain_name="default",  # FIXME(Magesh): Make this config driven
            auth_url=v3_auth_url)
        return v3client

    def _get_role_by_name(self, v3client, name):
        role = v3client.roles.list(name=name)
        if role:
            return role[0]
        else:
            raise RequiredRoleNotCreated(role_name=name)

    def _assign_admin_user_to_project(self, project_id):
        v3client = self._get_v3_keystone_admin_client()
        keystone_conf = cfg.CONF.keystone_authtoken
        admin_id = v3client.users.find(name=keystone_conf.admin_user).id
        admin_role = self._get_role_by_name(v3client, "admin")
        v3client.roles.grant(admin_role.id, user=admin_id, project=project_id)
        heat_role = self._get_role_by_name(v3client, "heat_stack_owner")
        v3client.roles.grant(heat_role.id, user=admin_id, project=project_id)
