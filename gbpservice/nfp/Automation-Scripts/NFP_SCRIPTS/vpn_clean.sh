#!/bin/bash

source /home/stack/devstack/openrc neutron service

echo "Make sure that policy-targets associated to PTGs are deleted!!"

# Delete PTG/external-policy
gbp external-policy-delete  vpn-consumer
gbp group-delete  vpn-provider

# Delete rule-set
gbp policy-rule-set-delete  vpn-webredirect-ruleset

# Delete rules
gbp policy-rule-delete  vpn-web-redirect-rule

# Delete classifier
gbp policy-classifier-delete  vpn-webredirect

# Delete actions
gbp policy-action-delete redirect-to-vpn

# Delete service chain node and specs
gbp servicechain-spec-delete  vpn_chainspec
gbp servicechain-node-delete VPN_VPNNODE
