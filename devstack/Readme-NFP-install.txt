
Fresh Installation Steps:
=========================

(1) Clone stable mitaka devstack
    # cd /home/stack
    # git clone https://git.openstack.org/openstack-dev/devstack -b stable/mitaka

(2) Get NFP devstack configuration file
    # cd devstack/
    # wget -O local.conf https://raw.githubusercontent.com/oneconvergence/group-based-policy/mitaka_21st_march_base/devstack/local.conf.nfp

(3) Configure devstack

    * Base Mode Configuration:
        # Zero Configuration

    * Advanced Mode Configuration:
        # Devstack installation in enterprise mode
              NFP_DEVSTACK_MODE=advanced
        # External network details
              EXT_NET_GATEWAY=
              EXT_NET_ALLOCATION_POOL_START=
              EXT_NET_ALLOCATION_POOL_END=
              EXT_NET_CIDR=
        # Configurator VM image path, its optional
        # If configured, install step uploads the specified image
        # If not configured, install step will build a new one and upload it
              ConfiguratorQcow2Image=
        # Service VM image paths, they are optional
        # One can build service images referring to the section "Build service images".
        # If configured, install step uploads the specified images
        # If not configured, install step ignores uploading these service images.
              VyosQcow2Image=
              HaproxyQcow2Image=
        # Public interface name
              PUBLIC_INTERFACE=
        # Change the value of GBPSERVICE_BRANCH to use different branch(in OC repo)/patch(in Openstack repo)

(4) Run stack.sh from the /home/stack/devstack/ directory
    # ./stack.sh


Re-installation Steps:
======================

(1) Cleanup devstack
    # cd devstack
    # ./unstack.sh
    # ./clean.sh
    # sudo rm -rf /opt/stack
    # cd ..
    # sudo rm -rf devstack

(2) Follow the fresh installation steps


Build service images:
====================

Steps to get the scripts to build images
 # git clone -b mitaka_21st_march_base --single-branch https://github.com/oneconvergence/group-based-policy.git /home/stack/gbp_mitaka_21st_march_base

Steps to setup the diskimage build
 # sudo -H -E pip install -r /home/stack/gbp_mitaka_21st_march_base/gbpservice/tests/contrib/diskimage-create/requirements.txt
 # sudo apt-get install -y --force-yes qemu-utils
 # sudo apt-get install -y --force-yes dpkg-dev

Steps to build VyOS service image:
 # cd /home/stack/gbp_mitaka_21st_march_base/gbpservice/tests/contrib/diskimage-create/vyos/
 # sudo python vyos_image_create.py vyos_conf.json
Image location:
 # /home/stack/gbp_mitaka_21st_march_base/gbpservice/tests/contrib/diskimage-create/vyos/output/vyos.qcow2

Steps to build Haproxy service image:
 # cd /home/stack/gbp_mitaka_21st_march_base/gbpservice/tests/contrib/diskimage-create/
 # sudo python build_image.py haproxy_conf.json
Image location:
 # /home/stack/gbp_mitaka_21st_march_base/gbpservice/tests/contrib/diskimage-create/output/haproxy.qcow2


Upload service images:
=====================

Steps to upload VyOS service image:
 # glance image-create --name vyos --disk-format qcow2 --container-format bare --visibility public --file /home/stack/gbp_mitaka_21st_march_base/gbpservice/tests/contrib/diskimage-create/vyos/output/vyos.qcow2

Steps to upload Haproxy service image:
 # glance image-create --name haproxy --disk-format qcow2 --container-format bare --visibility public --file /home/stack/gbp_mitaka_21st_march_base/gbpservice/tests/contrib/diskimage-create/output/haproxy.qcow2
