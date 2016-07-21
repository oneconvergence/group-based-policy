Steps to shift the advanced mode to enterprise mode:
===================================================

(1) Get the enterprise source
    # ENTERPRISE_BRANCH=mitaka_21st_march_base
    # git clone -b $ENTERPRISE_BRANCH --single-branch https://github.com/oneconvergence/group-based-policy.git /home/stack/gbp_$ENTERPRISE_BRANCH

(2) Configure the /home/stack/gbp_$ENTERPRISE_BRANCH/gbpservice/nfp/config/mode_shift.conf
    # DEVSTACK_SRC_DIR=

    For shifting to enterprise,
    # VISIBILITY_GIT_BRANCH=master
    # GIT_ACCESS_USERNAME=
    # GIT_ACCESS_PASSWORD=
    # DOCKER_IMAGES_URL=http://192.168.100.50/docker_images/
    # AsavQcow2Image=
    # PaloAltoQcow2Image=

(3) Execute the script.
    # cd /home/stack/gbp_$ENTERPRISE_BRANCH/gbpservice/nfp/scripts/
    # bash mode_shift.sh 
