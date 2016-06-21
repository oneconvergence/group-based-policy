#!/bin/bash
DEVSTACK_DIR=/home/stack/devstack

function configure_neutron_lbaasv2 {
 
    source input.sh
    if [ $TO = v2 ]; then
        echo "Configuring Loadbalancer V2 plugin driver"

        sudo sed -i "s/service_provider\ =\ LOADBALANCER:Haproxy:neutron_lbaas.services.loadbalancer.drivers.haproxy.plugin_driver.HaproxyOnHostPluginDriver/#service_provider\ =\ LOADBALANCER:Haproxy:neutron_lbaas.services.loadbalancer.drivers.haproxy.plugin_driver.HaproxyOnHostPluginDriver/g" /etc/neutron/neutron_lbaas.conf
        sudo sed -i "s/service_provider\ =\ LOADBALANCER:loadbalancer:gbpservice.nfp.service_plugins.loadbalancer.drivers.nfp_lbaas_plugin_driver.HaproxyOnVMPluginDriver:default/#service_provider\ =\ LOADBALANCER:loadbalancer:gbpservice.nfp.service_plugins.loadbalancer.drivers.nfp_lbaas_plugin_driver.HaproxyOnVMPluginDriver:default/g" /etc/neutron/neutron_lbaas.conf
        sudo sed -i "s/#service_provider\ =\ LOADBALANCERV2:loadbalancerv2:gbpservice.nfp.service_plugins.loadbalancer.drivers.nfp_lbaasv2_plugin_driver.HaproxyOnVMPluginDriver:default/service_provider\ =\ LOADBALANCERV2:loadbalancerv2:gbpservice.nfp.service_plugins.loadbalancer.drivers.nfp_lbaasv2_plugin_driver.HaproxyOnVMPluginDriver:default/g" /etc/neutron/neutron_lbaas.conf

    else
        echo "Configuring Loadbalancer V1 plugin driver"
        sudo sed -i "s/^#service_provider\ =\ LOADBALANCER:Haproxy:neutron_lbaas.services.loadbalancer.drivers.haproxy.plugin_driver.HaproxyOnHostPluginDriver/service_provider\ =\ LOADBALANCER:Haproxy:neutron_lbaas.services.loadbalancer.drivers.haproxy.plugin_driver.HaproxyOnHostPluginDriver/g" /etc/neutron/neutron_lbaas.conf
        sudo sed -i "s/^#service_provider\ =\ LOADBALANCER:loadbalancer:gbpservice.nfp.service_plugins.loadbalancer.drivers.nfp_lbaas_plugin_driver.HaproxyOnVMPluginDriver:default/service_provider\ =\ LOADBALANCER:loadbalancer:gbpservice.nfp.service_plugins.loadbalancer.drivers.nfp_lbaas_plugin_driver.HaproxyOnVMPluginDriver:default/g" /etc/neutron/neutron_lbaas.conf
        sudo sed -i "s/^service_provider\ =\ LOADBALANCERV2:loadbalancerv2:gbpservice.nfp.service_plugins.loadbalancer.drivers.nfp_lbaasv2_plugin_driver.HaproxyOnVMPluginDriver:default/#service_provider\ =\ LOADBALANCERV2:loadbalancerv2:gbpservice.nfp.service_plugins.loadbalancer.drivers.nfp_lbaasv2_plugin_driver.HaproxyOnVMPluginDriver:default/g" /etc/neutron/neutron_lbaas.conf

    fi


}
function configure_neutron {
    source input.sh
    if [ $TO = v2 ]; then
        sudo sed -i "s/neutron_lbaas.services.loadbalancer.plugin.LoadBalancerPlugin/neutron_lbaas.services.loadbalancer.plugin.LoadBalancerPluginv2/g" /etc/neutron/neutron.conf
    else
        sudo sed -i "s/neutron_lbaas.services.loadbalancer.plugin.LoadBalancerPluginv2/neutron_lbaas.services.loadbalancer.plugin.LoadBalancerPlugin/g" /etc/neutron/neutron.conf
    fi
}
function lbaas_mode_shifting {
    source $DEVSTACK_DIR/functions-common
    source $DEVSTACK_DIR/openrc neutron service

    # restart lbaas agent
    stop_process q-lbaas
    run_process q-lbaas "python /usr/local/bin/neutron-lbaasv2-agent --config-file /etc/neutron/neutron.conf --config-file /etc/neutron/neutron_lbaas.conf --config-file=/etc/neutron/services/loadbalancer/haproxy/lbaas_agent.ini"
    echo "restarted q-lbaas process"

     sleep 5   
    stop_process q-svc
    run_process q-svc "/usr/local/bin/neutron-server --config-file /etc/neutron/neutron.conf --config-file /etc/neutron/plugins/ml2/ml2_conf.ini"
    echo "restarted q-svc process"
    sleep 10


}
configure_neutron_lbaasv2
configure_neutron
lbaas_mode_shifting

source input.sh
sudo ssh-keygen -f "/root/.ssh/known_hosts" -R $config_ip

configurator_id=$(sudo ip netns exec nfp-proxy sshpass -p $CONFIGURATOR_PASS ssh -o StrictHostKeychecking=no $user@$config_ip "sudo docker ps | grep configurator-docker | cut -d' ' -f1")
echo $configurator_id
sudo ip netns exec nfp-proxy sshpass -p $CONFIGURATOR_PASS ssh -o StrictHostKeychecking=no $user@$config_ip "sudo docker restart $configurator_id"

