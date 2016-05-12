from gbpservice.nfp.config_orchestrator.agent import topics
from gbpservice.nfp.configurator.drivers.loadbalancer.v1.haproxy import (
    haproxy_lb_driver
)
from neutron_lbaas.services.loadbalancer.drivers.common import (
    agent_driver_base as adb
)
from neutron.common import topics as n_topics
from neutron.common import constants as n_const


class HaproxyOnVMPluginDriver(adb.AgentDriverBase):
    device_driver = haproxy_lb_driver.DRIVER_NAME

    def __init__(self, plugin):
        # Monkey patch LB agent topic and LB agent type
        n_topics.LOADBALANCER_AGENT = topics.LB_NFP_CONFIGAGENT_TOPIC
        n_const.AGENT_TYPE_LOADBALANCER = 'NFP Loadbalancer agent'

        super(HaproxyOnVMPluginDriver, self).__init__(plugin)

