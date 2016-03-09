#!/usr/bin/env bash

TOP_DIR=$4
GBP_SCRIPT_DIR=$3
#source $TOP_DIR/keystonerc_neutron neutron service
source $TOP_DIR/openrc neutron service
echo "wakeup_service.sh ImageName"
ConfiguratorQcow2ImageName=$1
VyosQcow2Image=$2
ConfiguratorImageName=configurator
VyosImageName=vyos
sudo bash $GBP_SCRIPT_DIR/oc_gbp_basic.sh $GBP_SCRIPT_DIR $TOP_DIR
sudo bash $GBP_SCRIPT_DIR/oc_gbp_script.sh $GBP_SCRIPT_DIR $TOP_DIR


if [ ! -z "$1" -a "$1" != " " ]; then
    ImageName=$1
    echo "Uploading Image : $ConfiguratorImageName $VyosImageName"
    glance image-create --name $ConfiguratorImageName --disk-format qcow2  --container-format bare  --visibility public --file $ConfiguratorQcow2ImageName
    glance image-create --name $VyosImageName --disk-format qcow2  --container-format bare  --visibility public --file $VyosQcow2Image
else
    echo "ImageName not provided ..."
    exit
fi

InstanceName="demo_configurator_instance"

GROUP="svc_management_ptg"
echo "GroupName: $GROUP"
PortId=$(gbp policy-target-create --policy-target-group $GROUP $InstanceName | grep port_id  | awk '{print $4}')

sleep 2
echo "Collecting ImageId : for $ConfiguratorImageName"
ImageId=`glance image-list|grep $ConfiguratorImageName |awk '{print $2}'`
if [ ! -z "$ImageId" -a "$ImageId" != " " ]; then
    echo $ImageId
else
    echo "No image found with name $ConfiguratorImageName ..."
    exit
fi

nova boot --flavor m1.medium --image $ImageId --nic port-id=$PortId $InstanceName
sleep 10

RouterId=`gbp l3p-show service_management_l3policy | grep routers|awk '{print $4}'`
echo "Collecting RouterId : for $RouterName"
if [ ! -z "$RouterId" -a "$RouterId" != " " ]; then
    echo $RouterId
else
    echo "Router creation failed with $RouterName ..."
    exit
fi

echo "Get IpAddr with port: $PortId"
IpAddr_extractor=`neutron port-list|grep $PortId|awk '{print $11}'`
IpAddr_purge_last=${IpAddr_extractor::-1}
IpAddr=${IpAddr_purge_last//\"/}
echo "Collecting IpAddr : for $PortId"
echo $IpAddr
sleep 2
#echo "Cleanup previous repo ..."
#rm -rf /tmp/demo_26thfeb2016
#sleep 1
#echo "Wait for a while Demo files getting clone to local Repository....."
#cd /tmp
#git clone -b demo_26thfeb2016 --single-branch https://github.com/oneconvergence/group-based-policy.git demo_26thfeb2016
#sleep 2
#echo "Copy binary files ...."
cd /opt/stack/gbp/gbpservice/nfp
mv bin/nfp /usr/bin/
sleep 1
chmod +x /usr/bin/nfp
mv bin/nfp_config_agent.ini /etc/
mv bin/nfp_orch_agent.ini /etc/
sleep 1
#echo "Copy starting for config_agent modules and proxy to nfp folder ..."
#if [ -d "/usr/lib/python2.7/dist-packages/gbpservice/" ] ; then
#cp -r ../nfp /usr/lib/python2.7/dist-packages/gbpservice/
#cd /usr/lib/python2.7/dist-packages/gbpservice/nfp
#elif [ -d "/usr/lib/python2.7/site-packages/gbpservice/" ] ; then
#cp -r ../nfp /usr/lib/python2.7/site-packages/gbpservice/
#cd /usr/lib/python2.7/site-packages/gbpservice/nfp
#elif [ -d "/opt/stack/gbp/gbpservice/" ] ; then
#cp -r ../nfp /opt/stack/gbp/gbpservice/
#cd /opt/stack/gbp/gbpservice/nfp
#else
#echo "it seems you dont have gbp installed please install and come back ..."
#exit
#fi
#sleep 1
echo "Configuring proxy.ini .... with rest_server_address as $IpAddr"
sed -i '/rest_server_address/d' proxy/proxy.ini
echo "rest_server_address=$IpAddr" >> proxy/proxy.ini
sleep 1
ipnetns_router=`ip netns |grep $RouterId`

echo "Starting config_agent  >>>> under screen named : config_agent"
screen -dmS "orchestrator" /usr/bin/nfp  --config-file /etc/neutron/neutron.conf --config-file /etc/neutron/plugins/ml2/ml2_conf.ini --config-file /etc/nfp_orch_agent.ini
echo "Starting proxy server under Router : $RouterId namespace $ipnetns_router >>>> under screen named : proxy"
ip netns exec $ipnetns_router screen -dmS "proxy" /usr/bin/python proxy/proxy.py --config-file=proxy/proxy.ini
sleep 1
echo "Starting config_agent  >>>> under screen named : config_agent"
screen -dmS "config_agent" /usr/bin/nfp  --config-file /etc/nfp_config_agent.ini --config-file /etc/neutron/neutron.conf --config-file /etc/neutron/plugins/ml2/ml2_conf.ini
sleep 1
echo "Running gbp-db-manage"
gbp-db-manage --config-file /etc/neutron/neutron.conf upgrade head
sleep 2
echo "Configuration success ... "
