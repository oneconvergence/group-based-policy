#!/usr/bin/env bash

TOP_DIR=$4
NFP_SCRIPTS_DIR=$3
source $TOP_DIR/openrc neutron service
function create_gbp_resources {
#sudo bash $NFP_SCRIPTS_DIR/nfp_gbp_basic.sh $NFP_SCRIPTS_DIR $TOP_DIR
sudo bash $NFP_SCRIPTS_DIR/nfp_gbp_script.sh $NFP_SCRIPTS_DIR $TOP_DIR

}

function upload_images_and_launch_configuratorVM {
source $TOP_DIR/openrc neutron service
ConfiguratorQcow2ImageName=$1
VyosQcow2Image=$2
ConfiguratorImageName=configurator
VyosImageName=vyos
if [ ! -z "$1" -a "$1" != " " ]; then
    ImageName=$1
    echo "Uploading Image : $ConfiguratorImageName $VyosImageName"
    glance image-create --name $ConfiguratorImageName --disk-format qcow2  --container-format bare  --visibility public --file $ConfiguratorQcow2ImageName
    glance image-create --name $VyosImageName --disk-format qcow2  --container-format bare  --visibility public --file $VyosQcow2Image
else
    echo "ImageName not provided ..."
    exit
fi

InstanceName="configurator_instance"

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

l2p_id=`gbp ptg-show svc_management_ptg | grep l2_policy_id | awk '{print $4}'`
l3p_id=`gbp l2p-show $l2p_id | grep l3_policy_id | awk '{print $4}'`
RouterId=`gbp l3p-show $l3p_id | grep routers | awk '{print $4}'`
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

}

function copy_nfp_files_and_start_process {

cd /opt/stack/gbp/gbpservice/nfp
sudo cp -r  bin/nfp /usr/bin/
sleep 1
sudo chmod +x /usr/bin/nfp
sudo cp -r  bin/nfp_config_agent.ini /etc/
sudo cp -r  bin/nfp_orch_agent.ini /etc/
sudo cp -r  bin/nfp_config_agent_proxy.ini /etc/
sleep 1

echo "Configuring proxy.ini .... with rest_server_address as $IpAddr"
sudo sed -i '/rest_server_address/d' agent_proxy/proxy/proxy.ini
echo "rest_server_address=$IpAddr" >> agent_proxy/proxy/proxy.ini
sleep 1
ipnetns_router=`sudo ip netns |grep $RouterId`



echo "Starting orchestrator  >>>> under screen named : orchestrator"
screen -dmS "orchestrator" /usr/bin/nfp  --config-file /etc/neutron/neutron.conf --config-file /etc/neutron/plugins/ml2/ml2_conf.ini --config-file /etc/nfp_orch_agent.ini --log-file /opt/stack/logs/nfp_orchestrator.log

echo "Starting config_agent_proxy  >>>> under screen named : config_agent_proxy"
screen -dmS "config_agent_proxy" /usr/bin/nfp  --config-file /etc/nfp_config_agent_proxy.ini
sleep 1

echo "Starting proxy server under Router : $RouterId namespace $ipnetns_router >>>> under screen named : proxy"
ip netns exec $ipnetns_router screen -dmS "proxy" /usr/bin/python agent_proxy/proxy/proxy.py --config-file=agent_proxy/proxy/proxy.ini
sleep 1
echo "Starting config_agent  >>>> under screen named : config_agent"
screen -dmS "config_agent" /usr/bin/nfp  --config-file /etc/nfp_config_agent.ini --config-file /etc/neutron/neutron.conf --config-file /etc/neutron/plugins/ml2/ml2_conf.ini
sleep 1


sleep 1
echo "Running gbp-db-manage"

source $TOP_DIR/openrc neutron service

gbp-db-manage --config-file /etc/neutron/neutron.conf upgrade head
sleep 2
echo "Configuration success ... "

}
create_gbp_resources
upload_images_and_launch_configuratorVM $1 $2 
copy_nfp_files_and_start_process
