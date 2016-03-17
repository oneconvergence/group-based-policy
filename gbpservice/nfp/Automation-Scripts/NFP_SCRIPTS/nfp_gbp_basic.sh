#!/bin/bash
TOP_DIR=$2

source $TOP_DIR/openrc neutron service
#set -x
NFP_SCRIPTS_DIR=$1
# update service_management_network to False if there is no separate service management network
# else update it to True 
service_management_network=False

if [ -f $NFP_SCRIPTS_DIR/nfp_gbp_params.sh ] ; 
then
	echo ""
else 
	echo "ERROR : /home/stack/test/nfp_gbp_params.sh is not exists."
	exit 0
fi

source $NFP_SCRIPTS_DIR/nfp_gbp_params.sh



gbp external-segment-create --ip-version 4 --cidr $inet_subnet --external-route destination=0.0.0.0/0,nexthop= --shared True --subnet_id=$subnet_id $inet_external_segment_name


gbp nat-pool-create --ip-version 4 --ip-pool $inet_nat_pool --external-segment $inet_external_segment_name --shared True $inet_external_segment_name

if [ "$service_management_network" == "True" ] ;
then
    gbp external-segment-create --ip-version 4 --cidr $SM_subnet --external-route destination=0.0.0.0/0,nexthop= $SM_external_segment_name

    gbp nat-pool-create --ip-version 4 --ip-pool $SM_nat_pool --external-segment $SM_external_segment_name $SM_external_segment_name
fi

