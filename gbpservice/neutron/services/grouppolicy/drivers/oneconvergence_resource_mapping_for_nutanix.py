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

import random
from neutron.common import log
from neutron.openstack.common import log as logging

from gbpservice.neutron.services.grouppolicy.drivers import resource_mapping
from gbpservice.neutron.services.grouppolicy.drivers import policyflow_driver

LOG = logging.getLogger(__name__)

DEFAULT_CLASSIFIER_NAME_PREFIX="default_cl_"
DEFAULT_ACTION_NAME_PREFIX="default_act_"
DEFAULT_RULE_NAME_PREFIX="default_rule_"

class OneConvergenceResourceMappingDriverForNutanix(resource_mapping.ResourceMappingDriver):
    '''
    One Convergence Resource Mapping driver to support Nutanix requirement
    '''

    def __init__(self):
        self.policyflow_driver = policyflow_driver.PolicyFlowDriver()
    
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
                self._use_explicit_subnet(context._plugin_context, subnet_id,
                                          router_id)
        else:
            self._use_implicit_subnet(context)
        self._handle_network_service_policy(context)
        self._handle_policy_rule_sets(context)
        #self._update_default_security_group(context._plugin_context,
        #                                    context.current['id'],
        #                                    context.current['tenant_id'],
        #                                    context.current['subnets'])

        ptg_id = context.current['id']
        #default_action = self.create_default_policy_action(context,ptg_id) 
        self.default_classifier = self.create_default_policy_classifier(context,ptg_id)
        self.default_rule = self.create_default_policy_rule(context,self.default_classifier,ptg_id)
       
        #create default_nvsd_policy_flow
        self.create_nvsd_policy_flow(context)
        
   
    @log.log
    def delete_policy_target_group_precommit(self, context):
        context.nsp_cleanup_ipaddress = self._get_ptg_policy_ipaddress_mapping(
            context._plugin_context.session, context.current['id'])
        provider_ptg_chain_map = self._get_ptg_servicechain_mapping(
                                            context._plugin_context.session,
                                            context.current['id'],
                                            None)
        consumer_ptg_chain_map = self._get_ptg_servicechain_mapping(
                                            context._plugin_context.session,
                                            None,
                                            context.current['id'],)
        context.ptg_chain_map = provider_ptg_chain_map + consumer_ptg_chain_map
        self.policy_rule_set_contract_map(context)
    
    @log.log
    def delete_policy_target_group_postcommit(self, context):

        ptg_id = context.current['id']          
        self.default_rules = context._plugin.get_policy_rules(context._plugin_context, 
                                                 filters={'name': [ DEFAULT_RULE_NAME_PREFIX+'%s' % ptg_id] })

        default_classifiers = context._plugin.get_policy_classifiers(context._plugin_context, 
                                                                     filters={'name': [ DEFAULT_CLASSIFIER_NAME_PREFIX+'%s' % ptg_id ]})
        #default_actions =  context._plugin.get_policy_actions(context._plugin_context, 
        #                                                      filters={'name': [ DEFAULT_ACTION_NAME_PREFIX+'%s' % ptg_id ]}) 
        self.delete_nvsd_policy_flow(context)
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
                self._cleanup_subnet(context._plugin_context, subnet_id, router_id)
            #self._delete_default_security_group(
            #    context._plugin_context, context.current['id'],
            #    context.current['tenant_id'])
              
        except Exception as e:
            LOG.exception((e))
      
        context._plugin.delete_policy_rule(context._plugin_context,self.default_rules[0]['id'])
        context._plugin.delete_policy_classifier(context._plugin_context,default_classifiers[0]['id'])
        #context._plugin.delete_policy_action(context._plugin_context,default_actions[0]['id'])
        #self.delete_nvsd_policy_flow(context)
    
    def policy_rule_set_contract_map(self,context):
        self.policy_rule_set_contracts = {}
        policy_rule_set_ids = self.get_policy_rule_sets(context)
        for policy_rule_set_id in  policy_rule_set_ids:
            policy_rule_set = context._plugin.get_policy_rule_set(context._plugin_context,policy_rule_set_id)
            contract_defined = self.is_gbp_contract_defined(context,policy_rule_set)
            if contract_defined is True:
                self.policy_rule_set_contracts[policy_rule_set_id] = True
            else:
                self.policy_rule_set_contracts[policy_rule_set_id] = False        
       
    def delete_nvsd_policy_flow(self,context):
        ''' 
        Delete default policy flow
        '''
        result = self.policyflow_driver.delete_policyflow(context._plugin_context.auth_token, self.default_rules[0]['id'])
        
        '''
        Delete other nvsd policy flows
        '''
        policy_rule_set_ids = self.get_policy_rule_sets(context)
        for policy_rule_set_id in  policy_rule_set_ids:
            policy_rule_set = context._plugin.get_policy_rule_set(context._plugin_context,policy_rule_set_id)
            if self.policy_rule_set_contracts.get(policy_rule_set_id) is True:
                policy_rules = context._plugin.get_policy_rules(
                        context._plugin_context,
                        filters={'id': policy_rule_set['policy_rules']})
                for policy_rule in policy_rules:
                    policy_flow_ids = []
                    policy_classifiers = context._plugin.get_policy_classifiers(context._plugin_context,
                                                                        filters={'id': [policy_rule.get("policy_classifier_id")] } )
                    policy_classifier = policy_classifiers[0]
                    if policy_classifier['direction'] == 'bi':
                        id = policy_rule['id']
                        policy_flow_ids.append(id.replace(id[len(id)-1],'0'))
                        policy_flow_ids.append(id.replace(id[len(id)-1],'1'))
                    else:
                        policy_flow_ids.append(policy_rule['id'])
                        
                    for policy_flow_id in policy_flow_ids:        
                        self.delete_nvsd_contract(context, policy_flow_id)

    
    def delete_nvsd_contract(self,context,policy_flow_id):
        self.policyflow_driver.delete_policyflow(context._plugin_context.auth_token, policy_flow_id)
      
    def create_nvsd_contract(self,context,policy_flow_context): 
        
        self.policyflow_driver.create_flow(policy_flow_context.auth_token,
                                      policy_flow_context.policy_flow_id,
                                      policy_flow_context.tenant_id,
                                      policy_flow_context.left_group_id,
                                      policy_flow_context.right_group_id,
                                      policy_flow_context.origin_port,
                                      policy_flow_context.target_port,
                                      policy_flow_context.classifier_protocol,
                                      policy_flow_context.vlan,
                                      policy_flow_context.flow_type,
                                      policy_flow_context.l4_src_port,
                                      policy_flow_context.l4_dst_port,
                                      policy_flow_context.left_group_type,
                                      policy_flow_context.right_group_type)

    def define_nvsd_policy_flow_context(self,context,policy_rule,policy_rule_set):
        
        policy_flow_contexts = []
        policy_actions = context._plugin.get_policy_actions(context._plugin_context,
                                                            filters={'id': policy_rule.get("policy_actions") } )
        policy_classifiers = context._plugin.get_policy_classifiers(context._plugin_context,
                                                            filters={'id': [policy_rule.get("policy_classifier_id")] } )
        policy_action = policy_actions[0]
        policy_classifier = policy_classifiers[0]
        consumer_port_group = context._plugin.get_policy_target_groups(context._plugin_context,
                                                                       filters={'id':[policy_rule_set['consuming_policy_target_groups'][0]]})
        left_group_id = consumer_port_group[0]['subnets'][0]
        provider_port_group = context._plugin.get_policy_target_groups(context._plugin_context,
                                                                       filters={'id':[policy_rule_set['providing_policy_target_groups'][0]]})
        right_group_id = provider_port_group[0]['subnets'][0]

        policy_flow_context = self.NVSDPolicyFlowContext()
        policy_flow_context.policy_flow_id = policy_rule['id']
        policy_flow_context.auth_token = context._plugin_context.auth_token
        policy_flow_context.tenant_id = context._plugin_context.tenant_id
        policy_flow_context.vlan = random.randint(500,1000)
        policy_flow_context.left_group_id = left_group_id
        policy_flow_context.right_group_id = right_group_id
        
        if policy_action['action_type'] == 'allow':
            policy_flow_context.flow_type = "ALLOW"
        elif policy_action['action_type'] == 'redirect':
            policy_flow_context.flow_type = "REDIRECT"
        
        policy_flow_context.classifier_protocol = policy_classifier['protocol']
        create_reverse_policy_flow = False
        
        if policy_classifier['direction'] == 'in':
            policy_flow_context.l4_dst_port = policy_classifier['port_range']
        elif policy_classifier['direction'] == 'out':    
            policy_flow_context.l4_src_port = policy_classifier['port_range']
        elif policy_classifier['direction'] == 'bi':
            policy_flow_context.l4_dst_port = policy_classifier['port_range']
            id = policy_rule['id']
            policy_flow_context.policy_flow_id = id.replace(id[len(id)-1],'0')
            create_reverse_policy_flow = True
            
        policy_flow_contexts.append(policy_flow_context)
        '''
        create reverse policy flow
        '''
        if create_reverse_policy_flow is True:
                
            policy_flow_context1 = self.NVSDPolicyFlowContext()
            policy_flow_context1.policy_flow_id = policy_rule['id']
            policy_flow_context1.auth_token = context._plugin_context.auth_token
            policy_flow_context1.tenant_id = context._plugin_context.tenant_id
            policy_flow_context1.vlan = random.randint(500,1000)
            policy_flow_context1.left_group_id = right_group_id 
            policy_flow_context1.right_group_id = left_group_id
           
            if policy_action['action_type'] == 'allow':
                policy_flow_context.flow_type = "ALLOW"
            elif policy_action['action_type'] == 'redirect':
                policy_flow_context.flow_type = "REDIRECT"
            
            policy_flow_context1.classifier_protocol = policy_classifier['protocol']
            policy_flow_context1.l4_src_port = policy_classifier['port_range']
            id = policy_rule['id']
            policy_flow_context1.policy_flow_id = id.replace(id[len(id)-1],'1')
            policy_flow_contexts.append(policy_flow_context1)    

        return policy_flow_contexts

    def create_nvsd_policy_flow(self,context):
        '''
        Create default nvsd policy flow
        '''
        subnets = context.current['subnets']
        for subnet_id in subnets:
            policy_flow_context = self.NVSDPolicyFlowContext()
            policy_flow_context.policy_flow_id = self.default_rule['id']
            policy_flow_context.auth_token = context._plugin_context.auth_token
            policy_flow_context.tenant_id = context._plugin_context.tenant_id
            policy_flow_context.vlan = random.randint(500,1000)
            policy_flow_context.left_group_id = subnet_id
            policy_flow_context.right_group_id = subnet_id
            self.create_nvsd_contract(context, policy_flow_context)

        '''
        1) create nvsd policy flows if contract is defined
        2) one nvsd policy flow per policy rule
        '''
        policy_rule_set_ids = self.get_policy_rule_sets(context)
        for policy_rule_set_id in  policy_rule_set_ids:
            policy_rule_set = context._plugin.get_policy_rule_set(context._plugin_context,policy_rule_set_id)
            contract_defined = self.is_gbp_contract_defined(context,policy_rule_set)
            if contract_defined is True:
                policy_rules = context._plugin.get_policy_rules(
                        context._plugin_context,
                        filters={'id': policy_rule_set['policy_rules']})
                for policy_rule in policy_rules:
                    policy_flow_contexts = self.define_nvsd_policy_flow_context(context, policy_rule, policy_rule_set)
                    for policy_flow_context in policy_flow_contexts:
                        self.create_nvsd_contract(context, policy_flow_context)
                    
    def is_gbp_contract_defined(self,context,policy_rule_set):
        ptgs_consuming_prs = (
        policy_rule_set['consuming_policy_target_groups'] +
        policy_rule_set['consuming_external_policies'])
        ptgs_providing_prs = policy_rule_set[
                                    'providing_policy_target_groups']

        if not ptgs_consuming_prs or not ptgs_providing_prs:
            return False
        else:
            return True
    
    def get_policy_rule_sets(self,context):
        policy_rule_set_ids = []
        if context.current['provided_policy_rule_sets']:
            policy_rule_set_ids = context.current['provided_policy_rule_sets']
        elif context.current['consumed_policy_rule_sets']:
            policy_rule_set_ids = context.current['consumed_policy_rule_sets']
        
        return policy_rule_set_ids
          
    def create_default_policy_action(self, context, ptg_id):
        policy_action = {'policy_action':
                         {'action_type': 'allow',
                         'action_value': ' ',
                         'description': 'default-policy-action',
                         'name': DEFAULT_ACTION_NAME_PREFIX+'%s' % ptg_id 
                         }
                        }
        return context._plugin.create_policy_action(context._plugin_context, policy_action)

    def create_default_policy_classifier(self, context, ptg_id):
        policy_classifier = {'policy_classifier':
                             {'description': 'default-policy-classifier',
                             'direction': 'in',
                             'name': DEFAULT_CLASSIFIER_NAME_PREFIX+'%s' % ptg_id,
                             'protocol': 'icmp',
                             'port_range': '0'
                             }
                            }
        return context._plugin.create_policy_classifier(context._plugin_context, policy_classifier)

    def create_default_policy_rule(self, context, default_classifier, ptg_id):
        policy_rule = {'policy_rule':
                       {'description': 'default-policy-rule',
                        'enabled': True,
                        'name': DEFAULT_RULE_NAME_PREFIX+'%s' % ptg_id,
                        'policy_classifier_id': default_classifier['id'],
                        'policy_actions': []
                        }
                      }
        return context._plugin.create_policy_rule(context._plugin_context, policy_rule)

    
    class NVSDPolicyFlowContext():
        def __init__(self):
            self.target_port = self.origin_port  = None
            self.classifier_protocol = self.l4_src_port = self.l4_dst_port = None
            self.policy_flow_id = self.left_group_id = self.right_group_id = None
            self.left_group_type = self.right_group_type = "Subnet"
            self.flow_type = "ALLOW"
            self.auth_token = None
            self.tenant_id = None
            self.vlan = None
       
