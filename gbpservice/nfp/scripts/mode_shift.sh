#! /bin/bash

SCRIPT_DIR=$PWD
ENTERPRISE_NFPSERVICE_DIR=$SCRIPT_DIR/../../../
source $SCRIPT_DIR/../config/mode_shift.conf
source $DEVSTACK_SRC_DIR/local.conf
INSTALLED_NFPSERVICE_DIR=$DEST/gbp
# BUGBUG(DEEPAK): Should be retrieved from a result file populated by advanced mode.
EXT_NET_NAME=ext-net

function setup_ssh_key {
    cd $SCRIPT_DIR
    sudo ssh-keygen -f "/root/.ssh/known_hosts" -R $configurator_ip
    sudo ssh-keygen -f configurator_vm -t rsa -N ''
    echo "Give the password for the root user of the Configurator VM when prompted."
    sleep 5
    cat configurator_vm.pub |\
 sudo ip netns exec nfp-proxy\
 ssh -o "StrictHostKeyChecking no" root@$configurator_ip\
 'cat >> .ssh/authorized_keys'
    sleep 5
}

function copy_files {
    cd $SCRIPT_DIR

    # Copy gbpservice/nfp from enterprise source
    sudo cp -r\
 $ENTERPRISE_NFPSERVICE_DIR/gbpservice/nfp\
 $INSTALLED_NFPSERVICE_DIR/gbpservice/

    # Copy gbpservice/contrib/nfp from enterprise source
    sudo cp -r\
 $ENTERPRISE_NFPSERVICE_DIR/gbpservice/contrib/nfp\
 $INSTALLED_NFPSERVICE_DIR/gbpservice/contrib/

    # Copy to Configurator from enterprise source
    sudo ip netns exec nfp-proxy\
 ssh -o "StrictHostKeyChecking no" -i configurator_vm root@$configurator_ip\
 mkdir /enterprise_src

    sudo ip netns exec nfp-proxy\
 scp -o "StrictHostKeyChecking no" -i configurator_vm -r\
 $ENTERPRISE_NFPSERVICE_DIR/gbpservice/nfp\
 root@$configurator_ip:/enterprise_src/
    sudo ip netns exec nfp-proxy\
 ssh -o "StrictHostKeyChecking no" -i configurator_vm root@$configurator_ip\
 docker cp\
 /enterprise_src/nfp\
 configurator:/usr/local/lib/python2.7/dist-packages/gbpservice/

    sudo ip netns exec nfp-proxy\
 scp -o "StrictHostKeyChecking no" -i configurator_vm -r\
 $ENTERPRISE_NFPSERVICE_DIR/gbpservice/contrib/nfp\
 root@$configurator_ip:/enterprise_src/contrib_nfp
    sudo ip netns exec nfp-proxy\
 ssh -o "StrictHostKeyChecking no" -i configurator_vm root@$configurator_ip\
 docker cp\
 /enterprise_src/contrib_nfp\
 configurator:/usr/local/lib/python2.7/dist-packages/gbpservice/contrib/
    sudo ip netns exec nfp-proxy\
 ssh -o "StrictHostKeyChecking no" -i configurator_vm root@$configurator_ip\
 docker exec configurator\
 rm -rf /usr/local/lib/python2.7/dist-packages/gbpservice/contrib/nfp
    sudo ip netns exec nfp-proxy\
 ssh -o "StrictHostKeyChecking no" -i configurator_vm root@$configurator_ip\
 docker exec configurator\
 mv /usr/local/lib/python2.7/dist-packages/gbpservice/contrib/contrib_nfp\
 /usr/local/lib/python2.7/dist-packages/gbpservice/contrib/nfp

    sudo ip netns exec nfp-proxy\
 ssh -o "StrictHostKeyChecking no" -i configurator_vm root@$configurator_ip\
 docker exec configurator\
 cp -r /usr/local/lib/python2.7/dist-packages/gbpservice/contrib/nfp/configurator/config /etc/nfp_config

    # Update the DB model
    sudo cp\
 $ENTERPRISE_NFPSERVICE_DIR/gbpservice/neutron/db/migration/alembic_migrations/versions/d2aab79622fe_nfp_enterprise_db.py\
 $INSTALLED_NFPSERVICE_DIR/gbpservice/neutron/db/migration/alembic_migrations/versions/
    echo "d2aab79622fe" > $INSTALLED_NFPSERVICE_DIR/gbpservice/neutron/db/migration/alembic_migrations/versions/HEAD
    gbp-db-manage --config-file /etc/neutron/neutron.conf upgrade head
}

function nfp_configure_nova {
    NOVA_CONF_DIR=/etc/nova
    NOVA_CONF=$NOVA_CONF_DIR/nova.conf
    source $DEVSTACK_SRC_DIR/inc/ini-config
    iniset $NOVA_CONF DEFAULT instance_usage_audit "True"

    for proc in n-cpu n-cond n-sch n-novnc n-cauth n-api; do
        # can be used to run the binary in a specific environment
        # A silly example will be 'watch free -m' where watch is the
        # sandbox and free is the proc 
        sandbox=
        param=--config-file\ /etc/nova/nova.conf
        # multiple config files can be given as space separated
        # e.g.: --config-file <conf file>\ --config-file\ <conf file>  
        extra_param=
        case $proc in
            n-cpu)
                sandbox=sg\ libvirtd
                proc_name=nova-compute
                ;;
            n-cond)
                proc_name=nova-conductor
                ;;
            n-sch)
                proc_name=nova-scheduler
                ;;
            n-novnc)
                proc_name=nova-novncproxy
                extra_param=--web\ /opt/stack/noVNC
                ;;
            n-cauth)
                proc_name=nova-consoleauth
                ;;
            n-api)
                proc_name=nova-api
                param=
                ;;
        esac
        restart_devstack_screen_processes "$proc" "$sandbox" "$proc_name" "$param" "$extra_param"
    done
}

function restart_devstack_screen_processes {
    SCREEN_NAME=stack
    SERVICE_DIR=$DEST/status/$SCREEN_NAME
    bin=/usr/local/bin
    proc_screen_name=$1
    sandbox=$2
    proc_name=$3
    param=$4
    extra_param=$5

    cmd=$bin/$proc_name\ $param\ $extra_param
    cmd="$(echo -e "${cmd}" | sed -e 's/[[:space:]]*$//')"
    
    if [[ ! -z "${sandbox// }" ]]; then
        cmd=$sandbox\ \'$cmd\'
    fi

    # stop the process
    screen -S $SCREEN_NAME -p $proc_screen_name -X kill
    sleep 4

    # start the process
    screen -S $SCREEN_NAME -X screen -t $proc_screen_name
    screen -S $SCREEN_NAME -p $proc_screen_name -X stuff "$cmd \
        & echo \$! >$SERVICE_DIR/${proc_screen_name}.pid; fg || \
        echo \"$proc_screen_name failed to start\" \
        | tee \"$SERVICE_DIR/${proc_screen_name}.failure\"\n"
    sleep 5
}

function create_port_for_vm {
# $1 is image_name
# $2 is instance name
    GROUP="svc_management_ptg"
    PortId=$(gbp policy-target-create --policy-target-group $GROUP $2 | grep port_id | awk '{print $4}')
    IpAddr_extractor=`neutron port-list --format value | grep $PortId | awk '{print $7}'`
    IpAddr_purge_last=${IpAddr_extractor::-1}
    IpAddr=${IpAddr_purge_last//\"/}
    echo "IpAddr of port($PortId): $IpAddr"
    visibility_image_name=$1
    visibility_port_id=$PortId
    visibility_ip=$IpAddr
}

function configure_vis_ip_addr_in_docker {
    cd $SCRIPT_DIR
    sudo ip netns exec nfp-proxy\
 ssh -o "StrictHostKeyChecking no" -i configurator_vm root@$configurator_ip\
 docker exec configurator\
 sed -i "s/log_forward_ip_address=*.*/log_forward_ip_address=$visibility_ip/" /etc/nfp_configurator.ini
}

function create_images {
    # prepare visibility image and upload it into glance
    VISIBILITY_QCOW2_IMAGE=${VISIBILITY_QCOW2_IMAGE:-build}
    VISIBILITY_QCOW2_IMAGE_NAME=visibility
    InstanceName="VisibilityVM_instance"
    create_port_for_vm $VISIBILITY_QCOW2_IMAGE_NAME $InstanceName
    # edits the docker file to add visibility vm IP address
    configure_vis_ip_addr_in_docker

    if [[ $VISIBILITY_QCOW2_IMAGE = build ]]; then
       # prepare visibility source, this is needed for diskimage build
       cd /home/stack/
       sudo rm -rf visibility
       sudo git clone\
 https://$GIT_ACCESS_USERNAME:$GIT_ACCESS_PASSWORD@github.com/oneconvergence/visibility.git\
 -b $VISIBILITY_GIT_BRANCH
       echo "Building Image: $VISIBILITY_QCOW2_IMAGE_NAME"
       cd $ENTERPRISE_NFPSERVICE_DIR/gbpservice/tests/contrib/diskimage-create/
       sudo python visibility_disk_image_create.py\
 visibility_conf.json $GBPSERVICE_BRANCH $DOCKER_IMAGES_URL
       VISIBILITY_QCOW2_IMAGE=$(cat output/last_built_image_path)
    fi
    echo "Uploading Image: $VISIBILITY_QCOW2_IMAGE_NAME"
    glance image-create\
 --name $VISIBILITY_QCOW2_IMAGE_NAME\
 --disk-format qcow2\
 --container-format bare\
 --visibility public\
 --file $VISIBILITY_QCOW2_IMAGE
    sleep 4
    
    if ! [[ -z $AsavQcow2Image ]]; then
        gbp service-profile-create\
 --servicetype FIREWALL\
 --insertion-mode l3\
 --shared True\
 --service-flavor service_vendor=asav,device_type=nova\
 --vendor NFP\
 asav_fw_profile

        ASAV_QCOW2_IMAGE_NAME=asav
        echo "Uploading Image: $ASAV_QCOW2_IMAGE_NAME"
        glance image-create\
 --name $ASAV_QCOW2_IMAGE_NAME\
 --disk-format qcow2\
 --container-format bare\
 --visibility public\
 --file $AsavQcow2Image
    fi

    if ! [[ -z $PaloAltoQcow2Image ]]; then
        PALO_ALTO_QCOW2_IMAGE_NAME=paloalto
        echo "Uploading Image: $PALO_ALTO_QCOW2_IMAGE_NAME"
        glance image-create\
 --name $PALO_ALTO_QCOW2_IMAGE_NAME\
 --disk-format qcow2\
 --container-format bare\
 --visibility public\
 --file $PaloAltoQcow2Image
    fi
}

function configure_visibility_user_data {
# $1 is the Visibility VM's IP address
    CUR_DIR=$PWD
    visibility_vm_ip=$1
    sudo rm -rf /opt/visibility_user_data
    sudo cp -r $ENTERPRISE_NFPSERVICE_DIR/devstack/exercises/nfp_service/user-data/visibility_user_data /opt/.
    cd /opt
    sudo rm -rf my.key my.key.pub
    sudo ssh-keygen -t rsa -N "" -f my.key
    value=`sudo cat my.key.pub`
    sudo echo $value
    sudo sed -i "s|<SSH PUBLIC KEY>|${value}|" visibility_user_data
    sudo sed -i "s/visibility_vm_ip=*.*/visibility_vm_ip=$visibility_vm_ip/g" visibility_user_data
    sudo sed -i "s/os_controller_ip=*.*/os_controller_ip=$HOST_IP/g" visibility_user_data
    sudo sed -i "s/statsd_host=*.*/statsd_host=$visibility_vm_ip/g" visibility_user_data
    sudo sed -i "s/rabbit_host=*.*/rabbit_host=$configurator_ip/g" visibility_user_data
    cd $CUR_DIR
}

function attach_security_groups {
    SecGroup="allow_all"
    nova secgroup-create $SecGroup "allow all traffic"
    nova secgroup-add-rule $SecGroup udp 1 65535 120.0.0.0/24
    nova secgroup-add-rule $SecGroup icmp -1 -1 120.0.0.0/24
    nova secgroup-add-rule $SecGroup tcp 1 65535 120.0.0.0/24
    nova secgroup-add-rule $SecGroup tcp 80 80 0.0.0.0/0
    nova secgroup-add-rule $SecGroup udp 514 514 0.0.0.0/0
    nova secgroup-add-rule $SecGroup tcp 443 443 0.0.0.0/0

    nova add-secgroup $InstanceName $SecGroup
}

function launch_visibilityVM {
    neutron net-create visibility-network
    neutron subnet-create visibility-network 188.0.0.0/24 --name visibility-subnet
    neutron router-create visibility-router
    neutron router-gateway-set visibility-router $EXT_NET_NAME
    neutron router-interface-add visibility-router visibility-subnet
    ExtPortId=$(neutron port-create visibility-network | grep ' id ' | awk '{print $4}')
    fip_id=$(neutron floatingip-create $EXT_NET_NAME | grep ' id '| awk '{print $4}')
    neutron floatingip-associate $fip_id $ExtPortId
    IpAddr_extractor=`neutron port-list --format value|grep $ExtPortId|awk '{print $6}'`
    IpAddr_purge_last=${IpAddr_extractor::-1}
    IpAddr2=${IpAddr_purge_last//\"/}
    echo "Collecting IpAddr : for $ExtPortId"
    echo $IpAddr2

    echo "Collecting ImageId : for $visibility_image_name"
    ImageId=`glance image-list|grep $visibility_image_name |awk '{print $2}'`
    if [ ! -z "$ImageId" -a "$ImageId" != " " ]; then
        echo $ImageId
    else
        echo "No image found with name $visibility_image_name ..."
        exit
    fi

    configure_visibility_user_data $visibility_ip
    echo "Launching Visibility image"
    nova boot\
 --image $ImageId\
 --flavor m1.xlarge\
 --user-data /opt/visibility_user_data\
 --nic port-id=$visibility_port_id\
 --nic port-id=$ExtPortId\
 $InstanceName
    sleep 10
    attach_security_groups
}

function nfp_logs_forword {
    VISIBILITY_CONF="/etc/rsyslog.d/visibility.conf"
    SYSLOG_CONFIG="/etc/rsyslog.conf"
    log_facility=local1

    sudo sed -i '/#$ModLoad imudp/ s/^#//' $SYSLOG_CONFIG
    sudo sed -i '/#$UDPServerRun 514/ s/^#//' $SYSLOG_CONFIG
    echo "Successfully enabled UDP in syslog"

    visibility_vm_ip_address=$(neutron floatingip-list --format value | grep "$IpAddr2" | awk '{print $3}')
    echo "$log_facility.* @$visibility_vm_ip_address:514" | sudo tee $VISIBILITY_CONF
    echo "Created $VISIBILITY_CONF file"

    sudo service rsyslog restart
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to restart rsyslog"
    fi
}

function restart_screen_process {
    SCREEN_NAME=stack
    SERVICE_DIR=$DEST/status
    name=$1
    cmd=$2

    # stop the process
    screen -S $SCREEN_NAME -p $name -X kill

    sleep 2

    # start the process
    screen -S $SCREEN_NAME -X screen -t $name
    screen -S $SCREEN_NAME -p $name -X stuff "$cmd & echo \$! >$SERVICE_DIR/$SCREEN_NAME/${name}.pid; fg || echo \"$name failed to start\" | tee \"$SERVICE_DIR/$SCREEN_NAME/${name}.failure\"\n"

    sleep 5
}

function restart_processes {
    cd $SCRIPT_DIR

    restart_screen_process nfp_orchestrator "sudo /usr/bin/nfp --config-file /etc/neutron/neutron.conf --config-file /etc/neutron/plugins/ml2/ml2_conf.ini --config-file /etc/nfp_orchestrator.ini --log-file $DEST/logs/nfp_orchestrator.log"

    # restart_screen_process nfp_proxy_agent "sudo /usr/bin/nfp --config-file /etc/nfp_proxy_agent.ini --log-file $DEST/logs/nfp_proxy_agent.log"

    # restart_screen_process nfp_proxy "source $INSTALLED_NFPSERVICE_DIR/devstack/lib/nfp; namespace_delete; namespace_create"

    restart_screen_process nfp_config_orchestrator "sudo /usr/bin/nfp --config-file /etc/nfp_config_orch.ini --config-file /etc/neutron/neutron.conf --log-file $DEST/logs/nfp_config_orchestrator.log"

    # restart nfp_configurator
    sudo ip netns exec nfp-proxy\
 ssh -o "StrictHostKeyChecking no" -i configurator_vm root@$configurator_ip\
 docker exec configurator screen -S configurator -X quit
    sudo ip netns exec nfp-proxy\
 ssh -o "StrictHostKeyChecking no" -i configurator_vm root@$configurator_ip\
 docker exec configurator screen -dmS "configurator" /usr/bin/python2 /usr/bin/nfp --config-file=/etc/nfp_configurator.ini --config-dir=/etc/nfp_config --log-file=/var/log/nfp/nfp_configurator.log
}

function prepare_for_mode_shift {
    if [[ $FROM = advanced ]] && [[ $TO = enterprise ]]; then
        source $DEVSTACK_SRC_DIR/openrc neutron service
        unset OS_USER_DOMAIN_ID
        unset OS_PROJECT_DOMAIN_ID

        # BUGBUG(RPM): Configurator's port name should be retrieved from a result file populated by advanced mode.
        configurator_ip=`neutron port-show pt_configuratorVM_instance -f value -c fixed_ips | cut -d'"' -f8`
        echo "Configurator's IP: $configurator_ip"

        echo "Setting up ssh key in configurator for password less ssh"
        setup_ssh_key
        echo "Copy files and configure"
        copy_files

        echo "Configuring nova"
        nfp_configure_nova
        sleep 10

        echo "Preparing image creation"
        create_images
        echo "Launching the Visibility VM"
        launch_visibilityVM
        nfp_logs_forword
    else
        echo "Shifting from $FROM mode to $TO mode is not supported."
    fi
}

function mode_shift {
    if [[ $FROM = advanced ]] && [[ $TO = enterprise ]]; then
        echo "Restarting various processes"
        restart_processes
    else
        echo "Shifting from $FROM mode to $TO mode is not supported."
    fi
}


echo "Task: Shifting mode of NFP from $FROM mode to $TO mode."

echo "Preparing for the NFP mode shift."
prepare_for_mode_shift

echo "Shifting NFP to $TO mode. There will be a little downtime. Kindly bear with it."
mode_shift

echo "Successfully shifted NFP from $FROM mode to $TO mode."
