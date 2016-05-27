#DISK_IMAGE_DIR=/home/dhuldev/UPGARDE/group-based-policy/gbpservice/tests/contrib/
DISK_IMAGE_DIR=/opt/stack/gbp/gbpservice/tests/contrib/
function prepare_nfp_image_builder {
    sudo -H -E pip install -r $DISK_IMAGE_DIR/diskimage-create/requirements.txt
    sudo apt-get install -y --force-yes qemu-utils
    sudo wget -qO- https://get.docker.com/ | bash
}

function create_nfp_image {
    cd /home/stack
    sudo rm -rf visibility
    #sudo git clone https://$GIT_ACCESS_USERNAME:$GIT_ACCESS_PASSWORD@github.com/oneconvergence/visibility.git -b $VISIBILITY_GIT_BRANCH
    sudo git clone https://sriharshabarkuru:sri1990@github.com/oneconvergence/visibility.git -b master

    sudo python $DISK_IMAGE_DIR/diskimage-create/visibility_disk_image_create.py $DISK_IMAGE_DIR/diskimage-create/visibility_conf.json $DISK_IMAGE_DIR/diskimage-create/local.conf
    VisibilityQcow2Image=$(cat /tmp/image_path)

}
prepare_nfp_image_builder
create_nfp_image
