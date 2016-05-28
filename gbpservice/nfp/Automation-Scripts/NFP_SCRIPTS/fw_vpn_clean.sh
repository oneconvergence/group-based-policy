#!/bin/bash

#source /root/keystonerc_cloud_admin
source /home/stack/devstack/openrc neutron service
echo "Make sure that policy-targets associated to PTGs are deleted!!"

# Delete PTG
gbp group-delete fw_vpn-provider
gbp external-policy-delete fw_vpn-consumer

# Delete network service policy
gbp network-service-policy-delete fw_vpn_nsp

# Delete rule-set
gbp policy-rule-set-delete fw_vpn-webredirect-ruleset

# Delete rules
gbp policy-rule-delete fw_vpn-web-redirect-rule

# Delete classifier
gbp policy-classifier-delete fw_vpn-webredirect

# Delete actions
gbp policy-action-delete redirect-to-fw_vpn

# Delete service chain node and specs
gbp servicechain-spec-delete fw_vpn_chainspec
gbp servicechain-node-delete FW_vpn-vpnNODE
gbp servicechain-node-delete FW_vpn-FWNODE

