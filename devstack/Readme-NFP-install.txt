
Fresh Installation Steps:
=========================

(1) Clone stable mitaka devstack
    # cd /home/stack
    # git clone https://git.openstack.org/openstack-dev/devstack -b stable/mitaka

(2) Get NFP devstack configuration file
    # wget https://raw.githubusercontent.com/oneconvergence/group-based-policy/mitaka_21st_march_base/devstack/local.conf.nfp
    # mv local.conf.nfp /home/stack/devstack/local.conf

(3) Configure devstack

    * Base Mode Configuration:
        # Zero Configuration

    * Advanced Mode Configuration:
        # To trigger advanced mode installation
            Example: [[ $ENABLE_NFP = True ]] && DEVSTACK_MODE=advanced
        # VyOS image path 
           * Available only at 192.168.100.135:/home/stack/service_images/vyos.qcow2
            Example: VyosQcow2Image=/home/stack/images/vyos.qcow2
        # Public interface
            Example: PUBLIC_INTERFACE=eth1

    * Enterprise Mode Configuration:
         # Devstack installation in enterprise mode
             Example: [[ $ENABLE_NFP = True ]] && DEVSTACK_MODE=enterprise
         # VyOS image path
            * Available only at 192.168.100.135:/home/stack/service_images/vyos.qcow2
             Example: VyosQcow2Image=/home/stack/images/vyos.qcow2
         # Public interface
             Example: PUBLIC_INTERFACE=eth1
         # External network details
             EXT_NET_GATEWAY=
             EXT_NET_ALLOCATION_POOL_START=
             EXT_NET_ALLOCATION_POOL_END=
             EXT_NET_CIDR=
             EXT_NET_MASK=
         # Visibility GIT Repository Credentials
             GIT_ACCESS_USERNAME=
             GIT_ACCESS_PASSWORD=
         # Docker image path
             * Available only at 192.168.100.50. Change and configure for different nework
             DOCKER_IMAGES_URL=http://192.168.100.50/docker_images/

(4) Run stack.sh from the /home/stack/devstack/ directory
    # cd /home/stack/devstack
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

