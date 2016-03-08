#!/bin/bash

TOP_DIR=$2
source $TOP_DIR/openrc neutron service
GBP_SCRIPT_DIR=$1
# update service_management_network to False if there is no separate service management network
# else update it to True 
set -x

if [ -f $GBP_SCRIPT_DIR/oc_gbp_params.sh ] ;
then
        echo ""
else
        echo "ERROR :  /home/stack/test/oc_gbp_params.sh is not exists."
        exit 0
fi

source  $GBP_SCRIPT_DIR/oc_gbp_params.sh

gbp policy-action-create --action-type allow allowmanagement_action

gbp policy-classifier-create --protocol tcp --port-range 22 --direction bi sshinclassifier

gbp policy-classifier-create --protocol tcp --port-range 1234 --direction bi haproxy_on_vm_agent_inclassifier

gbp policy-classifier-create --protocol tcp --port-range 8888 --direction bi vyos_agent_classifier

gbp policy-classifier-create --protocol tcp --port-range 443 --direction bi https_classifier

gbp policy-classifier-create --protocol icmp --direction bi icmpbiclassifier

gbp policy-classifier-create --protocol tcp --port-range 5000 --direction bi keystone_classifier


gbp policy-rule-create --classifier icmpbiclassifier --actions allowmanagement_action allowicmprule

gbp policy-rule-create --classifier haproxy_on_vm_agent_inclassifier --actions allowmanagement_action allow_haproxy_on_vm_agent_rule

gbp policy-rule-create --classifier sshinclassifier --actions allowmanagement_action allow_ssh_in_rule

gbp policy-rule-create --classifier https_classifier --actions allowmanagement_action https_rule

gbp policy-rule-create --classifier vyos_agent_classifier --actions allowmanagement_action vyos_agent_rule

gbp policy-rule-create --classifier keystone_classifier --actions allowmanagement_action keystone_allow


gbp policy-rule-set-create --policy-rules "https_rule allow_ssh_in_rule allow_haproxy_on_vm_agent_rule allowicmprule vyos_agent_rule keystone_allow" service_management_ruleset

gbp external-policy-create --external-segments $inet_external_segment_name --consumed-policy-rule-sets service_management_ruleset=None service_management_external_policy

gbp l3policy-create --ip-version 4 --ip-pool 120.0.0.0/22 --subnet-prefix-length 24 --external-segment                      "$inet_external_segment_name=" service_management_l3policy

gbp l2policy-create --l3-policy service_management_l3policy service_management_l2p

gbp network-service-policy-create --network-service-params type=ip_pool,name=vip_ip,value=nat_pool svc_mgmt_fip_policy





gbp service-profile-create --servicetype LOADBALANCER --insertion-mode l3 --shared True --service-flavor haproxy --vendor NFP lb_profile
gbp service-profile-create --servicetype FIREWALL --insertion-mode l3 --shared True --service-flavor vyos --vendor NFP fw_profile






gbp group-create svc_management_ptg --provided-policy-rule-sets service_management_ruleset=None --l2-policy service_management_l2p --service_management True
