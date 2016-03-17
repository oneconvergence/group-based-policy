#!/bin/bash

TOP_DIR=$2
source $TOP_DIR/openrc neutron service
NFP_SCRIPTS_DIR=$1
# update service_management_network to False if there is no separate service management network
# else update it to True 
set -x

if [ -f $NFP_SCRIPTS_DIR/nfp_gbp_params.sh ] ;
then
        echo ""
else
        echo "ERROR :  nfp_gbp_params.sh is not exists."
        exit 0
fi

source  $NFP_SCRIPTS_DIR/nfp_gbp_params.sh


gbp network-service-policy-create --network-service-params type=ip_pool,name=vip_ip,value=nat_pool svc_mgmt_fip_policy


gbp service-profile-create --servicetype LOADBALANCER --insertion-mode l3 --shared True --service-flavor haproxy --vendor NFP lb_profile
gbp service-profile-create --servicetype FIREWALL --insertion-mode l3 --shared True --service-flavor vyos --vendor NFP fw_profile


gbp group-create svc_management_ptg --service_management True

