from gbpservice.nfp.config_orchestrator.agent import topics
from gbpservice.nfp.configurator.drivers.loadbalancer.v2.haproxy import (
    haproxy_driver
)
from neutron_lbaas.drivers.common import agent_driver_base as adb


class HaproxyOnVMPluginDriver(adb.AgentDriverBase):
    device_driver = haproxy_driver.DRIVER_NAME

    def __init__(self, plugin):
        # Monkey patch LB agent topic and LB agent type
        adb.lb_const.LOADBALANCER_AGENTV2 = topics.LBV2_NFP_CONFIGAGENT_TOPIC
        adb.lb_const.AGENT_TYPE_LOADBALANCERV2 = 'NFP Loadbalancer V2 agent'

        super(HaproxyOnVMPluginDriver, self).__init__(plugin)

