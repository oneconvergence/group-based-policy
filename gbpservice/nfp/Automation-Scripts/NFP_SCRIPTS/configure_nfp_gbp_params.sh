
TOP_DIR=$2
NFP_SCRIPTS_DIR=$1

function assign_user_credential {
source $TOP_DIR/openrc admin admin
#set -x
serviceTenantID=`keystone tenant-list | grep "service" | awk '{print $2}'`
serviceRoleID=`keystone role-list | grep "service" | awk '{print $2}'`
adminRoleID=`keystone role-list | grep "admin" | awk '{print $2}'`
keystone user-role-add --user nova --tenant $serviceTenantID --role $serviceRoleID
sleep 1
keystone user-role-add --user neutron --tenant $serviceTenantID --role $adminRoleID
sleep 1
}

function create_ext_net {
source $TOP_DIR/stackrc
EXT_NET_NAME=$EXT_NET_NAME
EXT_NET_SUBNET_NAME=$EXT_NET_SUBNET_NAME
EXT_NET_GATEWAY=$EXT_NET_GATEWAY
EXT_NET_ALLOCATION_POOL_START=$EXT_NET_ALLOCATION_POOL_START
EXT_NET_ALLOCATION_POOL_END=$EXT_NET_ALLOCATION_POOL_END
EXT_NET_CIDR=$EXT_NET_CIDR
EXT_NET_MASK=$EXT_NET_MASK

source $TOP_DIR/openrc neutron service
neutron net-create --router:external=true --shared $EXT_NET_NAME
neutron subnet-create --ip_version 4 --gateway $EXT_NET_GATEWAY --name $EXT_NET_SUBNET_NAME --allocation-pool start=$EXT_NET_ALLOCATION_POOL_START,end=$EXT_NET_ALLOCATION_POOL_END $EXT_NET_NAME $EXT_NET_CIDR/$EXT_NET_MASK
subnet_id=`neutron net-list | grep "$EXT_NET_NAME" | awk '{print $6}'`

}

function configure_nfp_params {
sudo sed -i "s/^subnet_id=\".*\"/subnet_id=\"$subnet_id\"/g" $NFP_SCRIPTS_DIR/nfp_gbp_params.sh
sudo sed -i "s/^inet_subnet=.*/inet_subnet=$EXT_NET_CIDR\/$EXT_NET_MASK/g" $NFP_SCRIPTS_DIR/nfp_gbp_params.sh
sudo sed -i "s/^inet_nat_pool=.*/inet_nat_pool=$EXT_NET_CIDR\/$EXT_NET_MASK/g" $NFP_SCRIPTS_DIR/nfp_gbp_params.sh
}

assign_user_credential
create_ext_net
configure_nfp_params
