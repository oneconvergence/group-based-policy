import os
import sys
import ast
import json
import time

from oslo_log import log as logging
from gbpservice.neutron.nsf.core.main import ServiceController
from gbpservice.neutron.nsf.core.main import Event
from gbpservice.neutron.nsf.core.main import RpcAgent

from gbpservice.neutron.nsf.config_agent import topics
from gbpservice.neutron.nsf.config_agent.firewall import *
from gbpservice.neutron.nsf.config_agent.loadbalancer import *
from gbpservice.neutron.nsf.config_agent.vpn import *
from gbpservice.neutron.nsf.config_agent.rpc_cb import *

from oslo_config import cfg
import oslo_messaging as messaging
from neutron.common import rpc as n_rpc

LOG = logging.getLogger(__name__)

def rpc_init(sc, conf):
    fwrpcmgr = FirewallAgent(conf, sc)
    fwagent = RpcAgent(
        sc,
        host=cfg.CONF.host,
        topic=topics.FW_NSF_CONFIGAGENT_TOPIC,
        manager=fwrpcmgr
    )

    lbrpcmgr = LbAgent(conf, sc)
    agent = RpcAgent(
        sc,
        host=cfg.CONF.host,
        topic=topics.LB_NSF_CONFIGAGENT_TOPIC,
        manager=lbrpcmgr
    )

    vpnrpcmgr = VpnAgent(conf, sc)
    agent = RpcAgent(
        sc,
        host=cfg.CONF.host,
        topic=topics.VPN_NSF_CONFIGAGENT_TOPIC,
        manager=vpnrpcmgr
    )

    sc.register_rpc_agents([fwrpcmgr, lbrpcmgr, vpnrpcmgr])

def events_init(sc):
    evs = [
        Event(id='RPCS_PULL_CALLBACKS_EVENT', handler=RpcCallback(sc))]

def module_init(sc, conf):
    rpc_init(sc, conf)
    events_init(sc)

def init_complete(sc, conf):
    ev = sc.event(id='RPCS_PULL_CALLBACKS_EVENT', key='RPCS_PULL_CALLBACKS_EVENT')
    sc.rpc_event(ev)
