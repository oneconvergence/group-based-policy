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
from gbpservice.neutron.nsf.config_agent.generic import *
from gbpservice.neutron.nsf.config_agent.rpc_cb import *

from oslo_config import cfg
import oslo_messaging as messaging
from neutron.common import rpc as n_rpc

LOG = logging.getLogger(__name__)


def rpc_init(sc, conf):
    fwrpcmgr = FwAgent(conf, sc)
    fwagent = RpcAgent(
        sc,
        host=cfg.CONF.host,
        topic=topics.FW_NSF_CONFIGAGENT_TOPIC,
        manager=fwrpcmgr
    )

    lbrpcmgr = LbAgent(conf, sc)
    lbagent = RpcAgent(
        sc,
        host=cfg.CONF.host,
        topic=topics.LB_NSF_CONFIGAGENT_TOPIC,
        manager=lbrpcmgr
    )

    vpnrpcmgr = VpnAgent(conf, sc)
    vpnagent = RpcAgent(
        sc,
        host=cfg.CONF.host,
        topic=topics.VPN_NSF_CONFIGAGENT_TOPIC,
        manager=vpnrpcmgr
    )

    gcrpcmgr = GcAgent(conf, sc)
    gcagent = RpcAgent(
        sc,
        host=cfg.CONF.host,
        topic=topics.GC_NSF_CONFIGAGENT_TOPIC,
        manager=gcrpcmgr
    )

    sc.register_rpc_agents([fwagent, lbagent, vpnagent, gcagent])


def events_init(sc):
    evs = [
        Event(id='PULL_RPC_NOTIFICATIONS', handler=RpcCallback(sc))]
    sc.register_events(evs)


def module_init(sc, conf):
    rpc_init(sc, conf)
    events_init(sc)


def init_complete(sc, conf):
    ev = sc.event(id='PULL_RPC_NOTIFICATIONS', key='PULL_RPC_NOTIFICATIONS')
    sc.rpc_event(ev)
