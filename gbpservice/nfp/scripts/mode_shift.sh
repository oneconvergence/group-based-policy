#! /bin/bash

source /opt/stack/gbp/gbpservice/nfp/config/mode_shift.conf

DEVSTACK_DIR=/home/stack/devstack
source $DEVSTACK_DIR/local.conf
NFPSERVICE_DIR=/opt/stack/gbp
# TODO(DEEPAK): Should be retrieved from a result file populated by advanced mode.
EXT_NET_NAME=ext-net

function create_port_for_vm {
    image_name=$1

    GROUP="svc_management_ptg"
    echo "GroupName: $GROUP"
    PortId=$(gbp policy-target-create --policy-target-group $GROUP $InstanceName | grep port_id  | awk '{print $4}')

    echo "Getting IpAddr for port: $PortId"
    IpAddr_extractor=`neutron port-list|grep $PortId|awk '{print $11}'`
    IpAddr_purge_last=${IpAddr_extractor::-1}
    IpAddr=${IpAddr_purge_last//\"/}
    echo "Collecting IpAddr : for $PortId"
    echo $IpAddr 
}

function configure_vis_ip_addr_in_docker {
    echo "Visibility VM IP address is: $IpAddr"
    sed -i "s/VIS_VM_IP_ADDRESS/"$IpAddr"/" $NFPSERVICE_DIR/gbpservice/nfp/configurator/Dockerfile
}

function create_images {
    source $DEVSTACK_DIR/openrc neutron service
    unset OS_USER_DOMAIN_ID
    unset OS_PROJECT_DOMAIN_ID

    # prepare visibility image and upload it into glance
    VISIBILITY_QCOW2_IMAGE=${VISIBILITY_QCOW2_IMAGE:-build}
    VISIBILITY_QCOW2_IMAGE_NAME=visibility
    InstanceName="VisibilityVM_instance"
    create_port_for_vm $VISIBILITY_QCOW2_IMAGE_NAME

    if [[ $VISIBILITY_QCOW2_IMAGE = build ]]; then
       # edits the docker file to add visibility vm IP address
       configure_vis_ip_addr_in_docker

       # prepare visibility source, this is needed for diskimage build
       cd /home/stack/
       sudo rm -rf visibility
       sudo git clone https://$GIT_ACCESS_USERNAME:$GIT_ACCESS_PASSWORD@github.com/oneconvergence/visibility.git -b $VISIBILITY_GIT_BRANCH
       echo "Building Image: $VISIBILITY_QCOW2_IMAGE_NAME"
       cd $DEST/gbp/gbpservice/tests/contrib/diskimage-create/
       sudo python visibility_disk_image_create.py visibility_conf.json $DEVSTACK_DIR/local.conf
       VISIBILITY_QCOW2_IMAGE=$(cat /tmp/image_path)
    fi
    echo "Uploading Image: $VISIBILITY_QCOW2_IMAGE_NAME"
    glance image-create --name $VISIBILITY_QCOW2_IMAGE_NAME --disk-format qcow2 --container-format bare --visibility public --file $VISIBILITY_QCOW2_IMAGE
    sleep 4
    
    if ! [[ -z $AsavQcow2Image ]]; then
        gbp service-profile-create --servicetype FIREWALL --insertion-mode l3 --shared True --service-flavor service_vendor=asav,device_type=nova --vendor NFP asav_fw_profile

        ASAV_QCOW2_IMAGE_NAME=asav
        echo "Uploading Image: $ASAV_QCOW2_IMAGE_NAME"
        glance image-create --name $ASAV_QCOW2_IMAGE_NAME --disk-format qcow2 --container-format bare --visibility public --file $AsavQcow2Image
    fi
}

function nfp_configure_nova {
    NOVA_CONF_DIR=/etc/nova
    NOVA_CONF=$NOVA_CONF_DIR/nova.conf
    source $DEVSTACK_DIR/inc/ini-config
    iniset $NOVA_CONF DEFAULT instance_usage_audit "True"
    
    source $DEVSTACK_DIR/functions-common
    stop_process n-cpu
    stop_process n-cond 
    stop_process n-sch 
    stop_process n-novnc 
    stop_process n-cauth
    stop_process n-api 
    
    source $DEVSTACK_DIR/lib/nova
    start_nova_compute
    start_nova_api
    run_process n-cond "$NOVA_BIN_DIR/nova-conductor --config-file $NOVA_CONF"
    run_process n-sch "$NOVA_BIN_DIR/nova-scheduler --config-file $NOVA_CONF"
    run_process n-novnc "$NOVA_BIN_DIR/nova-novncproxy --config-file $NOVA_CONF --web $DEST/noVNC"
    run_process n-cauth "$NOVA_BIN_DIR/nova-consoleauth --config-file $NOVA_CONF"
}

function prepare_for_mode_shift {
    if [[ $FROM = advanced ]] && [[ $TO = enterprise ]]; then
        source $DEST/gbp/devstack/lib/nfp

        echo "Preparing image creation"
        create_images
        nfp_configure_nova
        sleep 10
        echo "Launching the Visibility VM"
        launch_visibilityVM

        nfp_logs_forword
    else
        echo "Shifting from $FROM mode to $TO mode is not supported."
    fi
}

function delete_instance_and_image {
    
    # delete the instance
    echo "Deleting the running '$2' instance."
    nova delete $2
    sleep 5
    
    echo "Deleting '$1' glance image."
    image_id=$(glance image-list | grep $1 | awk '{print $2}')
    glance image-delete $image_id
}
        

function restart_processes {
    source $DEVSTACK_DIR/functions-common
    source $DEVSTACK_DIR/openrc neutron service
    
    # restart proxy
    stop_process proxy
    run_process proxy "source $NFPSERVICE_DIR/devstack/lib/nfp;namespace_delete $DEVSTACK_DIR;namespace_create $DEVSTACK_DIR $IpAddr"
    echo "Restarted proxy process"
    sleep 10

    # restart proxy agent
    stop_process proxy_agent
    run_process proxy_agent "sudo /usr/bin/nfp --config-file /etc/nfp_proxy_agent.ini --log-file /opt/stack/logs/nfp_proxy_agent.log"
    echo "Restarted proxy agent process"
    sleep 3

}


function mode_shift {
    if [[ $FROM = advanced ]] && [[ $TO = enterprise ]]; then
        sudo sed -i 's/rest_server_address=.*/rest_server_address='$IpAddr'/' /etc/nfp_proxy.ini

        echo "Restarting various processes"
        restart_processes

        image=configurator
        instance_name=configuratorVM_instance
        delete_instance_and_image $image $instance_name
    else
        echo "Shifting from $FROM mode to $TO mode is not supported."
    fi
}


echo "Task: Shifting mode of NFP from $FROM mode to $TO mode."

echo "Preparing for the NFP mode shift."
prepare_for_mode_shift

echo "Shifting NFP to $TO mode. There will be a little downtime. Kindly bear with me."
mode_shift

echo "Successfully shifted NFP from $FROM mode to $TO mode."
