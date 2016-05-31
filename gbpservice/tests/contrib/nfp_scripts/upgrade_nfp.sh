#! /bin/bash

source upgrade_nfp.conf
source $DEVSTACK_DIR/local.conf

function create_visibility_image {
    source $DEVSTACK_DIR/openrc neutron service
    unset OS_USER_DOMAIN_ID
    unset OS_PROJECT_DOMAIN_ID

    # prepare visibility image and upload it into glance
    # assuming diskimage-create package requirements are already installed
    VISIBILITY_QCOW2_IMAGE=${VISIBILITY_QCOW2_IMAGE:-build}
    VISIBILITY_QCOW2_IMAGE_NAME=visibility
    if [[ $VISIBILITY_QCOW2_IMAGE = build ]]; then
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
}

function nfp_configure_nova {
    iniset $NOVA_CONF DEFAULT instance_usage_audit "True"
}

function prepare_for_upgrade {
    if [[ $FROM = advanced ]] && [[ $TO = enterprise ]]; then
        source $DEST/gbp/devstack/lib/nfp
        create_visibility_image
        launch_visibilityVM
        nfp_logs_forword
        nfp_configure_nova
    else
        echo "Not supported."
    fi
}

function upgrade {
    if [[ $FROM = advanced ]] && [[ $TO = enterprise ]]; then
        # edit nfp_proxy.ini with neutron port's fixed IP
        sed -e s//$VISIBILITY_VM_PORT_FIXED_IP/ nfp_proxy.ini

        # restart nfp_proxy
        service nfp_proxy restart

        # delete the configurator instance
        nova delete configurator

    else
        echo "Not supported."
    fi
}

echo "Task: Upgrade of NFP from $FROM mode to $TO mode."

echo "Preparing the upgrade..."
prepare_for_upgrade

echo "Upgrading to $TO mode..."
upgrade

