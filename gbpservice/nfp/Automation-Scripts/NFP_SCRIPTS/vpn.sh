#!/bin/bash

source /home/stack/devstack/openrc neutron service

# Service chain node and spec creation
gbp servicechain-node-create --service-profile vpn_profile --template-file ./templates/vpn.template VPN_VPNNODE
gbp servicechain-spec-create --nodes "VPN_VPNNODE" vpn_chainspec

# REDIRECT action, classifier, rule and rule-set
gbp policy-action-create --action-type REDIRECT --action-value vpn_chainspec redirect-to-vpn
gbp policy-classifier-create --protocol tcp --direction bi vpn-webredirect
gbp policy-rule-create --classifier vpn-webredirect --actions redirect-to-vpn vpn-web-redirect-rule
gbp policy-rule-set-create --policy-rules "vpn-web-redirect-rule" vpn-webredirect-ruleset

gbp group-create vpn-provider --provided-policy-rule-sets "vpn-webredirect-ruleset=None"
