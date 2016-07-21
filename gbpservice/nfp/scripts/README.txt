Steps to shift the advanced mode to enterprise mode:
===================================================

(1) Get the enterprise source
    # git clone\
 -b mitaka_21st_march_base\
 --single-branch\
 https://github.com/oneconvergence/group-based-policy.git\
 /home/stack/gbp_mitaka_21st_march_base

(2) Configure the /home/stack/gbp_mitaka_21st_march_base/gbpservice/nfp/config/mode_shift.conf
    # DEVSTACK_SRC_DIR=

    For shifting to enterprise,
    # VISIBILITY_GIT_BRANCH=master
    # GIT_ACCESS_USERNAME=
    # GIT_ACCESS_PASSWORD=
    # DOCKER_IMAGES_URL=http://192.168.100.50/docker_images/
    # AsavQcow2Image=
    # PaloAltoQcow2Image=

(3) Execute the script.
    # cd /home/stack/gbp_mitaka_21st_march_base/gbpservice/nfp/scripts/
    # bash mode_shift.sh 
