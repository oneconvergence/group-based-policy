from oslo_log import log as logging
from gbpservice.nfp.orchestrator.openstack.plumber import SCPlumber
from gbpservice.nfp.orchestrator.db import nfp_db as nfp_db
from gbpservice.nfp.orchestrator.db import api as nfp_db_api
# from gbpservice.nfp.core.main import Event
from gbpservice.nfp.core.rpc import RpcAgent
import constants as orchestrator_constants
import oslo_messaging

LOG = logging.getLogger(__name__)


def rpc_init(controller, config):
    rpcmgr = RpcHandler(config, controller)
    agent = RpcAgent(controller,
                     host=config.host,
                     topic=orchestrator_constants.NFP_NEUTRON_RENDERER_TOPIC,
                     manager=rpcmgr)
    controller.register_rpc_agents([agent])


def events_init(controller, config, so_helper):
    pass


def module_init(controller, config):
    events_init(controller, config, SOHelper(controller, config))
    rpc_init(controller, config)


class RpcHandler(object):
    RPC_API_VERSION = '1.0'
    target = oslo_messaging.Target(version=RPC_API_VERSION)

    def __init__(self, conf, controller):
        super(RpcHandler, self).__init__()
        self.so_helper = SOHelper(controller, conf)

    def neutron_update_nw_function_config(self, context, network_function):
        """
        RPC call().
        :param context:
        :param network_function:
        :return:
        """
        if not self.so_helper.get_service_details(network_function):
            network_function['action'] = \
                orchestrator_constants.NOOPS_ORCHESTRATION
        else:
            self.so_helper.prepare_network_function_request(network_function)
        return network_function

    def neutron_nw_function_delete(self, context, network_function):
        """
        RPC call()
        :param context:
        :param network_function:
        :return:
        """
        nw_function = self.so_helper.get_service_details(network_function)
        if nw_function:
            return nw_function[0]['id']
        else:
            return None


class SOHelper(object):
    def __init__(self, controller, config):
        self._config = config
        self._controller = controller
        self.db_handler = nfp_db.NFPDbBase()
        self.sc_plumber = SCPlumber()

    @property
    def db_session(self):
        return nfp_db_api.get_session()

    def prepare_network_function_request(self, nw_function_info):
        """
        :param nw_function_info:
        NOOP in GBP Case.
        In Neutron case:
        nw_function_info = {'network_function_mode': 'neutron',
                            'service_profile_id': service_profile_id,
                            'tenant_id': tenant_id,
                            'service_type': 'vpn/fw',
                            'service_id': 'VPN SERVICE ID',
                            'service_info': [{'router_id': <>, 'port': <>,
                                            'subnet': <>}]
                            }
        :return:
        """
        if nw_function_info['network_function_mode'].lower() != 'neutron':
            return
        else:
            fip_required = (True
                            if nw_function_info['service_type'].lower() ==
                            'vpn' else False)
            # This should return
            # {'id': <port id>, 'ip': <stitching ip>}
            stitching_port = self.sc_plumber.get_stitching_port(
                nw_function_info['tenant_id'], fip_required=fip_required)
            stitching_port.update(
                port_model=orchestrator_constants.NEUTRON_PORT,
                port_classification=orchestrator_constants.CONSUMER)
            nw_function_info['port_info'] = [stitching_port]
            nw_function_info['service_chain_id'] = None
            nw_function_info['management_network_info'] = dict(
                id=self.config.NEUTRON_SERVICE_MGMT_NW,
                port_model=orchestrator_constants.NEUTRON_PORT
            )
            self.sc_plumber.update_router_service_gateway(
                nw_function_info['router_id'],
                nw_function_info['service_info']['subnet']['cidr'],
                stitching_port['ip']
            )

    @staticmethod
    def update_attributes_for_vpn(nw_function_info):
        nw_function_info['port_info'].append(None)
        nw_function_info['share_existing_device'] = False

    @staticmethod
    def update_attributes_for_fw(nw_function_info):
        provider_port = {'id': nw_function_info['service_info']['port']['id'],
                         'port_model': orchestrator_constants.NEUTRON_PORT,
                         'port_classification':
                             orchestrator_constants.PROVIDER}
        nw_function_info['port_info'].append(provider_port)
        nw_function_info['service_id'] = provider_port['id']

    def get_service_details(self, nw_function_info):
        get_details = getattr(self, 'get_%s_service_details' %
                              nw_function_info['service_type'].lower())
        return get_details(nw_function_info)

    def get_vpn_service_details(self, nw_function_info):
        filters = dict(service_id=[nw_function_info['service_id']])
        return self.db_handler.get_network_functions(
            self.db_session, filters=filters)

    def get_fw_service_details(self, nw_function_info):
        filters = dict(service_id=[nw_function_info['service_info']['port'][
            'id']])
        return self.db_handler.get_network_functions(
            self.db_session, filters=filters)




