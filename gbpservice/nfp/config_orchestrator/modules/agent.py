import os
import sys
import ast
import json
import time

from oslo_log import log as logging
from gbpservice.nfp.core.controller import Controller
from gbpservice.nfp.core.event import Event
from gbpservice.nfp.core.rpc import RpcAgent

from gbpservice.nfp.config_orchestrator.agent import topics as a_topics
from gbpservice.nfp.config_orchestrator.agent.firewall import *
from gbpservice.nfp.config_orchestrator.agent.loadbalancer import *
from gbpservice.nfp.config_orchestrator.agent.vpn import *
from gbpservice.nfp.config_orchestrator.agent.generic import *

from oslo_config import cfg
import oslo_messaging as messaging
from neutron.common import rpc as n_rpc

LOG = logging.getLogger(__name__)


def rpc_init(sc, conf):
    fwrpcmgr = FwAgent(conf, sc)
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
    lbrpcmgr = LbAgent(conf, sc)
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
    vpnrpcmgr = VpnAgent(conf, sc)
    vpnagent = RpcAgent(
        sc,
        host=cfg.CONF.host,
        topic=a_topics.VPN_NFP_CONFIGAGENT_TOPIC,
        manager=vpnrpcmgr,
        report_state=vpn_report_state
    )

    sc.register_rpc_agents([fwagent, lbagent, vpnagent])

def nfp_module_init(sc, conf):
    rpc_init(sc, conf)
