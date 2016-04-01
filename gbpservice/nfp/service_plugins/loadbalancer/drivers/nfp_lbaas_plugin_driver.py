from gbpservice.nfp.config_orchestrator.agent import topics
from gbpservice.nfp.configurator.drivers.loadbalancer.v1.haproxy import (
    haproxy_lb_driver
)
from neutron_lbaas.services.loadbalancer.drivers.common import (
    agent_driver_base as adb
)


class HaproxyOnVMPluginDriver(adb.AgentDriverBase):
    device_driver = haproxy_lb_driver.DRIVER_NAME

    def __init__(self, plugin):
        # Monkey patch LB agent topic and LB agent type
        adb.l_const.LOADBALANCER_AGENT = topics.LB_NFP_CONFIGAGENT_TOPIC
        adb.q_const.AGENT_TYPE_LOADBALANCER = 'NFP Loadbalancer agent'

        # TODO (RPM): RPC API version 2.0 is not integration tested
        # Till then this is a workaround to use RPC API 1.0
        adb.LoadBalancerCallbacks.target.version = '1.0'

        super(HaproxyOnVMPluginDriver, self).__init__(plugin)

        # TODO (RPM): RPC API version 2.0 is not integration tested
        # Till then this is a workaround to use RPC API 1.0
        self.agent_rpc.client.target.version = '1.0'
