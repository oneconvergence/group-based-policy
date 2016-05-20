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

from gbpservice.nfp.config_orchestrator.agent import firewall as fw
from gbpservice.nfp.config_orchestrator.agent import loadbalancer as lb
from gbpservice.nfp.config_orchestrator.agent import loadbalancerv2 as lbv2
from gbpservice.nfp.config_orchestrator.agent import notification_handler as nh
from gbpservice.nfp.config_orchestrator.agent import \
    otc_service_events as otc_se
from gbpservice.nfp.config_orchestrator.agent import topics as a_topics
from gbpservice.nfp.config_orchestrator.agent import vpn as vp
from gbpservice.nfp.core.event import Event
from gbpservice.nfp.core.rpc import RpcAgent
from oslo_config import cfg


def rpc_init(sc, conf):
    fwrpcmgr = fw.FwAgent(conf, sc)
    fwagent = RpcAgent(
        sc,
        host=cfg.CONF.host,
        topic=a_topics.FW_NFP_CONFIGAGENT_TOPIC,
        manager=fwrpcmgr
    )

    lb_report_state = {
        'binary': 'NCO',
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

    lbv2_report_state = {
        'binary': 'NCO',
        'host': cfg.CONF.host,
        'topic': a_topics.LBV2_NFP_CONFIGAGENT_TOPIC,
        'plugin_topic': a_topics.LBV2_NFP_PLUGIN_TOPIC,
        'agent_type': 'NFP Loadbalancer V2 agent',
        'configurations': {'device_drivers': ['loadbalancerv2']},
        'start_flag': True,
        'report_interval': conf.reportstate_interval
    }
    lbv2rpcmgr = lbv2.Lbv2Agent(conf, sc)
    lbv2agent = RpcAgent(
        sc,
        host=cfg.CONF.host,
        topic=a_topics.LBV2_NFP_CONFIGAGENT_TOPIC,
        manager=lbv2rpcmgr,
        report_state=lbv2_report_state
    )

    vpn_report_state = {
        'binary': 'NCO',
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

    nhrpcmgr = nh.NotificationAgent(conf, sc)
    notificationagent = RpcAgent(
        sc,
        host=cfg.CONF.host,
        topic=a_topics.CONFIG_ORCH_TOPIC,
        manager=nhrpcmgr,
    )

    sc.register_rpc_agents([fwagent, lbagent, lbv2agent, vpnagent,
                            notificationagent])


def events_init(sc, conf):
    """Register event with its handler."""
    evs = [
        Event(id='SERVICE_CREATED',
              handler=otc_se.OTCServiceEventsHandler(sc, conf)),
        Event(id='SERVICE_DELETED',
              handler=otc_se.OTCServiceEventsHandler(sc, conf)),
        Event(id='SERVICE_CREATE_PENDING',
              handler=otc_se.OTCServiceEventsHandler(sc, conf))]

    sc.register_events(evs)


def nfp_module_init(sc, conf):
    rpc_init(sc, conf)
    events_init(sc, conf)
