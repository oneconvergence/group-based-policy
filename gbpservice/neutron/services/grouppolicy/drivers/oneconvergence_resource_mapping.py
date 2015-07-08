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


import netaddr

from neutron.common import log
from neutron.openstack.common import jsonutils
from neutron.openstack.common import log as logging
from neutron.plugins.common import constants as pconst
from neutron.common import exceptions as n_exc
from neutron.extensions import securitygroup as ext_sg
from oslo.config import cfg

from gbpservice.neutron.services.grouppolicy.common import constants as gconst
from gbpservice.neutron.services.grouppolicy.common import exceptions as exc
from gbpservice.neutron.extensions import group_policy as gp_ext

from gbpservice.neutron.services.grouppolicy.drivers import resource_mapping

LOG = logging.getLogger(__name__)


class OneConvergenceResourceMappingDriver(resource_mapping.ResourceMappingDriver):
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


    @log.log
    def delete_policy_target_group_postcommit(self, context):
        try:
            self._cleanup_network_service_policy(context,
                                                 context.current,
                                                 context.nsp_cleanup_ipaddress,
                                                 context.nsp_cleanup_fips)
        except Exception as e:
            LOG.error(e)
        self._cleanup_redirect_action(context)
        # Cleanup SGs
        self._unset_sg_rules_for_subnets(
            context, context.current['subnets'],
            context.current['provided_policy_rule_sets'],
            context.current['consumed_policy_rule_sets'])

        l2p_id = context.current['l2_policy_id']
        router_id = self._get_routerid_for_l2policy(context, l2p_id)
        for subnet_id in context.current['subnets']:
            self._cleanup_subnet(context._plugin_context, subnet_id, router_id)
        self._delete_default_security_group(
            context._plugin_context, context.current['id'],
            context.current['tenant_id'])

