
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
            Example: [[ $ENABLE_NFP = True ]] && NFP_DEVSTACK_MODE=advanced
        # Change the value of GBPSERVICE_BRANCH to use different branch(in OC repo)/patch(in Openstack repo)
        # External network details
             EXT_NET_GATEWAY=
             EXT_NET_ALLOCATION_POOL_START=
             EXT_NET_ALLOCATION_POOL_END=
             EXT_NET_CIDR=
        # VyOS image path
            * Available only at 192.168.100.135:/home/stack/service_images/vyos.qcow2
            Example: VyosQcow2Image=/home/stack/images/vyos.qcow2
        # Haproxy LBaaS V2 image path
            Haproxy_LBaasV2_Qcow2Image=
        # Public interface
            Example: PUBLIC_INTERFACE=eth1

    * Enterprise Mode Configuration:
        # Devstack installation in enterprise mode
            Example: [[ $ENABLE_NFP = True ]] && NFP_DEVSTACK_MODE=enterprise
        # Change the value of GBPSERVICE_BRANCH to use different branch
        # External network details
            EXT_NET_GATEWAY=
            EXT_NET_ALLOCATION_POOL_START=
            EXT_NET_ALLOCATION_POOL_END=
            EXT_NET_CIDR=
        # VyOS image path
            * Available only at 192.168.100.135:/home/stack/service_images/vyos.qcow2
            Example: VyosQcow2Image=/home/stack/images/vyos.qcow2
        # Haproxy LBaaS V2 image path
            Haproxy_LBaasV2_Qcow2Image=
        # Public interface
            Example: PUBLIC_INTERFACE=eth1
        # Visibility GIT Repository Credentials
            GIT_ACCESS_USERNAME=
            GIT_ACCESS_PASSWORD=
        # Docker image path
            * Available only at 192.168.100.50. Change and configure for different nework
            DOCKER_IMAGES_URL=http://192.168.100.50/docker_images/
        # ASAv image path
            AsavQcow2Image=
        # PaloAlto image path
            PaloAltoQcow2Image=


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

