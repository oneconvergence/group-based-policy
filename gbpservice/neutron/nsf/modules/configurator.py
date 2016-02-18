from oslo_log import log

from gbpservice.neutron.nsf.core.main import RpcAgent
from gbpservice.neutron.nsf.configurator.lib import topics
from gbpservice.neutron.nsf.configurator.lib.demuxer import ConfiguratorDemuxer
from gbpservice.neutron.nsf.configurator.lib.utils import Utils

LOG = log.getLogger(__name__)
AGENTS_PKG = 'gbpservice.neutron.nsf.configurator.agents'


class ConfiguratorRpcManager(object):
    def __init__(self, sc, sa, conf, demuxer):
        self.sc = sc
        self.conf = conf
        self.sa = sa
        self.demuxer = demuxer

    def _get_service_agent_obj(self, service_type):
        return self.sa.service_agent_objs[service_type]

    def _invoke_service_agent_method(self, method, request_data):
        try:
            sa_info_list = self.demuxer.get_service_agent_info(method,
                                                               request_data)
        except Exception as err:
            msg = ("Failed to demultiplex RPC requests in Configurator. " +
                   str(err).capitalize())
            LOG.error(msg)
            raise msg

        for sa_info in sa_info_list:
            try:
                sa_obj = self._get_service_agent_obj(sa_info['service_type'])
            except Exception as err:
                msg = ("Failed to get service agent object in Configurator. " +
                       str(err).capitalize())
                LOG.error(msg)
                raise msg

            try:
                getattr(sa_obj, sa_info['method'])(**sa_info['kwargs'])
            except Exception as err:
                msg = ("Failed to call service agent RPC manager from "
                       "Configurator. " + str(err).capitalize())
                LOG.error(msg)
                raise msg

    def create_network_device_config(self, context, request_data):
        self._invoke_service_agent_method('create', request_data)

    def delete_network_device_config(self, context, request_data):
        self._invoke_service_agent_method('delete', request_data)

    def create_network_service_config(self, context, request_data):
        self._invoke_service_agent_method('create', request_data)

    def delete_network_service_config(self, context, request_data):
        self._invoke_service_agent_method('delete', request_data)


class ConfiguratorModule(object):
    def __init__(self):
        self.service_agent_objs = {}
        self.imported_service_agents = []

    def register_service_agent(self, service_type, service_agent):
        if service_type not in self.service_agent_objs:
            self.service_agent_objs[service_type] = service_agent
            LOG.info(" Registered service_agent [%s] to handle"
                     " service [%s]" % (service_agent, service_type))
        else:
            LOG.warn(" Same service type [%s] being registered again with"
                     " service agent [%s] " % (service_type, service_agent))
            self.service_agent_objs[service_type] = service_agent

    def init_service_agents(self, sc, conf):
        for agent in self.imported_service_agents:
            try:
                agent.init_agent(self, sc, conf)
            except AttributeError as s:
                LOG.error(agent.__dict__)
                raise AttributeError(agent.__file__ + ': ' + str(s))
            except Exception as e:
                LOG.error(e)
                raise e

    def init_service_agents_complete(self, sc, conf):
        for agent in self.imported_service_agents:
            try:
                agent.init_agent_complete(self, sc, conf)
            except AttributeError as s:
                LOG.error(agent.__dict__)
                raise AttributeError(agent.__file__ + ': ' + str(s))
            except Exception as e:
                LOG.error(e)
                raise e


def init_rpc(sc, cm, conf, demuxer):
    rpc_mgr = ConfiguratorRpcManager(sc, cm, conf, demuxer)
    configurator_agent = RpcAgent(sc,
                                  topic=topics.CONFIGURATOR,
                                  manager=rpc_mgr)

    sc.register_rpc_agents([configurator_agent])


def get_configurator_module_handle():
    cm = ConfiguratorModule()
    cm.imported_service_agents = Utils().load_agents(AGENTS_PKG)
    LOG.info(" Imported agents %s " % (cm.imported_service_agents))
    return cm


def module_init(sc, conf):
    try:
        cm = get_configurator_module_handle()
        demuxer = ConfiguratorDemuxer()
    except Exception as err:
        LOG.error("Configurator Demuxer initialization unsuccessful. %s"
                  % (str(err).capitalize()))
        raise err
    else:
        LOG.debug("Configurator Demuxer initialization successful.")

    try:
        cm.init_service_agents(sc, conf)
        init_rpc(sc, cm, conf, demuxer)
    except Exception as err:
        LOG.error("Configurator RPC initialization unsuccessful. %s"
                  % (str(err).capitalize()))
        raise err
    else:
        LOG.debug("Configurator RPC initialization successful.")


def init_complete(sc, conf):
    cm = get_configurator_module_handle()
    cm.init_service_agents_complete(sc, conf)
