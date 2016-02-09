# Copyright (c) 2016 OpenStack Foundation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import eventlet
from keystoneclient import exceptions as k_exceptions
from keystoneclient.v2_0 import client as keyclient
from neutron.common import exceptions as n_exc
from neutron.common import rpc as n_rpc
from neutron.db import model_base
from neutron.plugins.common import constants as pconst
from oslo_config import cfg
from oslo_log import log as logging
import oslo_messaging
from oslo_serialization import jsonutils
from oslo_utils import excutils
import sqlalchemy as sa
from sqlalchemy.orm.exc import NoResultFound

from gbpservice.common import utils
from gbpservice.neutron.nsf.common import topics as nsf_rpc_topics
from gbpservice.neutron.services.servicechain.plugins.ncp import driver_base
from gbpservice.neutron.services.servicechain.plugins.ncp import (
    exceptions as exc)
from gbpservice.neutron.services.servicechain.plugins.ncp import model
from gbpservice.neutron.services.servicechain.plugins.ncp import plumber_base


NSF_NODE_DRIVER_OPTS = [
    cfg.StrOpt('svc_management_ptg_name',
               default='svc_management_ptg',
               help=_("Name of the PTG that is associated with the "
                      "service management network")),
    cfg.BoolOpt('is_service_admin_owned',
                help=_("Parameter to indicate whether the Service VM has to "
                       "be owned by the Admin"),
                default=False),
    cfg.IntOpt('service_create_timeout',
               default=600,
               help=_("Seconds to wait for service creation "
                      "to complete")),
    cfg.IntOpt('service_delete_timeout',
               default=120,
               help=_("Seconds to wait for service deletion "
                      "to complete")),
]

cfg.CONF.register_opts(NSF_NODE_DRIVER_OPTS, "nsf_node_driver")

SVC_MGMT_PTG_NAME = cfg.CONF.nsf_node_driver.svc_management_ptg_name


LOG = logging.getLogger(__name__)


class InvalidServiceType(exc.NodeCompositionPluginBadRequest):
    message = _("The NSF Node driver only supports the services "
                "VPN, Firewall and LB in a Service Chain")


class ServiceProfileRequired(exc.NodeCompositionPluginBadRequest):
    message = _("A Service profile is required in Service node")


class NodeVendorMismatch(exc.NodeCompositionPluginBadRequest):
    message = _("The NSF Node driver only handles nodes which have service "
                "profile with vendor name %(vendor)s")


class DuplicateServiceTypeInChain(exc.NodeCompositionPluginBadRequest):
    message = _("The NSF Node driver does not support duplicate "
                "service types in same chain")


class RequiredProfileAttributesNotSet(exc.NodeCompositionPluginBadRequest):
    message = _("The required attributes in service profile are not present")


class InvalidNodeOrderInChain(exc.NodeCompositionPluginBadRequest):
    message = _("The NSF Node driver does not support the order "
                "of nodes defined in the current service chain spec")


class UnSupportedServiceProfile(exc.NodeCompositionPluginBadRequest):
    message = _("The NSF Node driver does not support this service "
                "profile with service type %(service_type)s and vendor "
                "%(vendor)s")


class UnSupportedInsertionMode(exc.NodeCompositionPluginBadRequest):
    message = _("The NSF Node driver supports only L3 Insertion "
                "mode")


class ServiceInfoNotAvailableOnUpdate(n_exc.NeutronException):
    message = _("Service information is not available with Service Manager "
                "on node update")


class VipNspNotSetonProvider(n_exc.NeutronException):
    message = _("Network Service policy for VIP IP address is not configured "
                "on the Providing Group")


class NodeInstanceDeleteFailed(n_exc.NeutronException):
    message = _("Node instance delete failed in NSF Node driver")


class NodeInstanceCreateFailed(n_exc.NeutronException):
    message = _("Node instance create failed in NSF Node driver")


class ServiceNodeInstanceNetworkServiceMapping(model_base.BASEV2):
    """ServiceChainInstance to NSF network service mapping."""

    __tablename__ = 'ncp_node_instance_network_service_mappings'
    sc_instance_id = sa.Column(sa.String(36),
                               nullable=False, primary_key=True)
    sc_node_id = sa.Column(sa.String(36),
                           nullable=False, primary_key=True)
    network_service_id = sa.Column(sa.String(36),
                                   nullable=False, primary_key=True)


# These callback apis are not used today, This is supposed to be used when
# GBP supports asynchronous operations
class NSFCallbackApi(object):
    RPC_API_VERSION = "1.0"
    target = oslo_messaging.Target(version=RPC_API_VERSION)

    def __init__(self, node_driver):
        self.node_driver = node_driver

    def network_service_created(self, context, network_service):
        pass

    def network_service_deleted(self, context, network_service):
        pass


class NSFClientApi(object):
    """ Client side of the NSF Framework user """

    RPC_API_VERSION = '1.0'

    def __init__(self, topic):
        target = oslo_messaging.Target(
            topic=topic, version=self.RPC_API_VERSION)
        self.client = n_rpc.get_client(target)

    def create_network_service(self, context, network_service):
        cctxt = self.client.prepare(
            fanout=False, topic=nsf_rpc_topics.NSF_SERVICE_LCM_TOPIC)
        return cctxt.call(
            context, 'create_network_service', network_service=network_service)
        # cctxt.cast(context, 'create_service', service_info=service_info)

    def delete_network_service(self, context, network_service_id):
        cctxt = self.client.prepare(version=self.RPC_API_VERSION)
        return cctxt.call(
            context,
            'delete_network_service',
            network_service_id=network_service_id)

    def get_network_service(self, context, network_service_id):
        cctxt = self.client.prepare(version=self.RPC_API_VERSION)
        return cctxt.call(
            context,
            'get_network_service',
            network_service_id=network_service_id)

    def notify_consumer_ptg_added(self, context, network_service_id, ptg):
        pass

    def notify_consumer_ptg_removed(self, context, network_service_id, ptg):
        pass

    def notify_policy_target_added(self, context, network_service_id,
                                   policy_target):
        pass

    def notify_policy_target_removed(self, context, network_service_id,
                                     policy_target):
        pass


class NSFNodeDriver(driver_base.NodeDriverBase):
    SUPPORTED_SERVICE_TYPES = [
        pconst.LOADBALANCER, pconst.FIREWALL, pconst.VPN]
    SUPPORTED_SERVICE_VENDOR_MAPPING = {
        pconst.LOADBALANCER: ["haproxy"],
        pconst.FIREWALL: ["vyos"],
        pconst.VPN: ["vyos"],
    }
    vendor_name = 'NSF'
    required_heat_resources = {
        pconst.LOADBALANCER: ['OS::Neutron::LoadBalancer',
                              'OS::Neutron::Pool'],
        pconst.FIREWALL: ['OS::Neutron::Firewall',
                          'OS::Neutron::FirewallPolicy'],
        pconst.VPN: ['OS::Neutron::VPNService'],
    }
    initialized = False

    def __init__(self):
        super(NSFNodeDriver, self).__init__()
        self._lbaas_plugin = None

    @property
    def name(self):
        return self._name

    def initialize(self, name):
        self.initialized = True
        self._name = name
        if cfg.CONF.nsf_node_driver.is_service_admin_owned:
            self.resource_owner_tenant_id = self._resource_owner_tenant_id()
        else:
            self.resource_owner_tenant_id = None
        self._setup_rpc_listeners()
        self._setup_rpc()

    def _setup_rpc_listeners(self):
        self.endpoints = [NSFCallbackApi(self)]
        self.topic = nsf_rpc_topics.NSF_NODE_DRIVER_CALLBACK_TOPIC
        self.conn = n_rpc.create_connection(new=True)
        self.conn.create_consumer(self.topic, self.endpoints, fanout=False)
        return self.conn.consume_in_threads()

    def _setup_rpc(self):
        self.nsf_notifier = NSFClientApi(nsf_rpc_topics.NSF_SERVICE_LCM_TOPIC)

    def get_plumbing_info(self, context):
        context._plugin_context = self._get_resource_owner_context(
            context._plugin_context)
        service_type = context.current_profile['service_type']

        # Management PTs are managed by NSF since it supports hosting multiple
        # logical services in a single device
        plumbing_request = {'management': [], 'provider': [{}],
                            'consumer': [{}]}

        if service_type in [pconst.FIREWALL, pconst.VPN]:
            plumbing_request['plumbing_type'] = 'gateway'
        else:  # Loadbalancer which is one arm
            plumbing_request['consumer'] = []
            plumbing_request['plumbing_type'] = 'endpoint'

        LOG.info(_("Requesting plumber for %s PTs for service type "
                   "%s") % (plumbing_request, service_type))
        return plumbing_request

    def validate_create(self, context):
        if not context.current_profile:
            raise ServiceProfileRequired()
        if (not context.current_profile['vendor'] or not
            context.current_profile['insertion_mode'] or not
            context.current_profile['service_type'] or not
            context.current_profile['service_flavor']):
            raise RequiredProfileAttributesNotSet()
        if context.current_profile['vendor'] != self.vendor_name:
            raise NodeVendorMismatch(vendor=self.vendor_name)
        if context.current_profile['insertion_mode'].lower() != "l3":
            raise UnSupportedInsertionMode()
        if context.current_profile['service_type'] not in (
            self.SUPPORTED_SERVICE_TYPES):
            raise InvalidServiceType()
        if (context.current_profile['service_flavor'].lower() not in
            self.SUPPORTED_SERVICE_VENDOR_MAPPING[
                context.current_profile['service_type']]):
            raise UnSupportedServiceProfile(
                service_type=context.current_profile['service_type'],
                vendor=context.current_profile['vendor'])
        self._is_node_order_in_spec_supported(context)

    def validate_update(self, context):
        if not context.original_node:  # PT create/delete notifications
            return
        if context.current_node and not context.current_profile:
            raise ServiceProfileRequired()
        if context.current_profile['vendor'] != self.vendor_name:
            raise NodeVendorMismatch(vendor=self.vendor_name)
        if context.current_profile['insertion_mode'].lower() != "l3":
            raise UnSupportedInsertionMode()
        if context.current_profile['service_type'] not in (
            self.SUPPORTED_SERVICE_TYPES):
            raise InvalidServiceType()
        if (context.current_profile['service_flavor'].lower() not in
            self.SUPPORTED_SERVICE_VENDOR_MAPPING[
                context.current_profile['service_type']]):
            raise UnSupportedServiceProfile(
                service_type=context.current_profile['service_type'],
                vendor=context.current_profile['vendor'])

    def create(self, context):
        context._plugin_context = self._get_resource_owner_context(
            context._plugin_context)
        network_service_id = self._create_network_service(context)
        self._set_node_instance_network_service_map(
            context.plugin_session, context.current_node['id'],
            context.instance['id'], network_service_id)
        self._wait_for_network_service_create_completion(
            context, network_service_id)

    def update(self, context):
        context._plugin_context = self._get_resource_owner_context(
            context._plugin_context)
        self._update(context)

    def delete(self, context):
        context._plugin_context = self._get_resource_owner_context(
            context._plugin_context)
        network_service_map = self._get_node_instance_network_service_map(
            context.plugin_session,
            context.current_node['id'],
            context.instance['id'])

        if not network_service_map:
            return
        
        network_service_id = network_service_map.network_service_id
        try:
            self.nsf_notifier.delete_network_service(
                context=context.plugin_context,
                network_service_id=network_service_id)
        except Exception:
            LOG.exception(_("Delete Network service Failed"))

        self._wait_for_network_service_delete_completion(
            context, network_service_id)
        self._delete_node_instance_network_service_map(
            context.plugin_session,
            context.current_node['id'],
            context.instance['id'])

    def update_policy_target_added(self, context, policy_target):
        if self._get_service_type(
            context.current_profile) == pconst.LOADBALANCER:
            if self._is_service_target(policy_target):
                return
            context._plugin_context = self._get_resource_owner_context(
                context._plugin_context)
            network_service_id = self._get_node_instance_network_service_map(
                context.plugin_session,
                context.current_node['id'],
                context.instance['id'])
            if network_service_id:
                self.nsf_notifier.notify_policy_target_added(
                    context.plugin_context, network_service_id, policy_target)

    def update_policy_target_removed(self, context, policy_target):
        if self._get_service_type(
            context.current_profile) == pconst.LOADBALANCER:
            if self._is_service_target(policy_target):
                return
            context._plugin_context = self._get_resource_owner_context(
                context._plugin_context)
            network_service_map = self._get_node_instance_network_service_map(
                context.plugin_session,
                context.current_node['id'],
                context.instance['id'])

            if network_service_map:
                network_service_id = network_service_map.network_service_id
                self.nsf_notifier.notify_policy_target_removed(
                    context.plugin_context, network_service_id, policy_target)

    def notify_chain_parameters_updated(self, context):
        pass  # We are not using the classifier specified in redirect Rule

    def update_node_consumer_ptg_added(self, context, policy_target_group):
        if self._get_service_type(context.current_profile) == pconst.FIREWALL:
            context._plugin_context = self._get_resource_owner_context(
                context._plugin_context)
            network_service_map = self._get_node_instance_network_service_map(
                context.plugin_session,
                context.current_node['id'],
                context.instance['id'])

            if network_service_map:
                network_service_id = network_service_map.network_service_id
                self.nsf_notifier.notify_consumer_ptg_added(
                    context.plugin_context,
                    network_service_id,
                    policy_target_group)

    def update_node_consumer_ptg_removed(self, context, policy_target_group):
        if self._get_service_type(context.current_profile) == pconst.FIREWALL:
            context._plugin_context = self._get_resource_owner_context(
                context._plugin_context)
            network_service_map = self._get_node_instance_network_service_map(
                context.plugin_session,
                context.current_node['id'],
                context.instance['id'])

            if network_service_map:
                network_service_id = network_service_map.network_service_id
                self.nsf_notifier.notify_consumer_ptg_removed(
                    context.plugin_context,
                    network_service_id,
                    policy_target_group)

    def _wait_for_network_service_delete_completion(self, context,
                                                    network_service_id):
        time_waited = 0
        network_service = None
        while time_waited < cfg.CONF.nsf_node_driver.service_delete_timeout:
            network_service = self.nsf_notifier.get_network_service(
                context.plugin_context, network_service_id)
            if not network_service:
                break
            eventlet.sleep(5)
            time_waited = time_waited + 5

        if network_service:
            LOG.error(_("Delete network service %(network_service)s failed"),
                      {'network_service': network_service_id})
            raise NodeInstanceDeleteFailed()

    def _wait_for_network_service_create_completion(self, context,
                                                    network_service_id):
        time_waited = 0
        network_service = None
        while time_waited < cfg.CONF.nsf_node_driver.service_create_timeout:
            network_service = self.nsf_notifier.get_network_service(
                context.plugin_context, network_service_id)
            if (network_service['status'] == 'ACTIVE' or
                network_service['status'] == 'ERROR'):
                break
            eventlet.sleep(5)
            time_waited = time_waited + 5

        if network_service['status'] != 'ACTIVE':
            LOG.error(_("Delete network service %(network_service)s failed"),
                      {'network_service': network_service_id})
            raise NodeInstanceCreateFailed()

    def _is_service_target(self, policy_target):
        if policy_target['name'] and (policy_target['name'].startswith(
            plumber_base.SERVICE_TARGET_NAME_PREFIX) or
            policy_target['name'].startswith('tscp_endpoint_service') or
            policy_target['name'].startswith('vip_pt')):
            return True
        else:
            return False

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
        if cfg.CONF.nsf_node_driver.is_service_admin_owned:
            resource_owner_context = plugin_context.elevated()
            resource_owner_context.tenant_id = self.resource_owner_tenant_id
            user, pwd, ignore_tenant, auth_url = utils.get_keystone_creds()
            keystoneclient = keyclient.Client(username=user, password=pwd,
                                              auth_url=auth_url)
            resource_owner_context.auth_token = keystoneclient.get_token(
                self.resource_owner_tenant_id)
            return resource_owner_context
        else:
            return plugin_context

    def _update(self, context, pt_added_or_removed=False):
        if context.current_profile['service_type'] == pconst.LOADBALANCER:
            if (not context.original_node or
                context.original_node == context.current_node):
                LOG.info(_("No action to take on update"))
                return
        self.nsf_notifier.update_service_config()

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
                  % (relationship, context.instance['id'],
                     context.current_node['id'],
                     context._plugin_context.tenant_id))
        service_targets = model.get_service_targets(
            context.session,
            servicechain_instance_id=context.instance['id'],
            servicechain_node_id=context.current_node['id'],
            relationship=relationship)
        LOG.debug("service_type %s service_targets: %s"
                  % (context.current_profile['service_type'],
                     service_targets))
        return service_targets

    def _get_service_targets(self, context):
        service_type = context.current_profile['service_type']
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

        service_target_info = {'provider_ports': [], 'provider_pts': [],
                               'consumer_ports': [], 'consumer_pts': []}
        for service_target in provider_service_targets:
            policy_target = context.gbp_plugin.get_policy_target(
                context.plugin_context, service_target.policy_target_id)
            port = context.core_plugin.get_port(
                context.plugin_context, policy_target['port_id'])
            service_target_info['provider_ports'].append(port)
            service_target_info['provider_pts'].append(policy_target['id'])

        for service_target in consumer_service_targets:
            policy_target = context.gbp_plugin.get_policy_target(
                context.plugin_context, service_target.policy_target_id)
            port = context.core_plugin.get_port(
                context.plugin_context, policy_target['port_id'])
            service_target_info['consumer_ports'].append(port)
            service_target_info['consumer_pts'].append(policy_target['id'])

        return service_target_info

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
            service_type_list_in_chain.append(profile['service_type'])

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

    def _create_network_service(self, context):
        sc_instance = context.instance
        service_targets = self._get_service_targets(context)
        if context.current_profile['service_type'] == pconst.LOADBALANCER:
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

        network_service = {
            'tenant_id': context.provider['tenant_id'],
            'service_chain_id': sc_instance['id'],
            'service_id': context.current_node['id'],
            'service_profile_id': context.current_profile['id'],
            'management_ptg_id': self._get_management_ptg_id(context),
            'service_config': context.current_node.get('config'),
            'provider_port_id': service_targets['provider_pts'][0],
            'network_service_mode': 'GBP',
        }

        if service_targets.get('consumer_ports'):
            network_service['consumer_port_id'] = service_targets[
                'consumer_pts'][0]

        return self.nsf_notifier.create_network_service(
            context.plugin_context, network_service=network_service)

    def _set_node_instance_network_service_map(
        self, session, sc_node_id, sc_instance_id, network_service_id):
        with session.begin(subtransactions=True):
            sc_node_instance_ns_map = ServiceNodeInstanceNetworkServiceMapping(
                sc_node_id=sc_node_id,
                sc_instance_id=sc_instance_id,
                network_service_id=network_service_id)
            session.add(sc_node_instance_ns_map)

    def _get_node_instance_network_service_map(self, session, sc_node_id=None,
                                               sc_instance_id=None):
        try:
            with session.begin(subtransactions=True):
                query = session.query(ServiceNodeInstanceNetworkServiceMapping)
                if sc_node_id:
                    query = query.filter_by(sc_node_id=sc_node_id)
                if sc_instance_id:
                    query = query.filter_by(sc_instance_id=sc_instance_id)
                return query.first()
        except NoResultFound:
            return None

    def _delete_node_instance_network_service_map(self, session, sc_node_id,
                                                  sc_instance_id):
        with session.begin(subtransactions=True):
            sc_node_instance_ns_maps = (
                session.query(ServiceNodeInstanceNetworkServiceMapping).
                filter_by(sc_node_id=sc_node_id).
                filter_by(sc_instance_id=sc_instance_id).
                all())
            for sc_node_instance_ns_map in sc_node_instance_ns_maps:
                session.delete(sc_node_instance_ns_map)
