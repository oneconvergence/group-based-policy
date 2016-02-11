# Copyright 2014 Alcatel-Lucent USA Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import contextlib
import mock

import webob.exc

from gbpservice.neutron.tests.unit.services.grouppolicy import (
    test_resource_mapping as test_resource_mapping)


SERVICE_PROFILES = 'servicechain/service_profiles'
SERVICECHAIN_NODES = 'servicechain/servicechain_nodes'
SERVICECHAIN_SPECS = 'servicechain/servicechain_specs'
SERVICECHAIN_INSTANCES = 'servicechain/servicechain_instances'


class OneConvergenceGBPMappingDriverTestCase(
                    test_resource_mapping.ResourceMappingTestCase):

    def setUp(self):
        policy_drivers = ['implicit_policy', 'oneconvergence_resource_mapping']
        super(OneConvergenceGBPMappingDriverTestCase, self).setUp(
                                        policy_drivers=policy_drivers)


class TestPolicyTarget(OneConvergenceGBPMappingDriverTestCase,
                       test_resource_mapping.TestPolicyTarget):
    pass


class TestPolicyTargetGroup(OneConvergenceGBPMappingDriverTestCase,
                            test_resource_mapping.TestPolicyTargetGroup):
    pass


class TestL2Policy(OneConvergenceGBPMappingDriverTestCase,
                   test_resource_mapping.TestL2Policy):
    pass


class TestPolicyClassifier(OneConvergenceGBPMappingDriverTestCase):
    pass


class TestL3Policy(OneConvergenceGBPMappingDriverTestCase,
                   test_resource_mapping.TestL3Policy):
    pass


class TestPolicyRuleSet(OneConvergenceGBPMappingDriverTestCase,
                        test_resource_mapping.TestPolicyRuleSet):
    def test_ptg_delete_rejected_with_active_chain(self):
        scs_id = self._create_servicechain_spec()
        _, _, policy_rule_id = self._create_tcp_redirect_rule(
                                                "20:90", scs_id)

        policy_rule_set = self.create_policy_rule_set(
            name="c1", policy_rules=[policy_rule_id])
        policy_rule_set_id = policy_rule_set['policy_rule_set']['id']
        provider_ptg_id, consumer_ptg_id = self._create_provider_consumer_ptgs(
                                                            policy_rule_set_id)

        self._verify_prs_rules(policy_rule_set_id)
        sc_node_list_req = self.new_list_request(SERVICECHAIN_INSTANCES)
        res = sc_node_list_req.get_response(self.ext_api)
        sc_instances = self.deserialize(self.fmt, res)
        # We should have one service chain instance created now
        self.assertEqual(len(sc_instances['servicechain_instances']), 1)
        sc_instance = sc_instances['servicechain_instances'][0]
        self._assert_proper_chain_instance(sc_instance, provider_ptg_id,
                                           consumer_ptg_id, [scs_id])

        # Verify that PTG delete is rejected with InUse
        res = self.delete_policy_target_group(consumer_ptg_id,
                                              expected_res_status=409)
        self.assertEqual('PTGInUseByPRS',
                         res['NeutronError']['type'])

        # Verify unset PRS from Group cleans up Service chain
        self.update_policy_target_group(consumer_ptg_id,
                                        consumed_policy_rule_sets={},
                                        expected_res_status=200)
        sc_node_list_req = self.new_list_request(SERVICECHAIN_INSTANCES)
        res = sc_node_list_req.get_response(self.ext_api)
        sc_instances = self.deserialize(self.fmt, res)
        self.assertEqual(len(sc_instances['servicechain_instances']), 0)

    def test_redirect_to_ep_cleanup(self):
        scs_id = self._create_servicechain_spec()
        _, _, policy_rule_id = self._create_tcp_redirect_rule(
                                                "20:90", scs_id)

        policy_rule_set = self.create_policy_rule_set(
            name="c1", policy_rules=[policy_rule_id])
        policy_rule_set_id = policy_rule_set['policy_rule_set']['id']

        with self.network(router__external=True, shared=True) as net:
            with self.subnet(cidr='192.168.0.0/24', network=net) as sub:
                self.create_external_segment(
                    shared=True,
                    tenant_id='admin', name="default",
                    subnet_id=sub['subnet']['id'])['external_segment']

                ep = self.create_external_policy(
                    consumed_policy_rule_sets={policy_rule_set_id: ''})
                provider = self.create_policy_target_group(
                    provided_policy_rule_sets={policy_rule_set_id: ''})

                self._verify_prs_rules(policy_rule_set_id)
                sc_node_list_req = self.new_list_request(
                    SERVICECHAIN_INSTANCES)
                res = sc_node_list_req.get_response(self.ext_api)
                sc_instances = self.deserialize(self.fmt, res)
                # We should have one service chain instance created now
                self.assertEqual(
                    1, len(sc_instances['servicechain_instances']))
                sc_instance = sc_instances['servicechain_instances'][0]
                self._assert_proper_chain_instance(
                    sc_instance, provider['policy_target_group']['id'],
                    ep['external_policy']['id'], [scs_id])

                # Verify that PTG delete is rejected with InUse
                res = self.delete_external_policy(
                    ep['external_policy']['id'], expected_res_status=409)
                self.assertEqual('EPInUseByPRS',
                                 res['NeutronError']['type'])

                # Update the EP and unset the PRS. This should delete the chain
                self.update_external_policy(
                    ep['external_policy']['id'],
                    consumed_policy_rule_sets={},
                    expected_res_status=webob.exc.HTTPOk.code)
                sc_node_list_req = self.new_list_request(
                    SERVICECHAIN_INSTANCES)
                res = sc_node_list_req.get_response(self.ext_api)
                sc_instances = self.deserialize(self.fmt, res)
                self.assertEqual(
                    0, len(sc_instances['servicechain_instances']))

    def RaiseError(self, context):
        raise

    def test_cleanup_on_ep_create_failure(self):
        scs_id = self._create_servicechain_spec()
        _, _, policy_rule_id = self._create_tcp_redirect_rule(
                                                "20:90", scs_id)

        policy_rule_set = self.create_policy_rule_set(
            name="c1", policy_rules=[policy_rule_id])
        policy_rule_set_id = policy_rule_set['policy_rule_set']['id']
        with self.network(router__external=True, shared=True) as net:
            with self.subnet(cidr='192.168.0.0/24', network=net) as sub:
                self.create_external_segment(
                    shared=True,
                    tenant_id='admin', name="default",
                    subnet_id=sub['subnet']['id'])['external_segment']

                self.create_policy_target_group(
                    provided_policy_rule_sets={policy_rule_set_id: ''})
                mock.patch("gbpservice.neutron.services.servicechain.plugins."
                           "msc.driver_manager.DriverManager."
                           "create_servicechain_instance_postcommit",
                           new=self.RaiseError).start()
                delete_sc_instance = mock.patch(
                    "gbpservice.neutron.services.servicechain.plugins.msc."
                    "driver_manager.DriverManager."
                    "delete_servicechain_instance_postcommit").start()
                ep = self.create_external_policy(
                    name='ep1',
                    consumed_policy_rule_sets={policy_rule_set_id: ''},
                    expected_res_status=webob.exc.HTTPInternalServerError.code)
                self.assertEqual('ExternalPolicyCreateFailed',
                                 ep['NeutronError']['type'])
                delete_sc_instance.assert_called_once_with(mock.ANY)
                self.assertFalse(
                    self._list(
                        'policy_target_groups',
                        query_params='name=ep1')['policy_target_groups'])
                sc_node_list_req = self.new_list_request(
                    SERVICECHAIN_INSTANCES)
                res = sc_node_list_req.get_response(self.ext_api)
                sc_instances = self.deserialize(self.fmt, res)
                # All instances should be cleaned up
                self.assertEqual(
                    0, len(sc_instances['servicechain_instances']))

    def test_cleanup_on_ptg_create_failure(self):
        scs_id = self._create_servicechain_spec()
        _, _, policy_rule_id = self._create_tcp_redirect_rule(
                                                "20:90", scs_id)

        policy_rule_set = self.create_policy_rule_set(
            name="c1", policy_rules=[policy_rule_id])
        policy_rule_set_id = policy_rule_set['policy_rule_set']['id']

        with self.network(router__external=True, shared=True) as net:
            with self.subnet(cidr='192.168.0.0/24', network=net) as sub:
                self.create_external_segment(
                    shared=True,
                    tenant_id='admin', name="default",
                    subnet_id=sub['subnet']['id'])['external_segment']

                self.create_external_policy(
                    consumed_policy_rule_sets={policy_rule_set_id: ''})
                mock.patch("gbpservice.neutron.services.servicechain.plugins."
                           "msc.driver_manager.DriverManager."
                           "create_servicechain_instance_postcommit",
                           new=self.RaiseError).start()
                delete_sc_instance = mock.patch(
                    "gbpservice.neutron.services.servicechain.plugins.msc."
                    "driver_manager.DriverManager."
                    "delete_servicechain_instance_postcommit").start()
                provider = self.create_policy_target_group(
                    name='ptg1',
                    provided_policy_rule_sets={policy_rule_set_id: ''},
                    expected_res_status=webob.exc.HTTPInternalServerError.code)
                self.assertEqual('PTGCreateFailed',
                                 provider['NeutronError']['type'])
                delete_sc_instance.assert_called_once_with(mock.ANY)

                self.assertFalse(
                    self._list(
                        'policy_target_groups',
                        query_params='name=ptg1')['policy_target_groups'])
                sc_node_list_req = self.new_list_request(
                    SERVICECHAIN_INSTANCES)
                res = sc_node_list_req.get_response(self.ext_api)
                sc_instances = self.deserialize(self.fmt, res)
                # All instances should be cleaned up
                self.assertEqual(
                    0, len(sc_instances['servicechain_instances']))


class TestPolicyAction(OneConvergenceGBPMappingDriverTestCase,
                       test_resource_mapping.TestPolicyAction):
    pass


class TestPolicyRule(OneConvergenceGBPMappingDriverTestCase,
                     test_resource_mapping.TestPolicyRule):
    pass


class TestExternalSegment(OneConvergenceGBPMappingDriverTestCase,
                          test_resource_mapping.TestExternalSegment):
    pass


class TestExternalPolicy(OneConvergenceGBPMappingDriverTestCase,
                         test_resource_mapping.TestExternalPolicy):
    # One Convergence Driver supports Multiple External policies per tenant
    def test_create(self):
        with self.network(router__external=True) as net:
            with contextlib.nested(
                    self.subnet(cidr='10.10.1.0/24', network=net),
                    self.subnet(cidr='10.10.2.0/24', network=net)) as (
                    sub1, sub2):
                es1 = self.create_external_segment(
                    subnet_id=sub1['subnet']['id'],
                    shared=True)['external_segment']
                es2 = self.create_external_segment(
                    subnet_id=sub2['subnet']['id'])['external_segment']
                # Shared Rejected
                res = self.create_external_policy(
                    expected_res_status=400, external_segments=[es1['id']],
                    shared=True)
                self.assertEqual('InvalidSharedResource',
                                 res['NeutronError']['type'])
                # Multiple ES reject
                res = self.create_external_policy(
                    expected_res_status=400,
                    external_segments=[es1['id'], es2['id']])
                self.assertEqual('MultipleESPerEPNotSupported',
                                 res['NeutronError']['type'])
                # No ES reject
                res = self.create_external_policy(
                    expected_res_status=400, external_segments=[])
                self.assertEqual('ESIdRequiredWhenCreatingEP',
                                 res['NeutronError']['type'])


class TestNetworkServicePolicy(OneConvergenceGBPMappingDriverTestCase,
                               test_resource_mapping.TestNetworkServicePolicy):
    pass


class TestNatPool(OneConvergenceGBPMappingDriverTestCase,
                  test_resource_mapping.TestNatPool):
    pass
