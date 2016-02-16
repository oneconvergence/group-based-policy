import sys
import os
import oslo_messaging as messaging
from oslo_log import log
from gbpservice.neutron.nsf.core.main import RpcAgent
from gbpservice.neutron.nsf.configurator.lib import topics

LOG = log.getLogger(__name__)


def rpc_init(sc, conf, service_agents):
    configurator_rpc_mgr = ConfiguratorRpcManager(conf, sc, service_agents)
    configurator_agent = RpcAgent(sc,
                                  topics.GENERIC_CONFIG_RPC_TOPIC,
                                  configurator_rpc_mgr)

    sc.register_rpc_agents([configurator_agent])


class ConfiguratorRpcManager(object):
    def __init__(self, sc, conf, service_agents):
        self.sc = sc
        self.conf = conf
        self.service_agents = service_agents

    def _get_service_agent(self, service_type):
        return self.service_agents[service_type]

    ''' dummy representation '''
    def some_rpc(self, context):
        service_type = context['service']['type']
        agent = self._get_service_agent(service_type)
        agent.receive_rpc(context)

    def len(self):
        pass


class ServiceAgent(object):
    def __init__(self):
        self.service_agents = {}

    def register_service_agent(self, service_type, service_agent):
        if service_type not in self.service_agents:
            self.service_agents[service_type] = service_agent
            LOG.info(" Registered service_agent [%s] to handle"
                     " service [%s]" % (service_agent, service_type))
        else:
            LOG.warn(" Same service type [%s] being registered again with"
                     " service agent [%s] " % (service_type, service_agent))
            self.service_agents[service_type] = service_agent

    def service_agents_init(self, agents, sc, conf):
        for agent in agents:
            try:
                agent.agent_init(self, sc, conf)
            except AttributeError as s:
                LOG.error(agent.__dict__)
                raise AttributeError(agent.__file__ + ': ' + str(s))
            except Exception as e:
                LOG.error(e)
                raise e

    def service_agents_init_complete(self, sc, agents):
        for agent in agents:
            try:
                agent.agent_init_complete(sc)
            except AttributeError as s:
                LOG.error(agent.__dict__)
                raise AttributeError(agent.__file__ + ': ' + str(s))
            except Exception as e:
                LOG.error(e)
                raise e


def agents_import():
        pkg = 'gbpservice.neutron.nsf.configurator.agents'
        agents = []
        base_agent = __import__(pkg,
                                globals(), locals(), ['agents'], -1)
        agents_dir = base_agent.__path__[0]
        syspath = sys.path
        sys.path = [agents_dir] + syspath
        try:
            files = os.listdir(agents_dir)
        except OSError:
            print "Failed to read files"
            files = []

        for fname in files:
            if fname.endswith(".py") and fname != '__init__.py':
                agent = __import__(pkg,
                                   globals(), locals(), [fname[:-3]], -1)
                agents += [eval('agent.%s' % (fname[:-3]))]
                # modules += [__import__(fname[:-3])]
        sys.path = syspath
        return agents


def service_agents_init(sc, conf):
    agents = agents_import()
    sa = ServiceAgent()
    sa.service_agents_init(agents, sc, conf)
    return sa


def module_init(sc, conf):
    sa = service_agents_init(sc, conf)
    rpc_init(sc, conf, sa.service_agents)


def service_agents_init_complete(sc):
    agents = agents_import()
    sa = ServiceAgent()
    sa.service_agents_init_complete(sc, agents)
    return sa


def init_complete(sc, conf):
    service_agents_init_complete(sc)
