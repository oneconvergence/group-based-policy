
TOP_DIR=$2
GBP_SCRIPT_DIR=$1
source $TOP_DIR/openrc admin admin
#set -x
serviceTenantID=`keystone tenant-list | grep "service" | awk '{print $2}'`
serviceRoleID=`keystone role-list | grep "service" | awk '{print $2}'`
adminRoleID=`keystone role-list | grep "admin" | awk '{print $2}'`
keystone user-role-add --user nova --tenant $serviceTenantID --role $serviceRoleID
sleep 1
keystone user-role-add --user neutron --tenant $serviceTenantID --role $adminRoleID
sleep 1


EXT_NET_NAME=$3
EXT_NET_SUBNET_NAME=$4
EXT_NET_GATEWAY=$5
EXT_NET_ALLOCATION_POOL_START=$6
EXT_NET_ALLOCATION_POOL_END=$7
EXT_NET_CIDR=$8
EXT_NET_MASK=$9

source $TOP_DIR/openrc neutron service
neutron net-create --router:external=true --shared $EXT_NET_NAME
neutron subnet-create --ip_version 4 --gateway $EXT_NET_GATEWAY --name $EXT_NET_SUBNET_NAME --allocation-pool start=$EXT_NET_ALLOCATION_POOL_START,end=$EXT_NET_ALLOCATION_POOL_END $EXT_NET_NAME $EXT_NET_CIDR/$EXT_NET_MASK
subnet_id=`neutron net-list | grep "$EXT_NET_NAME" | awk '{print $6}'`

sudo sed -i "s/^subnet_id=\".*\"/subnet_id=\"$subnet_id\"/g" $1/oc_gbp_params.sh
sudo sed -i "s/^inet_subnet=.*/inet_subnet=$EXT_NET_CIDR\/$EXT_NET_MASK/g" $1/oc_gbp_params.sh
sudo sed -i "s/^inet_nat_pool=.*/inet_nat_pool=$EXT_NET_CIDR\/$EXT_NET_MASK/g" $1/oc_gbp_params.sh
