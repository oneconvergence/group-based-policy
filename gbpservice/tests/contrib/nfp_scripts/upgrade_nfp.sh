#! /bin/bash

source upgrade_nfp.conf
source $DEVSTACK_DIR/local.conf

TODO(DEEPAK): Should be retrieved from a result file populated by advanced mode.
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
}

function prepare_for_upgrade {
    if [[ $FROM = advanced ]] && [[ $TO = enterprise ]]; then
        source $DEST/gbp/devstack/lib/nfp

        echo "Preparing image creation"
        create_images

        echo "Launching the Visibility VM"
        launch_visibilityVM

        nfp_logs_forword
        nfp_configure_nova
        
    else
        echo "Not supported."
    fi
}

function delete_instance_and_image {
    
    # delete the instance
    echo "Deleting the running '$2' instance."
    nova delete $2
    
    echo "Deleting '$1' glance image."
    image_id=$(glance image-list | grep $1 | awk '{print $2}')
    glance image-delete $image_id
}
        

function restart_processes {
    source $DEVSTACK_DIR/functions-common
    source $DEVSTACK_DIR/openrc neutron service
    
    # restart proxy
    stop_process proxy
    run_process proxy "source $NFPSERVICE_DIR/devstack/lib/nfp;namespace_delete $TOP_DIR;namespace_create $TOP_DIR $IpAddr"
    echo "Restarted proxy process"
    sleep 10

    # restart proxy agent
    stop_process proxy_agent
    run_process proxy_agent "sudo /usr/bin/nfp --config-file /etc/nfp_proxy_agent.ini --log-file /opt/stack/logs/nfp_proxy_agent.log"
    echo "Restarted proxy agent process"
       
}


function upgrade {
    if [[ $FROM = advanced ]] && [[ $TO = enterprise ]]; then
        sed -i 's/rest_server_address=.*/rest_server_address='$IpAddr'/' /etc/nfp_proxy.ini

        echo "Restarting various processes"
        restart_processes

        image=configurator
        instance_name=configuratorVM_instance
        delete_instance_and_image $image $instance_name

    else
        echo "Not supported."
    fi
}


echo "Task: Upgrade of NFP from $FROM mode to $TO mode."

echo "Preparing for the upgrade."
prepare_for_upgrade

echo "Upgrading to $TO mode. There will be a little downtime. Kindly bear with me."
upgrade

echo "Successfully upgraded from $FROM mode to $TO mode."
