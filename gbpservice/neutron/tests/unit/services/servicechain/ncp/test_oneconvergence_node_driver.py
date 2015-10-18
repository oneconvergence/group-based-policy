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

import itertools
import time
import sys

import copy
import heatclient
import mock
from neutron import context as neutron_context
from neutron.extensions import external_net as external_net
from neutron.openstack.common import uuidutils
from neutron.plugins.common import constants
from oslo.serialization import jsonutils
import webob

from gbpservice.neutron.services.grouppolicy.drivers import (
    implicit_policy) #noqa
from gbpservice.neutron.services.servicechain.plugins.ncp import config
from gbpservice.neutron.services.servicechain.plugins.ncp.node_drivers import (
    heat_node_driver as heat_node_driver)
from gbpservice.neutron.services.servicechain.plugins.ncp.node_drivers import (
    openstack_heat_api_client as heatClient)
#from gbpservice.neutron.tests.unit.services.grouppolicy import (
#    test_resource_mapping as test_gp_driver)
from gbpservice.neutron.tests.unit.services.servicechain.ncp import (
    test_ncp_plugin as test_ncp_plugin)
from gbpservice.neutron.tests.unit.services.servicechain.ncp import (
    fake_svc_mgr_client as fake_svc_mgr_client)


STACK_ACTION_WAIT_TIME = 15
'''
SUPPORTED_SERVICE_VENDOR_MAPPING = {constants.LOADBALANCER: ["oneconvergence_haproxy"],
                                    constants.FIREWALL: ["vyos", "asav",
                                                         "vyos_ha", "asav_ha"],
                                    constants.VPN: ["vyos", "asav",
                                                    "vyos_ha", "asav_ha"]}
'''

SUPPORTED_SERVICE_VENDOR_MAPPING = {constants.LOADBALANCER: "oneconvergence_haproxy",
                                    constants.FIREWALL: "oneconvergence_asav_ha",
                                    constants.VPN: "oneconvergence_asav_ha"}
sys.modules["gbpservice.neutron.services.servicechain.plugins.ncp.node_drivers.oc_service_manager_client"] = fake_svc_mgr_client
#import pdb;pdb.set_trace()

class MockStackObject(object):
    def __init__(self, status):
        self.stack_status = status


class MockHeatClientFunctionsDeleteNotFound(object):
    def delete(self, stack_id):
        raise heatclient.exc.HTTPNotFound()

    def create(self, **fields):
        return {'stack': {'id': uuidutils.generate_uuid()}}

    def get(self, stack_id):
        return MockStackObject('DELETE_COMPLETE')


class MockHeatClientFunctions(object):
    def delete(self, stack_id):
        pass

    def create(self, **fields):
        return {'stack': {'id': uuidutils.generate_uuid()}}

    def update(self, stack_id, **fields):
        return {'stack': {'id': stack_id}}

    def get(self, stack_id):
        return MockStackObject('DELETE_COMPLETE')


class MockHeatClientDeleteNotFound(object):
    def __init__(self, api_version, endpoint, **kwargs):
        self.stacks = MockHeatClientFunctionsDeleteNotFound()


class MockHeatClient(object):
    def __init__(self, api_version, endpoint, **kwargs):
        self.stacks = MockHeatClientFunctions()


class OneConvergenceServiceNodeDriverTestCase(
        test_ncp_plugin.NodeCompositionPluginTestCase):

    DEFAULT_LB_CONFIG_DICT = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Resources": {
                "test_pool": {
                    "Type": "OS::Neutron::Pool",
                    "Properties": {
                        "admin_state_up": True,
                        "description": "Haproxy pool from teplate",
                        "lb_method": "ROUND_ROBIN",
                        "monitors": [{"Ref": "HttpHM"}],
                        "name": "Haproxy pool",
                        "protocol": "HTTP",
                        "subnet_id": {"Ref": "Subnet"},
                        "vip": {
                            "subnet": {"Ref": "Subnet"},
                            "address": {"Ref": "vip_ip"},
                            "name": "Haproxy vip",
                            "protocol_port": 80,
                            "connection_limit": -1,
                            "admin_state_up": True,
                            "description": "Haproxy vip from template"
                        }
                    }
                },
                "test_lb": {
                    "Type": "OS::Neutron::LoadBalancer",
                    "Properties": {
                        "pool_id": {"Ref": "HaproxyPool"},
                        "protocol_port": 80
                    }
                }
            }
    }
    DEFAULT_LB_CONFIG = jsonutils.dumps(DEFAULT_LB_CONFIG_DICT)
    DEFAULT_FW_CONFIG_DICT = {
            "heat_template_version": "2013-05-23",
            "resources": {
                'test_fw': {
                    "type": "OS::Neutron::Firewall",
                    "properties": {
                        "admin_state_up": True,
                        "firewall_policy_id": {
                            "get_resource": "Firewall_policy"},
                        "name": "testFirewall",
                        "description": "test Firewall"
                    }
                },
                'test_fw_policy': {
                    "type": "OS::Neutron::FirewallPolicy",
                    "properties": {
                        "shared": False,
                        "description": "test firewall policy",
                        "name": "testFWPolicy",
                        "firewall_rules": [{'get_resource': 'Rule_1'},
                                           {'get_resource': 'Rule_2'}],
                        "audited": True
                    }
                },
                'Rule_1': {
                    'type': 'OS::Neutron::FirewallRule',
                    'properties': {
                        'protocol': 'udp',
                        'enabled': True,
                        'source_ip_address': '172.0.0.0/22',
                        'action': 'allow',
                        'destination_port': '66'
                        }
                    },
                'Rule_2': {
                    'type': 'OS::Neutron::FirewallRule',
                    'properties': {
                        'protocol': 'udp',
                        'enabled': True,
                        'action': 'allow',
                        'destination_port': '22'
                        }
                    },
            }
    }

    DEFAULT_FW_CONFIG = jsonutils.dumps(DEFAULT_FW_CONFIG_DICT)
    
    DEFAULT_S_TO_S_CONFIG_DICT = {u'AWSTemplateFormatVersion': u'2010-09-09',
    u'Description': u'Creates new vpn service - ike + ipsec + vpn service + site-site connection',
    u'Parameters': {   u'RouterId': {   u'Default': u'd1ea4d97-b20e-44fe-a8ff-eccc505df9b1',
                                        u'Description': u'Router id',
                                        u'Type': u'String'},
                       u'ServiceDescription': {   u'Default': u'fip=192.168.20.192;tunnel_local_cidr=10.0.0.0/26',
                                                  u'Description': u'Give floating ip here after fip=',
                                                  u'Type': u'String'},
                       u'Subnet': {   u'Default': u'de1daeaa-7b44-4224-a16d-e37f58a950f6',
                                      u'Description': u'Subnet id on which vpn service is launched',
                                      u'Type': u'String'},
                       u'VPNPeerCidr': {   u'Default': u'50.0.0.0/24',
                                           u'Description': u'Remote CIDRs behind peer site',
                                           u'Type': u'String'},
                       u'peer_address': {   u'Default': u'192.168.20.154',
                                            u'Description': u'Address of peer in site-site connection',
                                            u'Type': u'String'},
                       u'peer_id': {   u'Default': u'50.0.0.6',
                                       u'Description': u'Id of the peer',
                                       u'Type': u'String'}},
    u'Resources': {   u'IKEPolicy': {   u'Properties': {   u'auth_algorithm': u'sha1',
                                                           u'description': u'My new IKE policy',
                                                           u'encryption_algorithm': u'3des',
                                                           u'ike_version': u'v1',
                                                           u'lifetime': {   u'units': u'seconds',
                                                                            u'value': 3600},
                                                           u'name': u'IKEPolicy',
                                                           u'pfs': u'group5',
                                                           u'phase1_negotiation_mode': u'main'},
                                        u'Type': u'OS::Neutron::IKEPolicy'},
                      u'IPsecPolicy': {   u'Properties': {   u'auth_algorithm': u'sha1',
                                                             u'description': u'My new IPsec policy',
                                                             u'encapsulation_mode': u'tunnel',
                                                             u'encryption_algorithm': u'3des',
                                                             u'lifetime': {   u'units': u'seconds',
                                                                              u'value': 3600},
                                                             u'name': u'IPsecPolicy',
                                                             u'pfs': u'group5',
                                                             u'transform_protocol': u'esp'},
                                          u'Type': u'OS::Neutron::IPsecPolicy'},
                      u'IPsecSiteConnection': {   u'Properties': {   u'admin_state_up': True,
                                                                     u'description': u'My new VPN connection',
                                                                     u'dpd': {   u'actions': u'hold',
                                                                                 u'interval': 30,
                                                                                 u'timeout': 120},
                                                                     u'ikepolicy_id': {   u'Ref': u'IKEPolicy'},
                                                                     u'initiator': u'bi-directional',
                                                                     u'ipsecpolicy_id': {   u'Ref': u'IPsecPolicy'},
                                                                     u'mtu': 1500,
                                                                     u'name': u'IPsecSiteConnection',
                                                                     u'peer_address': {   u'Ref': u'peer_address'},
                                                                     u'peer_cidrs': [   {   u'Ref': u'VPNPeerCidr'}],
                                                                     u'peer_id': {   u'Ref': u'peer_id'},
                                                                     u'psk': u'secret',
                                                                     u'vpnservice_id': {   u'Ref': u'VPNService'}},
                                                  u'Type': u'OS::Neutron::IPsecSiteConnection'},
                      u'VPNService': {   u'Properties': {   u'admin_state_up': True,
                                                            u'description': {   u'Ref': u'ServiceDescription'},
                                                            u'name': u'VPNService',
                                                            u'router_id': {   u'Ref': u'RouterId'},
                                                            u'subnet_id': {   u'Ref': u'Subnet'}},
                                         u'Type': u'OS::Neutron::VPNService'}}}
    
    DEFAULT_S_TO_S_CONFIG = jsonutils.dumps(DEFAULT_S_TO_S_CONFIG_DICT)

    DEFAULT_SSLVPN_CONFIG_DICT = {   u'description': u'Creates new vpn service - ike + ipsec + vpn service + site-site connection(s)',
    u'heat_template_version': u'2013-05-23',
    u'parameters': {   u'ClientAddressPoolCidr': {   u'description': u'Pool from which the ip address is allocated to all connected clients',
                                                     u'type': u'string'},
                       u'RouterId': {   u'description': u'Router ID',
                                        u'type': u'string'},
                       u'ServiceDescription': {   u'description': u'fip;tunnel_local-cidr',
                                                  u'type': u'string'},
                       u'Subnet': {   u'description': u'Subnet id on which vpn service is launched',
                                      u'type': u'string'}},
    u'resources': {   u'IKEPolicy': {   u'properties': {   u'auth_algorithm': u'sha1',
                                                           u'encryption_algorithm': u'3des',
                                                           u'ike_version': u'v1',
                                                           u'lifetime': {   u'units': u'seconds',
                                                                            u'value': 3600},
                                                           u'name': u'IKEPolicy',
                                                           u'pfs': u'group5',
                                                           u'phase1_negotiation_mode': u'main'},
                                        u'type': u'OS::Neutron::IKEPolicy'},
                      u'IPsecPolicy': {   u'properties': {   u'auth_algorithm': u'sha1',
                                                             u'encapsulation_mode': u'tunnel',
                                                             u'encryption_algorithm': u'3des',
                                                             u'lifetime': {   u'units': u'seconds',
                                                                              u'value': 3600},
                                                             u'name': u'IPsecPolicy',
                                                             u'pfs': u'group5',
                                                             u'transform_protocol': u'esp'},
                                          u'type': u'OS::Neutron::IPsecPolicy'},
                      u'SSLVPNConnection': {   u'properties': {   u'admin_state_up': True,
                                                                  u'client_address_pool_cidr': {   u'get_param': u'ClientAddressPoolCidr'},
                                                                  u'credential_id': u'',
                                                                  u'name': u'vtun0',
                                                                  u'vpnservice_id': {   u'get_resource': u'VPNService'}},
                                               u'type': u'OS::Neutron::SSLVPNConnection'},
                      u'VPNService': {   u'properties': {   u'admin_state_up': True,
                                                            u'description': {   u'get_param': u'ServiceDescription'},
                                                            u'name': u'VPNService',
                                                            u'router_id': {   u'get_param': u'RouterId'},
                                                            u'subnet_id': {   u'get_param': u'Subnet'}},
                                         u'type': u'OS::Neutron::VPNService'},
                      u'site_to_site_connection1': {   u'properties': {   u'admin_state_up': True,
                                                                          u'dpd': {   u'actions': u'hold',
                                                                                      u'interval': 30,
                                                                                      u'timeout': 120},
                                                                          u'ikepolicy_id': {   u'get_resource': u'IKEPolicy'},
                                                                          u'initiator': u'bi-directional',
                                                                          u'ipsecpolicy_id': {   u'get_resource': u'IPsecPolicy'},
                                                                          u'mtu': 1500,
                                                                          u'name': u'site_to_site_connection1',
                                                                          u'peer_address': u'192.168.104.212',
                                                                          u'peer_cidrs': [   u'78.0.0.0/24'],
                                                                          u'peer_id': u'54.0.0.2',
                                                                          u'psk': u'secret',
                                                                          u'vpnservice_id': {   u'get_resource': u'VPNService'}},
                                                       u'type': u'OS::Neutron::IPsecSiteConnection'}}}
    
    DEFAULT_SSLVPN_CONFIG = jsonutils.dumps(DEFAULT_SSLVPN_CONFIG_DICT)
    SERVICE_PROFILE_VENDOR = 'oneconvergence_haproxy'

    def setUp(self):
        oneconvergence_driver_opts = [
            config.cfg.StrOpt('svc_management_ptg_name',
                              default='svc_management_ptg',
                              help=_("Name of the PTG that is associated with the "
                                     "service management network")),
            config.cfg.StrOpt('heat_uri',
                              default='http://localhost:8004/v1',
                              help=_("Heat API server address to instantiate services "
                                     "specified in the service chain.")),
            config.cfg.IntOpt('stack_action_wait_time',
                              default=60,
                              help=_("Seconds to wait for pending stack operation "
                                     "to complete")),
        ]
        config.cfg.CONF.register_opts(oneconvergence_driver_opts,
                                      "oneconvergence_node_driver")
        config.cfg.CONF.set_override('stack_action_wait_time',
                                     STACK_ACTION_WAIT_TIME,
                                     group='oneconvergence_node_driver')
        config.cfg.CONF.set_override('auth_uri',
                                     "http://localhost:5000/v2.0",
                                     group='keystone_authtoken')
        config.cfg.CONF.set_override('admin_user',
                                     "neutron",
                                     group='keystone_authtoken')
        config.cfg.CONF.set_override('admin_password',
                                     "services",
                                     group='keystone_authtoken')
        config.cfg.CONF.set_override('admin_tenant_name',
                                     "services",
                                     group='keystone_authtoken')
        config.cfg.CONF.set_override('auth_protocol',
                                     "https",
                                     group='keystone_authtoken')
        config.cfg.CONF.set_override('auth_host',
                                     "localhost",
                                     group='keystone_authtoken')
        config.cfg.CONF.set_override('auth_port',
                                     '5000',
                                     group='keystone_authtoken')
        config.cfg.CONF.set_override(
            'extension_drivers', ['proxy_group'], group='group_policy')
        config.cfg.CONF.set_override('allow_overlapping_ips', True)
        mock.patch(heatclient.__name__ + ".client.Client",
                   new=MockHeatClient).start()
        mock.patch('keystoneclient.v2_0.client').start()
        mock.patch('keystoneclient.v3.client').start()
        #mock.patch('gbpservice.neutron.services.servicechain.plugins.ncp.'
        #           'node_drivers.oc_service_manager_client.SvcManagerClientApi',
        #           new=MockServiceManagerClient).start()
        # For Unit testing OC driver, RMD or APIC mapping should not matter
        # Revisit(Magesh): Need to configure chain owner
        config.cfg.CONF.set_override('default_proxy_ip_pool', "192.166.1.0/16",
                                     group="group_policy_implicit_policy")
        super(OneConvergenceServiceNodeDriverTestCase, self).setUp(
            node_drivers=['oneconvergence_node_driver'],
            node_plumber='stitching_plumber')
        config.cfg.CONF.set_override('remote_vpn_client_pool_cidr',
                                     '166.168.254.0/24',
                                     group='oneconvergence_node_driver')
        self._create_service_management_group()

    def _create_network(self, fmt, name, admin_state_up, **kwargs):
        """Override the routine for allowing the router:external attribute."""
        # attributes containing a colon should be passed with
        # a double underscore
        new_args = dict(itertools.izip(map(lambda x: x.replace('__', ':'),
                                           kwargs),
                                       kwargs.values()))
        arg_list = new_args.pop('arg_list', ()) + (external_net.EXTERNAL,)
        return super(OneConvergenceServiceNodeDriverTestCase, self)._create_network(
            fmt, name, admin_state_up, arg_list=arg_list, **new_args)

    def test_manager_initialized(self):
        mgr = self.plugin.driver_manager
        self.assertIsInstance(mgr.ordered_drivers[0].obj,
                              heat_node_driver.HeatNodeDriver)
        for driver in mgr.ordered_drivers:
            self.assertTrue(driver.obj.initialized)

    def _create_profiled_servicechain_node(
            self, service_type=constants.LOADBALANCER, shared_profile=False,
            profile_tenant_id=None, vendor=SERVICE_PROFILE_VENDOR, **kwargs):
        prof = self.create_service_profile(
            service_type=service_type,
            shared=shared_profile,
            vendor=vendor,
            tenant_id=profile_tenant_id or self._tenant_id)['service_profile']
        return self.create_servicechain_node(
            service_profile_id=prof['id'], **kwargs)

    def _create_allow_rule(self):
        action = self.create_policy_action(action_type='ALLOW',
                                           #tenant_id='admin_id'
                                           )
        classifier = self.create_policy_classifier(
            port_range=80, protocol='tcp', direction='bi',
            #tenant_id='admin_id'
            )
        rule = self.create_policy_rule(
            policy_actions=[action['policy_action']['id']],
            #tenant_id='admin_id',
            policy_classifier_id=classifier['policy_classifier']['id'])
        return rule

    def _create_allow_prs(self):
        rule = self._create_allow_rule()['policy_rule']
        prs = self.create_policy_rule_set(#tenant_id='admin_id',
                                          policy_rules=[rule['id']])
        return prs

    def _create_nat_pool_and_es(self, cidr, es_name, routes=None):
        with self.network(router__external=True, shared=True, tenant_id='admin_id') as net:
            with self.subnet(cidr=cidr, network=net) as sub:
                if not routes:
                    routes = [{'destination': '172.0.0.0/22', 'nexthop': None}]
                ext_segment = self.create_external_segment(
                    #tenant_id='admin_id',
                    shared=True,
                    name=es_name,
                    external_routes=routes,
                    subnet_id=sub['subnet']['id'])['external_segment']
                nat_pool = self.create_nat_pool(
                    #tenant_id='admin_id',
                    ip_version='4', ip_pool=cidr,
                    external_segment_id=ext_segment['id'],
                    expected_res_status=webob.exc.HTTPCreated.code)['nat_pool']
                return nat_pool, ext_segment['id']
    def _create_external_policy_with_nat_pool(self, consumed_prs, routes=None):
        # Have UT issues with two external networks
        nat_pool, es_id = self._create_nat_pool_and_es("222.168.1.0/24",
                                                       "default", 
                                                       routes=routes)
        return self.create_external_policy(
            name='svc_mgmt_external_policy',
            #tenant_id='admin_id',
            external_segments=[es_id],
            consumed_policy_rule_sets={})

    def _create_service_management_group(self):
        prs = self._create_allow_prs()['policy_rule_set']
        ep = self._create_external_policy_with_nat_pool(prs['id'])
        nsp = self.create_network_service_policy(
            #tenant_id='admin_id',
            shared=True,
            network_service_params=[
                {"type": "ip_pool", "value": "nat_pool",
                 "name": "fip"}])['network_service_policy']
        l3p = self.create_l3_policy(
            external_segments={ep['external_policy']['external_segments'][0]: []},
            ip_pool='20.0.0.0/24',
            shared=True,
            #tenant_id='admin_id'
            )['l3_policy']
        l2p = self.create_l2_policy(l3_policy_id=l3p['id'],
                                    shared=True,
                                    #tenant_id='admin_id'
                                    )['l2_policy']
        svc_mgmt = self.create_policy_target_group(
            provided_policy_rule_sets={},
            name='svc_management_ptg',
            network_service_policy_id=nsp['id'],
            l2_policy_id=l2p['id'],
            shared=True
            #tenant_id='admin_id'
            )['policy_target_group']

    def create_policy_target_group(self, **kwargs):
        if not kwargs.get('network_service_policy_id'):
            nsp = self.create_network_service_policy(
            #tenant_id='admin_id',
            network_service_params=[
                {"type": "ip_single", "value": "self_subnet",
                 "name": "vip_ip"}])['network_service_policy']
            kwargs['network_service_policy_id'] = nsp['id']
        return self._create_resource('policy_target_group', **kwargs)
            

    def test_context_no_management(self):
        pass

    def test_context_attributes(self):
        pass

    def test_multiple_nodes_update(self):
        pass

    def test_context_relevant_specs(self):
        pass

class TestServiceChainInstance(OneConvergenceServiceNodeDriverTestCase):

    def _get_node_instance_stacks(self, sc_node_id):
        context = neutron_context.get_admin_context()
        with context.session.begin(subtransactions=True):
            return (context.session.query(
                        heat_node_driver.ServiceNodeInstanceStack).
                    filter_by(sc_node_id=sc_node_id).
                    all())

    def test_invalid_service_type_rejected(self):
        node_used = self._create_profiled_servicechain_node(
            service_type="test")['servicechain_node']
        spec_used = self.create_servicechain_spec(
            nodes=[node_used['id']])['servicechain_spec']
        provider = self.create_policy_target_group()['policy_target_group']
        classifier = self.create_policy_classifier()['policy_classifier']
        res = self.create_servicechain_instance(
            provider_ptg_id=provider['id'],
            classifier_id=classifier['id'],
            servicechain_specs=[spec_used['id']],
            expected_res_status=webob.exc.HTTPBadRequest.code)
        self.assertEqual('NoDriverAvailableForAction',
                         res['NeutronError']['type'])

    def _create_allow_rule(self):
        action = self.create_policy_action(action_type='ALLOW',
                                           #tenant_id='admin_id'
                                           )
        classifier = self.create_policy_classifier(
            port_range=80, protocol='tcp', direction='bi',
            #tenant_id='admin_id'
            )
        rule = self.create_policy_rule(
            policy_actions=[action['policy_action']['id']],
            #tenant_id='admin_id',
            policy_classifier_id=classifier['policy_classifier']['id'])
        return rule

    def _create_allow_prs(self):
        rule = self._create_allow_rule()['policy_rule']
        prs = self.create_policy_rule_set(#tenant_id='admin_id',
                                          policy_rules=[rule['id']])
        return prs

    def _create_chain_with_nodes(self, node_ids=None):
        node_ids = node_ids or []
        spec = self.create_servicechain_spec(
            nodes=node_ids,
            expected_res_status=201)['servicechain_spec']
        prs = self._create_redirect_prs(spec['id'])['policy_rule_set']
        nsp = self.create_network_service_policy(
            #tenant_id='admin_id',
            network_service_params=[
                {"type": "ip_single", "value": "self_subnet",
                 "name": "vip_ip"}])['network_service_policy']
        provider = self.create_policy_target_group(
            provided_policy_rule_sets={prs['id']: ''},
            network_service_policy_id=nsp['id'])['policy_target_group']
        consumer = self.create_policy_target_group(
            consumed_policy_rule_sets={prs['id']: ''})['policy_target_group']
        return provider, consumer, prs

    def _create_simple_service_chain(self, number_of_nodes=1):
        node_ids = []
        for x in xrange(number_of_nodes):
            node_ids.append(self._create_profiled_servicechain_node(
                service_type='LOADBALANCER',
                config=self.DEFAULT_LB_CONFIG,
                expected_res_status=201)['servicechain_node']['id'])

        return self._create_chain_with_nodes(node_ids)

    def _create_profiled_servicechain_node(
            self, service_type=constants.LOADBALANCER, shared_profile=False,
            profile_tenant_id=None, profile_id=None, **kwargs):
        if not profile_id:
            prof = self.create_service_profile(
                service_type=service_type,
                shared=shared_profile,
                vendor=SUPPORTED_SERVICE_VENDOR_MAPPING[service_type],
                tenant_id=profile_tenant_id or self._tenant_id)[
                                                    'service_profile']
        else:
            prof = self.get_service_profile(profile_id)

        service_config = kwargs.get('config')
        if not service_config or service_config == '{}':
            if service_type == constants.FIREWALL:
                kwargs['config'] = self.DEFAULT_FW_CONFIG
            elif service_type == constants.VPN:
                if kwargs.get("site_to_site"):
                    del kwargs['site_to_site']
                    kwargs['config'] = self.DEFAULT_S_TO_S_CONFIG
                else:
                    kwargs['config'] = self.DEFAULT_SSLVPN_CONFIG
            else:
                kwargs['config'] = self.DEFAULT_LB_CONFIG
        return self.create_servicechain_node(
            service_profile_id=prof['id'], **kwargs)

    def test_node_create(self):
        with mock.patch.object(heatClient.HeatClient,
                               'create') as stack_create:
            stack_create.return_value = {'stack': {
                                        'id': uuidutils.generate_uuid()}}
            #get_existing_service_for_sharing = mock.patch('gbpservice.neutron.services.servicechain.plugins.ncp.'
            #      'node_drivers.oc_service_manager_client.SvcManagerClientApi.get_existing_service_for_sharing').start()
            #get_existing_service_for_sharing.return_value = None
            provider, consumer, prs = self._create_simple_service_chain()
            expected_lb_config = copy.deepcopy(self.DEFAULT_LB_CONFIG_DICT)

            expected_pool_name = "%s%s%s" %(
                expected_lb_config['Resources']['test_pool'][
                    'Properties']['name'],
                "-",
                provider['name'])
            expected_lb_config['Resources']['test_pool'][
                'Properties']['name'] = expected_pool_name
            
            expected_vip_name = "%s%s%s" %(
                expected_lb_config['Resources']['test_pool'][
                    'Properties']['vip']['name'],
                "-",
                provider['name'])
            expected_lb_config['Resources']['test_pool'][
                'Properties']['vip']['name'] = expected_vip_name

            expected_stack_name = mock.ANY
            expected_stack_params = mock.ANY
            stack_create.assert_called_once_with(
                    expected_stack_name,
                    expected_lb_config,
                    expected_stack_params)

    def _get_pool_member_resource_dict(self, port):
        member_ip = port['fixed_ips'][0]['ip_address']
        member_name = 'mem-' + member_ip
        member = {member_name: {
                        'Type': 'OS::Neutron::PoolMember',
                        'Properties': {
                            'protocol_port': 80,
                            'admin_state_up': True,
                            'pool_id': {'Ref': u'test_pool'},
                            'weight': 1,
                            'address': member_ip
                        }
                    }
                  }
        return member

    def _create_policy_target_port(self, policy_target_group_id):
        pt = self.create_policy_target(
                policy_target_group_id=policy_target_group_id)['policy_target']
        req = self.new_show_request('ports', pt['port_id'], fmt=self.fmt)
        port = self.deserialize(self.fmt,
                                req.get_response(self.api))['port']
        return (pt, port)

    def _create_external_policy(self, consumed_prs, routes=None):
        with self.network(router__external=True, shared=True) as net:
            with self.subnet(cidr='192.168.0.0/24', network=net) as sub:
                if not routes:
                    routes = [{'destination': '172.0.0.0/22', 'nexthop': None}]
                self.create_external_segment(
                    shared=True,
                    name="default",
                    external_routes=routes,
                    subnet_id=sub['subnet']['id'])['external_segment']
                return self.create_external_policy(
                    consumed_policy_rule_sets={consumed_prs: ''})

    # TODO(Magesh): Add UTs for dynamic lb member add -> Now the member
    # has to be added after the provider has prs set
    def _test_lb_node_create(self, consumer_external=False):
        with mock.patch.object(heatClient.HeatClient,
                               'create') as stack_create:
            stack_create.return_value = {'stack': {
                                        'id': uuidutils.generate_uuid()}}

            node_id = self._create_profiled_servicechain_node(
                service_type=constants.LOADBALANCER)['servicechain_node']['id']
            spec = self.create_servicechain_spec(
                nodes=[node_id],
                expected_res_status=201)['servicechain_spec']

            prs = self._create_redirect_prs(spec['id'])['policy_rule_set']
            provider = self.create_policy_target_group()['policy_target_group']

            _, port1 = self._create_policy_target_port(provider['id'])
            _, port2 = self._create_policy_target_port(provider['id'])

            self.update_policy_target_group(
                provider['id'], provided_policy_rule_sets={prs['id']: ''})

            if consumer_external:
                eps = self._list("external_policies")['external_policies']
                consumed_policy_rule_sets_list = eps[0]['consumed_policy_rule_sets']
                consumed_policy_rule_sets_dict = {}
                for prs_id in consumed_policy_rule_sets_list:
                    consumed_policy_rule_sets_dict[prs_id] = ""
                consumed_policy_rule_sets_dict[prs['id']] = ""
                self.update_external_policy(
                    eps[0]['id'],
                    consumed_policy_rule_sets=consumed_policy_rule_sets_dict)
                #self._create_external_policy(prs['id'])
            else:
                self.create_policy_target_group(
                    consumed_policy_rule_sets={prs['id']: ''})

            created_stacks_map = self._get_node_instance_stacks(node_id)
            self.assertEqual(1, len(created_stacks_map))

            pool_member1 = self._get_pool_member_resource_dict(port1)
            pool_member2 = self._get_pool_member_resource_dict(port2)

            # Instantiating the chain invokes stack create
            expected_stack_template = copy.deepcopy(
                                    self.DEFAULT_LB_CONFIG_DICT)
            expected_stack_template['Resources'].update(pool_member1)
            expected_stack_template['Resources'].update(pool_member2)

            expected_pool_name = "%s%s%s" %(
                expected_stack_template['Resources']['test_pool'][
                    'Properties']['name'],
                "-",
                provider['name'])
            expected_stack_template['Resources']['test_pool'][
                'Properties']['name'] = expected_pool_name

            expected_vip_name = "%s%s%s" %(
                expected_stack_template['Resources']['test_pool'][
                    'Properties']['vip']['name'],
                "-",
                provider['name'])
            expected_stack_template['Resources']['test_pool'][
                'Properties']['vip']['name'] = expected_vip_name

            expected_stack_name = mock.ANY
            # TODO(Magesh): Verify expected_stack_params with IP address from
            # Network Service Policy
            expected_stack_params = {}
            call_stack_name, call_stack_template, call_stack_params = (
                stack_create.call_args_list[0][0])
            self.assertEqual(expected_stack_template, call_stack_template)
            return (expected_stack_template, provider,
                    created_stacks_map[0].stack_id, prs['id'])

    def _test_lb_dynamic_pool_member_add(self, expected_stack_template,
                                         provider, stack_id):
        with mock.patch.object(heatClient.HeatClient,
                           'update') as stack_update:
            stack_update.return_value = {'stack': {'id': stack_id}}

            # Creating PT will update the node, thereby adding the PT as an
            # LB Pool Member using heat stack
            pt, port = self._create_policy_target_port(provider['id'])
            pool_member = self._get_pool_member_resource_dict(port)
            expected_stack_template['Resources'].update(pool_member)
            expected_stack_id = stack_id
            expected_stack_params = {}
            call_stack_name, call_stack_template, call_stack_params = (
                stack_update.call_args_list[0][0])
            self.assertEqual(expected_stack_template, call_stack_template)
            '''
            stack_update.assert_called_once_with(
                expected_stack_id,
                expected_stack_template,
                expected_stack_params)
            '''
            return (pt, pool_member)

    def _test_dynamic_lb_pool_member_delete(self, pt, pool_member,
                                            expected_stack_template,
                                            stack_id):
        # Deleting PT will update the node, thereby removing the Pool
        # Member from heat stack
        with mock.patch.object(heatClient.HeatClient,
                           'update') as stack_update:
            self.delete_policy_target(pt['id'])

            template_on_delete_pt = copy.deepcopy(expected_stack_template)
            template_on_delete_pt['Resources'].pop(pool_member.keys()[0])
            expected_stack_id = stack_id
            expected_stack_params = {}
            stack_update.assert_called_once_with(
                    expected_stack_id,
                    template_on_delete_pt,
                    expected_stack_params)

    def _test_node_cleanup(self, ptg, stack_id, prs_id=None):
        with mock.patch.object(heatClient.HeatClient,
                               'delete') as stack_delete:
            eps = self._list("external_policies")['external_policies']
            consumed_policy_rule_sets_list = eps[0]['consumed_policy_rule_sets']
            consumed_policy_rule_sets_dict = {}
            for prs_id in consumed_policy_rule_sets_list:
                consumed_policy_rule_sets_dict[prs_id] = ""
            if prs_id:
                del consumed_policy_rule_sets_dict[prs_id]
            self.update_external_policy(
                eps[0]['id'],
                consumed_policy_rule_sets=consumed_policy_rule_sets_dict)
            self.update_policy_target_group(
                ptg['id'],
                consumed_policy_rule_sets={},
                provided_policy_rule_sets={},
                expected_res_status=200)
            self.delete_policy_target_group(ptg['id'], expected_res_status=204)
            stack_delete.assert_called_once_with(mock.ANY)
            stack_delete.assert_called_once_with(stack_id)

    def test_lb_node_operations(self):
        expected_stack_template, provider, stack_id, prs_id = (
            self._test_lb_node_create())
        pt, pool_member = self._test_lb_dynamic_pool_member_add(
            expected_stack_template, provider, stack_id)
        self._test_dynamic_lb_pool_member_delete(
            pt, pool_member, expected_stack_template, stack_id)
        self._test_node_cleanup(provider, stack_id)

    def test_lb_redirect_from_external(self):
        expected_stack_template, provider, stack_id, prs_id = (
                self._test_lb_node_create(consumer_external=True))
        pt, pool_member = self._test_lb_dynamic_pool_member_add(
                expected_stack_template, provider, stack_id)
        self._test_dynamic_lb_pool_member_delete(
                pt, pool_member, expected_stack_template, stack_id)
        self._test_node_cleanup(provider, stack_id, prs_id=prs_id)

    def _create_sslvpn_redirect_ruleset(self, classifier_port,
                                        classifier_protocol):
        node_id = self._create_profiled_servicechain_node(
                service_type=constants.VPN)['servicechain_node']['id']
        spec = self.create_servicechain_spec(
            nodes=[node_id],
            expected_res_status=201)['servicechain_spec']
        action = self.create_policy_action(action_type='REDIRECT',
                                           action_value=spec['id'])
        classifier = self.create_policy_classifier(
            port_range=classifier_port, protocol=classifier_protocol,
            direction='bi')
        rule = self.create_policy_rule(
            policy_actions=[action['policy_action']['id']],
            policy_classifier_id=classifier['policy_classifier']['id'])
        rule = rule['policy_rule']
        prs = self.create_policy_rule_set(policy_rules=[rule['id']])
        return (prs['policy_rule_set'], node_id)

    def _create_s_to_s_vpn_redirect_ruleset(self, classifier_port,
                                            classifier_protocol):
        node_id = self._create_profiled_servicechain_node(
                service_type=constants.VPN,
                site_to_site=True)['servicechain_node']['id']
        spec = self.create_servicechain_spec(
            nodes=[node_id],
            expected_res_status=201)['servicechain_spec']
        action = self.create_policy_action(action_type='REDIRECT',
                                           action_value=spec['id'])
        classifier = self.create_policy_classifier(
            port_range=classifier_port, protocol=classifier_protocol,
            direction='bi')
        rule = self.create_policy_rule(
            policy_actions=[action['policy_action']['id']],
            policy_classifier_id=classifier['policy_classifier']['id'])
        rule = rule['policy_rule']
        prs = self.create_policy_rule_set(policy_rules=[rule['id']])
        return (prs['policy_rule_set'], node_id)

    def _create_fwredirect_ruleset(self, classifier_port, classifier_protocol):
        node_id = self._create_profiled_servicechain_node(
                service_type=constants.FIREWALL)['servicechain_node']['id']
        spec = self.create_servicechain_spec(
            nodes=[node_id],
            expected_res_status=201)['servicechain_spec']
        action = self.create_policy_action(action_type='REDIRECT',
                                           action_value=spec['id'])
        classifier = self.create_policy_classifier(
            port_range=classifier_port, protocol=classifier_protocol,
            direction='bi')
        rule = self.create_policy_rule(
            policy_actions=[action['policy_action']['id']],
            policy_classifier_id=classifier['policy_classifier']['id'])
        rule = rule['policy_rule']
        prs = self.create_policy_rule_set(policy_rules=[rule['id']])
        return (prs['policy_rule_set'], node_id)

    def _get_ptg_cidr(self, ptg):
        req = self.new_show_request(
                'subnets', ptg['subnets'][0], fmt=self.fmt)
        ptg_subnet = self.deserialize(
                self.fmt, req.get_response(self.api))['subnet']
        return ptg_subnet['cidr']

    def test_fw_node_east_west(self):
        classifier_port = '66'
        classifier_protocol = 'udp'
        with mock.patch.object(heatClient.HeatClient,
                               'create') as stack_create:
            stack_create.return_value = {'stack': {
                                        'id': uuidutils.generate_uuid()}}
            prs, node_id = self._create_fwredirect_ruleset(
                                    classifier_port, classifier_protocol)
            
            consumer = self.create_policy_target_group(
                consumed_policy_rule_sets={prs['id']: ''})[
                                                'policy_target_group']
            # TODO(Magesh): Add a test for consumer add later on
            provider = self.create_policy_target_group(
                provided_policy_rule_sets={prs['id']: ''})[
                                                'policy_target_group']

            created_stacks_map = self._get_node_instance_stacks(node_id)
            self.assertEqual(1, len(created_stacks_map))
            stack_id = created_stacks_map[0].stack_id

            provider_cidr = self._get_ptg_cidr(provider)
            consumer_cidr = self._get_ptg_cidr(consumer)
            # TODO(Magesh): Add an UT for PTG in rule source and destination 

            expected_stack_template = copy.deepcopy(
                                        self.DEFAULT_FW_CONFIG_DICT)
            #expected_stack_template['resources'].update(fw_rule)
            description = expected_stack_template['resources'][
                'test_fw']['properties'].pop('description')
            existing_fw_policy_name = expected_stack_template['resources'][
                'test_fw_policy']['properties']['name']
            expected_fw_policy_name = "%s%s%s" %(
                existing_fw_policy_name, "-", provider['name'])
            existing_fw_name = expected_stack_template['resources'][
                'test_fw']['properties']['name']
            expected_fw_name = "%s%s%s" %(
                existing_fw_name, "-", provider['name'])
            expected_stack_template['resources'][
                'test_fw_policy']['properties']['name'] = existing_fw_policy_name
            expected_stack_template['resources'][
                'test_fw']['properties']['name'] = expected_fw_name
            expected_stack_template['resources'][
                'test_fw_policy']['properties']['name'] = expected_fw_policy_name
            rule1_name = "%s_%s_%s" %("node_driver_rule", consumer['id'][:16], 1) 
            rule2_name = "%s_%s_%s" %("node_driver_rule", consumer['id'][:16], 2) 
            expected_stack_template['resources'][rule1_name] = (
                copy.deepcopy(expected_stack_template['resources']['Rule_1']))
            expected_stack_template['resources'][
                rule1_name]['properties']['destination_ip_address'] = provider_cidr
            expected_stack_template['resources'][rule2_name] = (
                copy.deepcopy(expected_stack_template['resources']['Rule_2']))
            expected_stack_template['resources'][
                rule2_name]['properties']['destination_ip_address'] = provider_cidr
            del expected_stack_template['resources']['Rule_1']
            del expected_stack_template['resources']['Rule_2']
            expected_stack_template['resources'][
                'test_fw_policy']['properties']['firewall_rules'] = (
                    [{'get_resource': rule1_name},
                     {'get_resource': rule2_name}])
            expected_stack_template['resources'][
                rule1_name]['properties']['source_ip_address'] = consumer_cidr
            expected_stack_template['resources'][
                rule2_name]['properties']['source_ip_address'] = consumer_cidr
            expected_stack_name = mock.ANY
            expected_stack_params = {}
            
            expected_stack_id = stack_id
            expected_stack_params = {}
            call_stack_name, call_stack_template, call_stack_params = (
                stack_create.call_args_list[0][0])
            called_description = call_stack_template['resources'][
                'test_fw']['properties'].pop('description')
            self.assertEqual(expected_stack_template, call_stack_template)
            
            '''
            stack_create.assert_called_once_with(
                    expected_stack_name,
                    expected_stack_template,
                    expected_stack_params)
            '''

            self._test_node_cleanup(provider, stack_id)

    def _get_firewall_rule_dict(self, rule_name, protocol, port, provider_cidr,
                                consumer_cidr):
        if provider_cidr and consumer_cidr:
            fw_rule = {rule_name: {'type': "OS::Neutron::FirewallRule",
                                   'properties': {
                                       "protocol": protocol,
                                       "enabled": True,
                                       "destination_port": port,
                                       "action": "allow",
                                       "destination_ip_address": provider_cidr,
                                       "source_ip_address": consumer_cidr
                                   }
                                   }
                       }
            return fw_rule
        return {}

    def _test_fw_node_north_south(self, consumer_cidrs):
        classifier_port = '66'
        classifier_protocol = 'udp'
        with mock.patch.object(heatClient.HeatClient,
                               'create') as stack_create:
            stack_create.return_value = {'stack': {
                                        'id': uuidutils.generate_uuid()}}
            prs, node_id = self._create_fwredirect_ruleset(
                                    classifier_port, classifier_protocol)

            eps = self._list("external_policies")['external_policies']
            consumed_policy_rule_sets_list = eps[0]['consumed_policy_rule_sets']
            consumed_policy_rule_sets_dict = {}
            for prs_id in consumed_policy_rule_sets_list:
                consumed_policy_rule_sets_dict[prs_id] = ""
            consumed_policy_rule_sets_dict[prs['id']] = ""
            self.update_external_policy(
                eps[0]['id'],
                consumed_policy_rule_sets=consumed_policy_rule_sets_dict)

            provider = self.create_policy_target_group(
                provided_policy_rule_sets={prs['id']: ''})[
                                                'policy_target_group']

            #routes = []
            #for consumer_cidr in consumer_cidrs:
            #    routes.append({'destination': consumer_cidr, 'nexthop': None})
            
            #self._create_external_policy(
            #            prs['id'], routes=routes)['external_policy']

            created_stacks_map = self._get_node_instance_stacks(node_id)
            self.assertEqual(1, len(created_stacks_map))
            stack_id = created_stacks_map[0].stack_id

            expected_stack_template = copy.deepcopy(
                                        self.DEFAULT_FW_CONFIG_DICT)
            expected_stack_template['resources']['test_fw_policy'][
                                        'properties']['firewall_rules'] = []
            provider_cidr = self._get_ptg_cidr(provider)

            expected_stack_template = copy.deepcopy(
                                        self.DEFAULT_FW_CONFIG_DICT)
            #expected_stack_template['resources'].update(fw_rule)
            description = expected_stack_template['resources'][
                'test_fw']['properties'].pop('description')
            existing_fw_policy_name = expected_stack_template['resources'][
                'test_fw_policy']['properties']['name']
            expected_fw_policy_name = "%s%s%s" %(
                existing_fw_policy_name, "-", provider['name'])
            existing_fw_name = expected_stack_template['resources'][
                'test_fw']['properties']['name']
            expected_fw_name = "%s%s%s" %(
                existing_fw_name, "-", provider['name'])
            expected_stack_template['resources'][
                'test_fw_policy']['properties']['name'] = existing_fw_policy_name
            expected_stack_template['resources'][
                'test_fw']['properties']['name'] = expected_fw_name
            expected_stack_template['resources'][
                'test_fw_policy']['properties']['name'] = expected_fw_policy_name
            rule1_name = "%s_%s_%s" %("node_driver_rule", eps[0]['id'][:16], 1) 
            rule2_name = "%s_%s_%s" %("node_driver_rule", eps[0]['id'][:16], 2) 
            expected_stack_template['resources'][rule1_name] = (
                copy.deepcopy(expected_stack_template['resources']['Rule_1']))
            expected_stack_template['resources'][
                rule1_name]['properties']['destination_ip_address'] = provider_cidr
            expected_stack_template['resources'][rule2_name] = (
                copy.deepcopy(expected_stack_template['resources']['Rule_2']))
            expected_stack_template['resources'][
                rule2_name]['properties']['destination_ip_address'] = provider_cidr
            del expected_stack_template['resources']['Rule_1']
            del expected_stack_template['resources']['Rule_2']
            expected_stack_template['resources'][
                'test_fw_policy']['properties']['firewall_rules'] = (
                    [{'get_resource': rule1_name},
                     {'get_resource': rule2_name}])

            expected_stack_name = mock.ANY
            expected_stack_params = {}
            
            expected_stack_id = stack_id
            expected_stack_params = {}
            call_stack_name, call_stack_template, call_stack_params = (
                stack_create.call_args_list[0][0])
            called_description = call_stack_template['resources'][
                'test_fw']['properties'].pop('description')
            self.assertEqual(expected_stack_template, call_stack_template)

            self._test_node_cleanup(provider, stack_id, prs_id=prs['id'])

    def test_fw_node_north_south_single_external_cidr(self):
        self._test_fw_node_north_south(['172.0.0.0/22'])

    def test_fw_node_north_south_multiple_external_cidr(self):
        self._test_fw_node_north_south(['172.0.0.0/22', '20.0.0.0/16'])

    def test_fw_node_update(self):
        with mock.patch.object(heatClient.HeatClient,
                               'create') as stack_create:
            stack_create.return_value = {'stack': {
                                        'id': uuidutils.generate_uuid()}}
            prof = self.create_service_profile(
                        service_type=constants.FIREWALL,
                        vendor=SUPPORTED_SERVICE_VENDOR_MAPPING[constants.FIREWALL])['service_profile']

            node = self.create_servicechain_node(
                        service_profile_id=prof['id'],
                        config=self.DEFAULT_FW_CONFIG,
                        expected_res_status=201)['servicechain_node']

            self._create_chain_with_nodes(node_ids=[node['id']])
            with mock.patch.object(heatClient.HeatClient,
                                   'update') as stack_update:
                self.update_servicechain_node(
                                        node['id'],
                                        name='newname',
                                        expected_res_status=200)
                # Name update should not update stack ??
                # Try updating config and see its reflected
                stack_update.assert_called_once_with(
                                    mock.ANY, mock.ANY, mock.ANY)

    def test_sslvpn_node_update(self):
        with mock.patch.object(heatClient.HeatClient,
                               'create') as stack_create:
            stack_create.return_value = {'stack': {
                                        'id': uuidutils.generate_uuid()}}
            prof = self.create_service_profile(
                        service_type=constants.VPN,
                        vendor=SUPPORTED_SERVICE_VENDOR_MAPPING[constants.VPN])['service_profile']

            node = self.create_servicechain_node(
                        service_profile_id=prof['id'],
                        config=self.DEFAULT_SSLVPN_CONFIG,
                        expected_res_status=201)['servicechain_node']

            self._create_chain_with_nodes(node_ids=[node['id']])
            with mock.patch.object(heatClient.HeatClient,
                                   'update') as stack_update:
                self.update_servicechain_node(
                                        node['id'],
                                        name='newname',
                                        expected_res_status=200)
                # Name update should not update stack ??
                # Try updating config and see its reflected
                stack_update.assert_called_once_with(
                                    mock.ANY, mock.ANY, mock.ANY)

    def _test_sslvpn(self):
        classifier_port = '66'
        classifier_protocol = 'udp'
        with mock.patch.object(heatClient.HeatClient,
                               'create') as stack_create:
            stack_create.return_value = {'stack': {
                                        'id': uuidutils.generate_uuid()}}
            prs, node_id = self._create_sslvpn_redirect_ruleset(
                classifier_port, classifier_protocol)

            eps = self._list("external_policies")['external_policies']
            consumed_policy_rule_sets_list = eps[0]['consumed_policy_rule_sets']
            consumed_policy_rule_sets_dict = {}
            for prs_id in consumed_policy_rule_sets_list:
                consumed_policy_rule_sets_dict[prs_id] = ""
            consumed_policy_rule_sets_dict[prs['id']] = ""
            self.update_external_policy(
                eps[0]['id'],
                consumed_policy_rule_sets=consumed_policy_rule_sets_dict)

            provider = self.create_policy_target_group(
                provided_policy_rule_sets={prs['id']: ''})[
                                                'policy_target_group']

            created_stacks_map = self._get_node_instance_stacks(node_id)
            self.assertEqual(1, len(created_stacks_map))
            stack_id = created_stacks_map[0].stack_id

            expected_stack_template = copy.deepcopy(
                self.DEFAULT_SSLVPN_CONFIG_DICT)
            provider_cidr = self._get_ptg_cidr(provider)

            expected_stack_template = copy.deepcopy(
                                        self.DEFAULT_SSLVPN_CONFIG_DICT)

            call_stack_name, call_stack_template, call_stack_params = (
                stack_create.call_args_list[0][0])
            '''
            {u'ClientAddressPoolCidr': '158.168.254.0/24',
 u'RouterId': u'92b88b7f-4503-49fb-aef5-0a19bdd25ac6',
 'ServiceDescription': u'fip=222.168.1.4;tunnel_local_cidr=10.0.0.0/26;user_access_ip=222.168.1.6;fixed_ip=192.169.0.2',
 u'Subnet': u'ff407812-c888-4158-a220-0045d653774e'}
            '''
            self.assertEqual(expected_stack_template, call_stack_template)
            #self.assertEqual({}, call_stack_params)

            self._test_node_cleanup(provider, stack_id, prs_id=prs['id'])

    # TODO(Magesh): Verify the template contents for sslvpn
    def test_sslvpn_chain(self):
        #self._create_nat_pool_and_es("111.0.0.0/24", "default")
        self._test_sslvpn()

    def _test_sitetositevpn(self):
        classifier_port = '66'
        classifier_protocol = 'udp'
        with mock.patch.object(heatClient.HeatClient,
                               'create') as stack_create:
            stack_create.return_value = {'stack': {
                                        'id': uuidutils.generate_uuid()}}
            prs, node_id = self._create_s_to_s_vpn_redirect_ruleset(
                classifier_port, classifier_protocol)

            eps = self._list("external_policies")['external_policies']
            consumed_policy_rule_sets_list = eps[0]['consumed_policy_rule_sets']
            consumed_policy_rule_sets_dict = {}
            for prs_id in consumed_policy_rule_sets_list:
                consumed_policy_rule_sets_dict[prs_id] = ""
            consumed_policy_rule_sets_dict[prs['id']] = ""
            self.update_external_policy(
                eps[0]['id'],
                consumed_policy_rule_sets=consumed_policy_rule_sets_dict)

            provider = self.create_policy_target_group(
                provided_policy_rule_sets={prs['id']: ''})[
                                                'policy_target_group']

            created_stacks_map = self._get_node_instance_stacks(node_id)
            self.assertEqual(1, len(created_stacks_map))
            stack_id = created_stacks_map[0].stack_id

            expected_stack_template = copy.deepcopy(
                self.DEFAULT_S_TO_S_CONFIG_DICT)
            provider_cidr = self._get_ptg_cidr(provider)

            expected_stack_template = copy.deepcopy(
                                        self.DEFAULT_S_TO_S_CONFIG_DICT)

            call_stack_name, call_stack_template, call_stack_params = (
                stack_create.call_args_list[0][0])

            self.assertEqual(expected_stack_template, call_stack_template)
            #self.assertEqual({}, call_stack_params)

            self._test_node_cleanup(provider, stack_id, prs_id=prs['id'])

    def test_sitetositevpn(self):
        #self._create_nat_pool_and_es("111.0.0.0/24", "default")
        self._test_sitetositevpn()

    def test_node_update(self):
        with mock.patch.object(heatClient.HeatClient,
                               'create') as stack_create:
            stack_create.return_value = {'stack': {
                                        'id': uuidutils.generate_uuid()}}
            prof = self.create_service_profile(
                        service_type=constants.LOADBALANCER,
                        vendor=SUPPORTED_SERVICE_VENDOR_MAPPING[constants.LOADBALANCER])['service_profile']

            node = self.create_servicechain_node(
                        service_profile_id=prof['id'],
                        config=self.DEFAULT_LB_CONFIG,
                        expected_res_status=201)['servicechain_node']

            self._create_chain_with_nodes(node_ids=[node['id']])
            with mock.patch.object(heatClient.HeatClient,
                                   'update') as stack_update:
                self.update_servicechain_node(
                                        node['id'],
                                        name='newname',
                                        expected_res_status=200)
                # Name update should not update stack ??
                stack_update.assert_called_once_with(
                                    mock.ANY, mock.ANY, mock.ANY)

    def test_vpn_site_to_site_fw_lb_chain(self):
        with mock.patch.object(heatClient.HeatClient,
                               'create') as stack_create:
            stack_create.return_value = {'stack': {
                                        'id': uuidutils.generate_uuid()}}
            lb_prof = self.create_service_profile(
                service_type=constants.LOADBALANCER,
                vendor=SUPPORTED_SERVICE_VENDOR_MAPPING[constants.LOADBALANCER])['service_profile']
            fw_prof = self.create_service_profile(
                service_type=constants.FIREWALL,
                vendor=SUPPORTED_SERVICE_VENDOR_MAPPING[constants.FIREWALL])['service_profile']
            vpn_prof = self.create_service_profile(
                service_type=constants.VPN,
                vendor=SUPPORTED_SERVICE_VENDOR_MAPPING[constants.VPN])['service_profile']
            lb_node = self.create_servicechain_node(
                service_profile_id=lb_prof['id'],
                config=self.DEFAULT_LB_CONFIG,
                expected_res_status=201)['servicechain_node']
            fw_node = self.create_servicechain_node(
                service_profile_id=fw_prof['id'],
                config=self.DEFAULT_FW_CONFIG,
                expected_res_status=201)['servicechain_node']
            vpn_node = self.create_servicechain_node(
                service_profile_id=vpn_prof['id'],
                config=self.DEFAULT_S_TO_S_CONFIG,
                expected_res_status=201)['servicechain_node']

            # FIXME (Magesh): Have to patch get_shared_service_info()
            self._create_chain_with_nodes(
                node_ids=[vpn_node['id'], fw_node['id'], lb_node['id']])
            with mock.patch.object(heatClient.HeatClient,
                                   'update') as stack_update:
                self.update_servicechain_node(
                                        lb_node['id'],
                                        name='newname',
                                        expected_res_status=200)
                # Name update should not update stack ??
                stack_update.assert_called_once_with(
                                    mock.ANY, mock.ANY, mock.ANY)

    def test_node_delete(self):
        with mock.patch.object(heatClient.HeatClient,
                               'create') as stack_create:
            stack_create.return_value = {'stack': {
                                        'id': uuidutils.generate_uuid()}}
            provider, _, _ = self._create_simple_service_chain()
            with mock.patch.object(heatClient.HeatClient,
                                   'delete'):
                self.update_policy_target_group(
                                        provider['id'],
                                        provided_policy_rule_sets={},
                                        expected_res_status=200)
                self.delete_policy_target_group(provider['id'],
                                                expected_res_status=204)

    def test_wait_stack_delete_for_instance_delete1(self):
        #FIXME(Magesh): Second chain fails. so split this test from the next one
        with mock.patch.object(heatClient.HeatClient,
                               'create') as stack_create:
            stack_create.return_value = {'stack': {
                                        'id': uuidutils.generate_uuid()}}
            provider, _, _ = self._create_simple_service_chain()

            # Verify that as part of delete service chain instance we call
            # get method for heat stack 3 times before giving up if the state
            # does not become DELETE_COMPLETE
            with mock.patch.object(heatClient.HeatClient,
                                   'delete') as stack_delete:
                with mock.patch.object(heatClient.HeatClient,
                                       'get') as stack_get:
                    mock.patch.object(time, 'sleep').start()
                    stack_get.return_value = MockStackObject('DELETE_IN_PROGRESS')
                    # Unsetting PRS not required anymore
                    self.update_policy_target_group(
                                        provider['id'],
                                        provided_policy_rule_sets={},
                                        expected_res_status=200)
                    self.delete_policy_target_group(provider['id'],
                                                    expected_res_status=204)
                    self.assertEqual(STACK_ACTION_WAIT_TIME / 5,
                                     stack_get.call_count)

    def test_wait_stack_delete_for_instance_delete(self):
        with mock.patch.object(heatClient.HeatClient,
                               'create') as stack_create:
            stack_create.return_value = {'stack': {
                                        'id': uuidutils.generate_uuid()}}
            # Create and delete another service chain instance and verify that
            # we call get method for heat stack only once if the stack state
            # is DELETE_COMPLETE
            provider, _, _ = self._create_simple_service_chain()
            with mock.patch.object(heatClient.HeatClient,
                                   'delete') as stack_delete:
                with mock.patch.object(heatClient.HeatClient,
                                       'get') as stack_get:
                    stack_get.return_value = MockStackObject(
                        'DELETE_COMPLETE')
                    # Removing the PRSs will make the PTG deletable again
                    self.update_policy_target_group(
                                        provider['id'],
                                        provided_policy_rule_sets={},
                                        expected_res_status=200)
                    self.delete_policy_target_group(provider['id'],
                                                expected_res_status=204)
                    stack_delete.assert_called_once_with(mock.ANY)
                    self.assertEqual(1, stack_get.call_count)

    def test_stack_not_found_ignored(self):
        mock.patch(heatclient.__name__ + ".client.Client",
                   new=MockHeatClientDeleteNotFound).start()

        provider, _, _ = self._create_simple_service_chain()

        # Removing the PRSs will make the PTG deletable again
        self.update_policy_target_group(provider['id'],
                                        provided_policy_rule_sets={},
                                        expected_res_status=200)
        self.delete_policy_target_group(provider['id'],
                                        expected_res_status=204)


# TODO(Magesh): Add Update UTs, UTs with Interchange order of Provider,consumer
# create and delete, rule updates with consumer add/delete
