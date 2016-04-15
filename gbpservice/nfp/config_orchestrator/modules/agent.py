#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from oslo_log import log as logging
from gbpservice.nfp.core.event import Event
from gbpservice.nfp.core.rpc import RpcAgent
from gbpservice.nfp.config_orchestrator.agent import firewall as fw
from gbpservice.nfp.config_orchestrator.agent import loadbalancer as lb
from gbpservice.nfp.config_orchestrator.agent import \
    otc_service_events as otc_se
from gbpservice.nfp.config_orchestrator.agent import topics as a_topics
from gbpservice.nfp.config_orchestrator.agent import vpn as vp
from oslo_config import cfg
from gbpservice.nfp.config_orchestrator.agent.l3 import NFPL3Agent


LOG = logging.getLogger(__name__)


def rpc_init(sc, conf):
    fwrpcmgr = fw.FwAgent(conf, sc)
    fwagent = RpcAgent(
        sc,
        host=cfg.CONF.host,
        topic=a_topics.FW_NFP_CONFIGAGENT_TOPIC,
        manager=fwrpcmgr
    )

    lb_report_state = {
        'binary': 'oc-lb-agent',
        'host': cfg.CONF.host,
        'topic': a_topics.LB_NFP_CONFIGAGENT_TOPIC,
        'plugin_topic': a_topics.LB_NFP_PLUGIN_TOPIC,
        'agent_type': 'NFP Loadbalancer agent',
        'configurations': {'device_drivers': ['loadbalancer']},
        'start_flag': True,
        'report_interval': conf.reportstate_interval
    }
    lbrpcmgr = lb.LbAgent(conf, sc)
    lbagent = RpcAgent(
        sc,
        host=cfg.CONF.host,
        topic=a_topics.LB_NFP_CONFIGAGENT_TOPIC,
        manager=lbrpcmgr,
        report_state=lb_report_state
    )

    vpn_report_state = {
        'binary': 'oc-vpn-agent',
        'host': cfg.CONF.host,
        'topic': a_topics.VPN_NFP_CONFIGAGENT_TOPIC,
        'plugin_topic': a_topics.VPN_NFP_PLUGIN_TOPIC,
        'agent_type': 'NFP Vpn agent',
        'configurations': {'device_drivers': ['vpn']},
        'start_flag': True,
        'report_interval': conf.reportstate_interval
    }
    vpnrpcmgr = vp.VpnAgent(conf, sc)
    vpnagent = RpcAgent(
        sc,
        host=cfg.CONF.host,
        topic=a_topics.VPN_NFP_CONFIGAGENT_TOPIC,
        manager=vpnrpcmgr,
        report_state=vpn_report_state
    )

    nfp_l3_mgr = NFPL3Agent(conf, sc)
    nfp_l3_agent = RpcAgent(sc, host=cfg.CONF.host,
                            topic=a_topics.NFP_L3_AGENT, manager=nfp_l3_mgr)

    sc.register_rpc_agents([fwagent, vpnagent, nfp_l3_agent])
    # sc.register_rpc_agents([fwagent, lbagent, vpnagent, nfp_l3_agent])


def events_init(controller, config, nfp_agents_obj):
    vpn_events = ['VPN_SERVICE_LAUNCHED', 'VPN_SERVICE_DELETED',
                  'VPN_SERVICE_ERRED']
    firewall_events = ['FW_INSTANCE_SPAWNING', 'FW_SERVICE_DELETE_IN_PROGRESS',
                       'FW_SERVICE_ERRED', 'ROUTERS_UPDATED',
                       'FW_INSTANCE_SPAWNING']
    events_to_register = []
    # for event in vpn_events:
    #   events_to_register.append(
    #        Event(id=event, handler=nfp_agents_obj.vpn_agent))
    for event in firewall_events:
        events_to_register.append(
                Event(id=event, handler=nfp_agents_obj.fw_agent))
    controller.register_events(events_to_register)


def nfp_module_init(sc, conf):
    rpc_init(sc, conf)
