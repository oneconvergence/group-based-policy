#!/bin/bash

source /home/stack/devstack/openrc neutron service

# Service chain node and spec creation
gbp servicechain-node-create --service-profile fw_profile --template-file ./templates/fw_template.yml FW_vpn-FWNODE
gbp servicechain-node-create --service-profile vpn_profile --template-file ./templates/vpn.template FW_vpn-vpnNODE
gbp servicechain-spec-create --nodes "FW_vpn-vpnNODE FW_vpn-FWNODE" fw_vpn_chainspec
#gbp servicechain-spec-create --nodes "FW_vpn-vpnNODE" fw_vpn_chainspec

# REDIRECT action, classifier, rule and rule-set
gbp policy-action-create --action-type REDIRECT --action-value fw_vpn_chainspec redirect-to-fw_vpn
gbp policy-classifier-create --protocol tcp --direction bi fw_vpn-webredirect
gbp policy-rule-create --classifier fw_vpn-webredirect --actions redirect-to-fw_vpn fw_vpn-web-redirect-rule
gbp policy-rule-set-create --policy-rules "fw_vpn-web-redirect-rule" fw_vpn-webredirect-ruleset

# Network service policy
gbp network-service-policy-create --network-service-params type=ip_single,name=vip_ip,value=self_subnet fw_vpn_nsp

#   For N-S create external-policy, for E-W create policy-target-group(consumer-group)
gbp external-policy-create --external-segments default --consumed-policy-rule-sets fw_vpn-webredirect-ruleset=None fw_vpn-consumer
#       (or for E-W)                                           
#gbp group-create fw_vpn-consumer --consumed-policy-rule-sets "fw_vpn-webredirect-ruleset=None"

# Provider PTG
gbp group-create fw_vpn-provider --provided-policy-rule-sets "fw_vpn-webredirect-ruleset=None" --network-service-policy fw_vpn_nsp

