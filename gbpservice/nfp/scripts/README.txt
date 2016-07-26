

Steps to shift from NFP to NSD:
===============================

Pre-requisite:
--------------
NFP should be installed on the setup by following instructions from
gbpservice/devstack/Readme-NFP-install.txt

Steps:
------
(1) Get the enterprise source
    # ENTERPRISE_BRANCH=mitaka_21st_march_base
    # git clone -b $ENTERPRISE_BRANCH --single-branch https://github.com/oneconvergence/group-based-policy.git /home/stack/gbp_$ENTERPRISE_BRANCH

(2) Configure the /home/stack/gbp_$ENTERPRISE_BRANCH/gbpservice/nfp/config/mode_shift.conf
    Specify the path where the devstack git code is cloned.
    # DEVSTACK_SRC_DIR=

    Specify the following details of visibility
    # VISIBILITY_GIT_BRANCH=master
    # GIT_ACCESS_USERNAME=
    # GIT_ACCESS_PASSWORD=
    # DOCKER_IMAGES_URL=http://192.168.100.50/docker_images/

    Specification of the following image location is optional. If specified,
    these images will be uploaded to Openstack glance. Otherwise, user has
    to manually upload these image.
    # AsavQcow2Image=
    # PaloAltoQcow2Image=

(3) Execute the script.
    # cd /home/stack/gbp_$ENTERPRISE_BRANCH/gbpservice/nfp/scripts/
    # bash mode_shift.sh 
