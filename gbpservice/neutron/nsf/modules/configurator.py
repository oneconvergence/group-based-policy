from oslo_log import log

from gbpservice.neutron.nsf.core.main import RpcAgent
from gbpservice.neutron.nsf.configurator.lib.demuxer import ConfiguratorDemuxer
from gbpservice.neutron.nsf.configurator.lib.utils import ConfiguratorUtils
from gbpservice.neutron.nsf.configurator.lib import constants as const

LOG = log.getLogger(__name__)
AGENTS_PKG = 'gbpservice.neutron.nsf.configurator.agents'
CONFIGURATOR_RPC_TOPIC = 'configurator'

class ConfiguratorRpcManager(object):
    def __init__(self, sc, sa, conf, demuxer):
        self.sc = sc
        self.conf = conf
        self.sa = sa
        self.demuxer = demuxer

    def _get_service_agent_obj(self, service_type):
        return self.sa.service_agent_objs[service_type]

    def _invoke_service_agent_method(self, context, method, request_data):
        service_type = self.demuxer.get_service_type(request_data)
        if (service_type == const.invalid_service_type):
            msg = ("Invalid service type %s received." % service_type)
            raise Exception(msg)

        sa_info_list = self.demuxer.get_service_agent_info(
                                                    method,
                                                    service_type,
                                                    request_data)
        if not sa_info_list:
            msg = ("Invalid data format received for service type %s."
                   "Data format: %r" % (service_type, request_data))
            raise Exception(msg)

        sa_obj = self._get_service_agent_obj(service_type)
        if not sa_obj:
            msg = ("Failed to find agent with service type %s." % service_type)
            raise Exception(msg)
        
        notification_data = []
        sa_obj.process_request(context, sa_info_list, notification_data)
        

    def create_network_device_config(self, context, request_data):
        try:
            self._invoke_service_agent_method(context, 'create', request_data)
        except Exception as err:
            msg = ("Failed to create network device configuration." +
                   str(err).capitalize())
            LOG.error(msg)

    def delete_network_device_config(self, context, request_data):
        try:
            self._invoke_service_agent_method(context, 'delete', request_data)
        except Exception as err:
            msg = ("Failed to delete network device configuration." +
                   str(err).capitalize())
            LOG.error(msg)        

    def update_network_device_config(self, context, request_data):
        try:
            self._invoke_service_agent_method(context, 'update', request_data)
        except Exception as err:
            msg = ("Failed to update network device configuration." +
                   str(err).capitalize())
            LOG.error(msg)        

    def create_network_service_config(self, context, request_data):
        try:
            self._invoke_service_agent_method(context, 'create', request_data)
        except Exception as err:
            msg = ("Failed to create network service configuration." +
                   str(err).capitalize())
            LOG.error(msg)

    def delete_network_service_config(self, context, request_data):
        try:
            self._invoke_service_agent_method(context, 'delete', request_data)
        except Exception as err:
            msg = ("Failed to delete network device configuration." +
                   str(err).capitalize())
            LOG.error(msg)
    
    def update_network_service_config(self, context, request_data):
        try:
            self._invoke_service_agent_method(context, 'update', request_data)
        except Exception as err:
            msg = ("Failed to update network device configuration." +
                   str(err).capitalize())
            LOG.error(msg)        

    def get_notification(self):
        pass
    
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
                                  topic=CONFIGURATOR_RPC_TOPIC,
                                  manager=rpc_mgr)

    sc.register_rpc_agents([configurator_agent])


def get_configurator_module_handle():
    cm = ConfiguratorModule()
    cm.imported_service_agents = ConfiguratorUtils().load_agents(AGENTS_PKG)
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
