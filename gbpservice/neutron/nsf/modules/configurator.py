import oslo_messaging as messaging
from oslo_log import log
from oslo_config import cfg
from gbpservice.neutron.nsf.core.main import Event
from gbpservice.neutron.nsf.core.main import RpcAgent
from gbpservice.neutron.nsf.configurator.lib import topics

from gbpservice.neutron.nsf.configurator.agents.firewall import \
                            FWaasRpcManager, FWaasEventHandler
from gbpservice.neutron.nsf.configurator.agents.vpn import \
                            VPNaasRpcManager, VPNaasEventHandler
from gbpservice.neutron.nsf.configurator.agents.loadbalancer import \
                            LBaasRpcManager, LBaasEventHandler
from gbpservice.neutron.nsf.configurator.agents.generic_config import \
                            GenericConfigRpcManager, GenericConfigEventHandler

LOG = log.getLogger(__name__)


def rpc_init(sc, conf):
    # FWaaS agent
    fw_agent_state = {
            'start_flag': True,
            'binary': 'nsf-fw-module',
            'host': conf.host,
            'topic': topics.FWAAS_AGENT_RPC_TOPIC,
            'plugin_topic': topics.FWAAS_PLUGIN_RPC_TOPIC,
            'agent_type': 'OC Firewall Agent',
            'configurations': {
                'driver': 'OC Firewall Driver'
            },
            'report_interval': 10,
            'description': 'OC Firewall Agent'
        }

    fw_rpc_receiver = FWaasRpcManager(conf, sc)
    fw_agent = RpcAgent(sc,
                        topics.FWAAS_AGENT_RPC_TOPIC,
                        fw_rpc_receiver,
                        fw_agent_state)

    # VPNaaS agent
    vpn_rpc_receiver = VPNaasRpcManager(conf, sc)

    vpn_agent = RpcAgent(sc,
                         topics.VPNAAS_AGENT_RPC_TOPIC,
                         vpn_rpc_receiver)

    # LBaaS agent
    lb_agent_state = {
        'binary': 'nsf-lb-module',
        'host': conf.host,
        'topic': topics.LBAAS_AGENT_RPC_TOPIC,
        'report_interval': 10,
        'plugin_topic': topics.LBAAS_PLUGIN_RPC_TOPIC,
        'configurations': {'device_drivers': 'haproxy_on_vm'},
        'agent_type': 'OC Loadbalancer Agent',
        'start_flag': True,
    }

    lb_rpc_receiver = LBaasRpcManager(conf, sc)
    lb_agent = RpcAgent(sc,
                        topics.LBAAS_AGENT_RPC_TOPIC,
                        lb_rpc_receiver,
                        lb_agent_state)

    # Generic Config Agent
    generic_config_rpc_receiver = GenericConfigRpcManager(conf, sc)
    generic_config_agent = RpcAgent(sc,
                                    topics.GENERIC_CONFIG_RPC_TOPIC,
                                    generic_config_rpc_receiver)

    sc.register_rpc_agents([fw_agent, vpn_agent, lb_agent,
                            generic_config_agent])


def events_init(sc):
    evs = [

        # Events for FWaaS standard RPCs coming from FWaaS Plugin
        Event(id='CREATE_FIREWALL', handler=FWaasEventHandler(sc)),
        Event(id='UPDATE_FIREWALL', handler=FWaasEventHandler(sc)),
        Event(id='DELETE_FIREWALL', handler=FWaasEventHandler(sc)),

        # Events for VPNaaS standard RPCs coming from VPNaaS Plugin
        Event(id='VPNSERVICE_UPDATED', handler=VPNaasEventHandler(sc)),

        # Events for LBaaS standard RPCs coming from LBaaS Plugin
        Event(id='CREATE_VIP', handler=LBaasEventHandler(sc)),
        Event(id='UPDATE_VIP', handler=LBaasEventHandler(sc)),
        Event(id='DELETE_VIP', handler=LBaasEventHandler(sc)),

        Event(id='CREATE_POOL', handler=LBaasEventHandler(sc)),
        Event(id='UPDATE_POOL', handler=LBaasEventHandler(sc)),
        Event(id='DELETE_POOL', handler=LBaasEventHandler(sc)),

        Event(id='CREATE_MEMBER', handler=LBaasEventHandler(sc)),
        Event(id='UPDATE_MEMBER', handler=LBaasEventHandler(sc)),
        Event(id='DELETE_MEMBER', handler=LBaasEventHandler(sc)),

        Event(id='CREATE_POOL_HEALTH_MONITOR', handler=LBaasEventHandler(sc)),
        Event(id='UPDATE_POOL_HEALTH_MONITOR', handler=LBaasEventHandler(sc)),
        Event(id='DELETE_POOL_HEALTH_MONITOR', handler=LBaasEventHandler(sc)),
        Event(id='AGENT_UPDATED', handler=LBaasEventHandler(sc)),

        # Events for RPCs coming from orchestrator
        Event(id='CONFIGURE_INTERFACES', handler=GenericConfigEventHandler(
                                                                       sc)),
        Event(id='CLEAR_INTERFACES', handler=GenericConfigEventHandler(sc)),
        Event(id='CONFIGURE_SOURCE_ROUTES', handler=GenericConfigEventHandler(
                                                                       sc)),
        Event(id='DELETE_SOURCE_ROUTES', handler=GenericConfigEventHandler(
                                                                       sc)),
        # Poll Events triggered internally
        Event(id='COLLECT_STATS', handler=LBaasEventHandler(sc))
        ]

    sc.register_events(evs)


def module_init(sc, conf):
    rpc_init(sc, conf)
    events_init(sc)


def _start_collect_stats(sc):
    arg_dict = {}
    ev = sc.event(id='COLLECT_STATS', data=arg_dict)
    sc.rpc_event(ev)


def init_complete(sc, conf):
    # where to trigger looping events like collect stats ?
    _start_collect_stats(sc)
