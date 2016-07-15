
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
        # Service VM image path(s)
        # (optional - Leave them empty, so that they will be built during installation)
              ConfiguratorQcow2Image=
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

