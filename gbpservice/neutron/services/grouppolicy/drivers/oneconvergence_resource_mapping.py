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

from neutron.common import exceptions as n_exc
from neutron.common import log
from neutron.extensions import securitygroup as ext_sg
from neutron.openstack.common import log as logging
from neutron.plugins.common import constants as pconst

from gbpservice.neutron.extensions import group_policy as gp_ext
from gbpservice.neutron.services.grouppolicy.common import constants as gconst
from gbpservice.neutron.services.grouppolicy.common import exceptions as exc
from gbpservice.neutron.services.grouppolicy.drivers import resource_mapping

LOG = logging.getLogger(__name__)


class PTGInUseByPRS(n_exc.InUse, exc.GroupPolicyException):
    message = _("Please unset the Policy Rule Sets before deleting the "
                "Policy Target Group")


class EPInUseByPRS(n_exc.InUse, exc.GroupPolicyException):
    message = _("Please unset the Policy Rule Sets before deleting the "
                "External Policy")


class PTGCreateFailed(exc.GroupPolicyException):
    message = _("Policy Target group creation failed")


class PTGCreateAndCleanupFailed(exc.GroupPolicyException):
    message = _("Policy Target group creation and cleanup failed. Please unset"
                " the Policy Rulesets and delete the Policy Target Group")


class ExternalPolicyCreateFailed(exc.GroupPolicyException):
    message = _("External Policy creation failed")


class ExternalPolicyCreateAndCleanupFailed(exc.GroupPolicyException):
    message = _("External Policy creation and cleanup failed. Please unset"
                " the Policy Rulesets and delete the External Policy")


class OneConvergenceResourceMappingDriver(
    resource_mapping.ResourceMappingDriver):
    """One Convergence Resource Mapping driver for Group Policy plugin.

    This driver inherits default group policy RMD.
    """

    # This operation may fail since we delete it if we have FW in chain
    def _remove_router_interface(self, plugin_context, router_id,
                                 interface_info):
        try:
            self._l3_plugin.remove_router_interface(
                    plugin_context, router_id, interface_info)
        except Exception:
            pass

    def create_external_policy_precommit(self, context):
        self._reject_shared(context.current, 'external_policy')
        # REVISIT(ivar): For security reasons, only one ES allowed per EP.
        # see bug #1398156
        if len(context.current['external_segments']) > 1:
            raise exc.MultipleESPerEPNotSupported()

    def create_external_policy_postcommit(self, context):
        # Only *North to South* rules are actually effective.
        # The rules will be calculated as the symmetric difference between
        # the union of all the Tenant's L3P supernets and the union of all the
        # ES routes.
        # REVISIT(ivar): Remove when ES update is supported for EP
        if not context.current['external_segments']:
            raise exc.ESIdRequiredWhenCreatingEP()
        ep = context.current
        if ep['external_segments']:
            if (ep['provided_policy_rule_sets'] or
                ep['consumed_policy_rule_sets']):
                # Get the full processed list of external CIDRs
                cidr_list = self._get_processed_ep_cidr_list(context, ep)
                # set the rules on the proper SGs
                self._set_sg_rules_for_cidrs(
                    context, cidr_list, ep['provided_policy_rule_sets'],
                    ep['consumed_policy_rule_sets'])
            try:
                if ep['consumed_policy_rule_sets']:
                    self._handle_redirect_action(
                        context, ep['consumed_policy_rule_sets'])
            except Exception:
                LOG.exception(_("Creating External Policy failed"))
                external_policy = {'external_policy': {
                                       'provided_policy_rule_sets': {},
                                       'consumed_policy_rule_sets': {}}}
                try:
                    context._plugin.update_external_policy(
                        context._plugin_context,
                        context.current['id'],
                        external_policy)
                except Exception:
                    LOG.exception(_("Unsetting Policy Ruleset failed as part "
                                    "of cleanup"))
                    raise ExternalPolicyCreateAndCleanupFailed()
                else:
                    raise ExternalPolicyCreateFailed()

    @log.log
    def create_policy_target_group_postcommit(self, context):
        subnets = context.current['subnets']
        if subnets:
            l2p_id = context.current['l2_policy_id']
            l2p = context._plugin.get_l2_policy(context._plugin_context,
                                                l2p_id)
            l3p_id = l2p['l3_policy_id']
            l3p = context._plugin.get_l3_policy(context._plugin_context,
                                                l3p_id)
            router_id = l3p['routers'][0] if l3p['routers'] else None
            for subnet_id in subnets:
                self._use_explicit_subnet(
                    context._plugin_context, subnet_id, router_id)
        else:
            self._use_implicit_subnet(context)
        self._handle_network_service_policy(context)
        try:
            self._handle_policy_rule_sets(context)
            self._update_default_security_group(context._plugin_context,
                                                context.current['id'],
                                                context.current['tenant_id'],
                                                context.current['subnets'])
            if (self._is_firewall_in_sc_spec(context,
                                             ptg_id=context.current['id'])
                and self._is_ptg_provider(context, context.current['id'])):
                    self._create_service_vm_sg(context,
                                               context.current['tenant_id'],
                                               context.current['id'])
        except Exception:
            LOG.exception(_("Creating Policy Target Group failed"))
            policy_target_group = {'policy_target_group': {
                                        'provided_policy_rule_sets': {},
                                        'consumed_policy_rule_sets': {}}}
            try:
                context._plugin.update_policy_target_group(
                    context._plugin_context,
                    context.current['id'],
                    policy_target_group)
            except Exception:
                LOG.exception(_("Unsetting Policy Ruleset failed as part of "
                                "cleanup"))
                raise PTGCreateAndCleanupFailed()
            else:
                raise PTGCreateFailed()

    @log.log
    def delete_policy_target_group_precommit(self, context):
        provider_ptg_chain_map = self._get_ptg_servicechain_mapping(
                                            context._plugin_context.session,
                                            context.current['id'],
                                            None)
        consumer_ptg_chain_map = self._get_ptg_servicechain_mapping(
                                            context._plugin_context.session,
                                            None,
                                            context.current['id'],)
        context.ptg_chain_map = provider_ptg_chain_map + consumer_ptg_chain_map
        if context.ptg_chain_map:
            raise PTGInUseByPRS()
        context.nsp_cleanup_ipaddress = self._get_ptg_policy_ipaddress_mapping(
            context._plugin_context.session, context.current['id'])
        context.nsp_cleanup_fips = self._get_ptg_policy_fip_mapping(
            context._plugin_context.session, context.current['id'])
        if (self._is_firewall_in_sc_spec(context, ptg_id=context.current['id'])
                and self._is_ptg_provider(context, context.current['id'])):
            context.delete_service_vm_sg = True
        else:
            context.delete_service_vm_sg = False

    @log.log
    def delete_policy_target_group_postcommit(self, context):
        try:
            self._cleanup_network_service_policy(context,
                                                 context.current,
                                                 context.nsp_cleanup_ipaddress,
                                                 context.nsp_cleanup_fips)
        except Exception as e:
            LOG.exception((e))
        self._cleanup_redirect_action(context)
        # Cleanup SGs
        self._unset_sg_rules_for_subnets(
            context, context.current['subnets'],
            context.current['provided_policy_rule_sets'],
            context.current['consumed_policy_rule_sets'])

        l2p_id = context.current['l2_policy_id']
        try:
            router_id = self._get_routerid_for_l2policy(context, l2p_id)
            for subnet_id in context.current['subnets']:
                self._cleanup_subnet(
                    context._plugin_context, subnet_id, router_id)
        except Exception as e:
            LOG.exception((e))
        self._delete_default_security_group(
            context._plugin_context, context.current['id'],
            context.current['tenant_id'])
        if context.delete_service_vm_sg:
            self._delete_service_vm_sg(context, context.current['tenant_id'],
                                       context.current['id'])

    def delete_external_policy_precommit(self, context):
        provider_ptg_chain_map = self._get_ptg_servicechain_mapping(
                                            context._plugin_context.session,
                                            context.current['id'],
                                            None)
        consumer_ptg_chain_map = self._get_ptg_servicechain_mapping(
                                            context._plugin_context.session,
                                            None,
                                            context.current['id'],)
        context.ptg_chain_map = provider_ptg_chain_map + consumer_ptg_chain_map
        if context.ptg_chain_map:
            raise EPInUseByPRS()

    def _create_service_vm_sg_rule(self, context, sg_id):
        attrs = {'tenant_id': context._plugin_context.tenant_id,
                 'security_group_id': sg_id,
                 'direction': 'ingress',
                 'ethertype': 'IPv4',
                 'protocol': None,
                 'port_range_min': None,
                 'port_range_max': None,
                 'remote_ip_prefix': '0.0.0.0/0',
                 'remote_group_id': None}

        return self._create_sg_rule(context._plugin_context, attrs)

    def _create_service_vm_sg(self, context, tenant_id, ptg_id):
        port_name = 'svc_vm_%s' % ptg_id
        attrs = {'name': port_name,
                 'tenant_id': tenant_id,
                 'description': 'default'}
        sg_id = self._create_sg(context._plugin_context, attrs)['id']
        self._create_service_vm_sg_rule(context, sg_id)
        return sg_id

    def _get_service_vm_sg(self, plugin_context, tenant_id, ptg_id):
        port_name = 'svc_vm_%s' % ptg_id
        filters = {'name': [port_name]}
        default_group = self._core_plugin.get_security_groups(
            plugin_context, filters)
        return default_group[0]['id'] if default_group else None

    def _delete_service_vm_sg(self, context, tenant_id, ptg_id):
        sg_id = self._get_service_vm_sg(context._plugin_context,
                                        tenant_id, ptg_id)
        if sg_id:
            self._delete_sg(context._plugin_context, sg_id)

    def _is_firewall_in_sc_spec(self, context, pt_id=None, ptg_id=None):
        spec_id = self._get_redirect_action_spec_id(context, pt_id, ptg_id)
        if spec_id:
            sc_spec = self._servicechain_plugin.get_servicechain_spec(
                                            context._plugin_context, spec_id)
            for node_id in sc_spec['nodes']:
                sc_node = self._servicechain_plugin.get_servicechain_node(
                                            context._plugin_context, node_id)
                profile_id = sc_node.get('service_profile_id')
                if profile_id:
                    profile = self._servicechain_plugin.get_service_profile(
                        context._plugin_context, profile_id)
                    if profile['service_type'] == pconst.FIREWALL:
                        return True
        return False

    def _get_policy_rule_set_ids(self, context, pt_id, ptg_id):
        policy_rule_set_ids = []
        if pt_id:
            try:
                pt = context._plugin.get_policy_target(context._plugin_context,
                                                       pt_id)
            except gp_ext.PolicyTargetNotFound:
                LOG.warn(_("PT %s doesn't exist anymore"), pt_id)
                return
            ptg = context._plugin.get_policy_target_group(
                context._plugin_context, pt['policy_target_group_id'])
            if ptg['provided_policy_rule_sets']:
                policy_rule_set_ids = ptg['provided_policy_rule_sets']
        if ptg_id:
            policy_rule_set_ids = context.current['provided_policy_rule_sets']
        return policy_rule_set_ids

    def _get_redirect_action_spec_id(self, context, pt_id, ptg_id):
        policy_rule_set_ids = self._get_policy_rule_set_ids(
            context, pt_id, ptg_id)
        if not policy_rule_set_ids:
            return None

        policy_rule_sets = context._plugin.get_policy_rule_sets(
                                    context._plugin_context,
                                    filters={'id': policy_rule_set_ids})
        for policy_rule_set in policy_rule_sets:
            policy_rules = context._plugin.get_policy_rules(
                context._plugin_context,
                filters={'id': policy_rule_set['policy_rules']})
            for policy_rule in policy_rules:
                policy_actions = context._plugin.get_policy_actions(
                    context._plugin_context,
                    filters={'id': policy_rule["policy_actions"],
                             'action_type': [gconst.GP_ACTION_REDIRECT]})
                for policy_action in policy_actions:
                    if (policy_action['action_type'] ==
                        gconst.GP_ACTION_REDIRECT):
                        spec_id = policy_action.get("action_value")
                        return spec_id

    def _update_service_vm_rules(self, context, pt_id=None, ptg_id=None):
        # Get all instances corresponding to a spec _id and update
        # each instance.
        spec_id = self._get_redirect_action_spec_id(context, pt_id, ptg_id)
        if spec_id:
            sc_instance_update_req = {
                'servicechain_specs': [spec_id]}
            sc_spec = self._servicechain_plugin.get_servicechain_specs(
                context._plugin_context, filters={'id': [spec_id]})[0]
            for sc_instance in sc_spec['instances']:

                self._update_resource(
                        self._servicechain_plugin,
                        context._plugin_context,
                        'servicechain_instance',
                        sc_instance,
                        sc_instance_update_req)

    def _is_ptg_provider(self, context, ptg_id):
        ptg = context._plugin.get_policy_target_group(context._plugin_context,
                                                      ptg_id)
        if ptg['provided_policy_rule_sets']:
            return True
        else:
            return False

    def _assoc_sgs_to_pt(self, context, pt_id, sg_list):
        try:
            pt = context._plugin.get_policy_target(context._plugin_context,
                                                   pt_id)
        except gp_ext.PolicyTargetNotFound:
            LOG.warn(_("PT %s doesn't exist anymore"), pt_id)
            return
        port_id = pt['port_id']
        port = self._core_plugin.get_port(context._plugin_context, port_id)
        cur_sg_list = port[ext_sg.SECURITYGROUPS]
        if (self._is_firewall_in_sc_spec(context, pt_id=pt_id) and
            self._is_ptg_provider(context, pt['policy_target_group_id'])):
            sg_id = self._get_service_vm_sg(context._plugin_context,
                                    context._plugin_context.tenant_id,
                                    pt['policy_target_group_id'])
            new_sg_list = [sg_id]
            # Commenting update part, until update changes are upstreamed
            # for plugin.
            # self._update_service_vm_rules(context, pt_id=pt_id)
        else:
            new_sg_list = cur_sg_list + sg_list
        port[ext_sg.SECURITYGROUPS] = new_sg_list
        self._update_port(context._plugin_context, port_id, port)

    def _disassoc_sgs_from_pt(self, context, pt_id, sg_list):
        try:
            pt = context._plugin.get_policy_target(context._plugin_context,
                                                   pt_id)
        except gp_ext.PolicyTargetNotFound:
            LOG.warn(_("PT %s doesn't exist anymore"), pt_id)
            return
        port_id = pt['port_id']
        self._disassoc_sgs_from_port(context._plugin_context, port_id, sg_list)

    def _disassoc_sgs_from_port(self, plugin_context, port_id, sg_list):
        try:
            port = self._core_plugin.get_port(plugin_context, port_id)
            cur_sg_list = port[ext_sg.SECURITYGROUPS]
            new_sg_list = list(set(cur_sg_list) - set(sg_list))
            port[ext_sg.SECURITYGROUPS] = new_sg_list
            self._update_port(plugin_context, port_id, port)
        except n_exc.PortNotFound:
            LOG.warn(_("Port %s is missing") % port_id)

"""
    def _handle_redirect_action(self, context, policy_rule_set_ids):
        policy_rule_sets = context._plugin.get_policy_rule_sets(
                                    context._plugin_context,
                                    filters={'id': policy_rule_set_ids})
        for policy_rule_set in policy_rule_sets:
            ptgs_consuming_prs = (
                policy_rule_set['consuming_policy_target_groups'] +
                policy_rule_set['consuming_external_policies'])
            ptgs_providing_prs = policy_rule_set[
                                            'providing_policy_target_groups']

            # Create the ServiceChain Instance when we have both Provider and
            # consumer PTGs. If Labels are available, they have to be applied
            if not ptgs_consuming_prs or not ptgs_providing_prs:
                continue

            parent_classifier_id = None
            parent_spec_id = None
            if policy_rule_set['parent_id']:
                parent = context._plugin.get_policy_rule_set(
                    context._plugin_context, policy_rule_set['parent_id'])
                policy_rules = context._plugin.get_policy_rules(
                                    context._plugin_context,
                                    filters={'id': parent['policy_rules']})
                for policy_rule in policy_rules:
                    policy_actions = context._plugin.get_policy_actions(
                        context._plugin_context,
                        filters={'id': policy_rule["policy_actions"],
                                 'action_type': [gconst.GP_ACTION_REDIRECT]})
                    if policy_actions:
                        parent_spec_id = policy_actions[0].get("action_value")
                        parent_classifier_id = policy_rule.get(
                                                    "policy_classifier_id")
                        break  # only one redirect action is supported
            policy_rules = context._plugin.get_policy_rules(
                    context._plugin_context,
                    filters={'id': policy_rule_set['policy_rules']})

            # Delete the existing mapped chains here.
            for ptg_consuming_prs in ptgs_consuming_prs:
                for ptg_providing_prs in ptgs_providing_prs:
                    ptg_chain_map = (
                                self._get_ptg_servicechain_mapping(
                                    context._plugin_context.session,
                                    ptg_providing_prs,
                                    ptg_consuming_prs))
                    # REVISIT(Magesh): There may be concurrency
                    # issues here.
                    for ptg_chain in ptg_chain_map:
                        self._delete_servicechain_instance(
                            context,
                            ptg_chain.servicechain_instance_id)

            for policy_rule in policy_rules:
                classifier_id = policy_rule.get("policy_classifier_id")
                if parent_classifier_id and not set(
                                [parent_classifier_id]) & set([classifier_id]):
                    continue
                policy_actions = context._plugin.get_policy_actions(
                        context._plugin_context,
                        filters={'id': policy_rule.get("policy_actions"),
                                 'action_type': [gconst.GP_ACTION_REDIRECT]})
                for policy_action in policy_actions:
                    for ptg_consuming_prs in ptgs_consuming_prs:
                        for ptg_providing_prs in ptgs_providing_prs:
                            sc_instance = self._create_servicechain_instance(
                                context, policy_action.get("action_value"),
                                parent_spec_id, ptg_providing_prs,
                                ptg_consuming_prs, classifier_id)
                            self._set_ptg_servicechain_instance_mapping(
                                context._plugin_context.session,
                                ptg_providing_prs, ptg_consuming_prs,
                                sc_instance['id'])
"""

