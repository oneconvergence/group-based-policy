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

from gbpservice.nfp.config_orchestrator.agent import topics as a_topics
from gbpservice.nfp.core import common as nfp_common
from gbpservice.nfp.lib import transport

from neutron.common import constants as n_constants
from neutron.common import rpc as n_rpc
from neutron.common import topics as n_topics

from oslo_log import log as oslo_logging
import oslo_messaging as messaging

LOGGER = oslo_logging.getLogger(__name__)
LOG = nfp_common.log

# Version = 'v1'  # v1/v2/v3#


def prepare_request_data(context, resource, resource_type,
                         resource_data, service_vendor=None):

    request_data = {'info': {
        # Commenting version, may be need to remove later
        # 'version': Version,
        'context': context,
        'service_type': resource_type,
        'service_vendor': service_vendor  # Just keeping None for now.
    },

        'config': [{
            'resource': resource,
            'resource_data': resource_data
        }]
    }

    return request_data


def _filter_data(routers, networks, filters):
    # filter routers and networks data and formulate
    # dictionary of subnets, routers and ports for the
    # given tenant.
    tenant_id = filters['tenant_id'][0]
    _filtered_routers = []
    _filtered_subnets = []
    _filtered_ports = []
    for router in routers:
        if router['tenant_id'] == tenant_id:
            _filtered_routers.append({'id': router['id']})
    for network in networks:
        subnets = network['subnets']
        ports = network['ports']
        for subnet in subnets:
            if subnet['tenant_id'] == tenant_id:
                _filtered_subnets.append({'id': subnet['id'],
                                          'cidr': subnet['cidr'],
                                          'gateway_ip': subnet['gateway_ip']})
        for port in ports:
            if port['tenant_id'] == tenant_id:
                _filtered_ports.append({'id': port['id'],
                                        'fixed_ips': port['fixed_ips']})

    return {'subnets': _filtered_subnets,
            'routers': _filtered_routers,
            'ports': _filtered_ports}


def get_core_context(context, filters, host):
    routers = get_routers(context, host)
    networks = get_networks(context, host)
    return _filter_data(routers, networks, filters)


def get_routers(context, host):
    target = messaging.Target(topic=n_topics.L3PLUGIN, version='1.0')
    client = n_rpc.get_client(target)
    cctxt = client.prepare()
    return cctxt.call(context, 'sync_routers', host=host,
                      router_ids=None)


def get_networks(context, host):
    target = messaging.Target(
        topic=n_topics.PLUGIN,
        namespace=n_constants.RPC_NAMESPACE_DHCP_PLUGIN,
        version='1.0')
    client = n_rpc.get_client(target)
    cctxt = client.prepare(version='1.1')
    return cctxt.call(context, 'get_active_networks_info',
                      host=host)


def _prepare_structure(network_function_details, ports_info,
                       mngmt_port_info, monitor_port_info):
    return {'nfi_ports_map': {
        network_function_details[
            'network_function_instance'][
            'id']: ports_info},
            'nfi_nfd_map': {
                network_function_details[
                    'network_function_instance'][
                    'id']: {
                    'nfd': network_function_details[
                        'network_function_device'],
                    'nfd_mgmt_port': mngmt_port_info,
                    'nfd_monitoring_port': None,
                    'nfd_monitoring_port_network': network_function_details[
                        'network_function_device'][
                            'monitoring_port_network']}},
            'nfi': [network_function_details['network_function_instance']],
            'nf': network_function_details['network_function']
            }


def get_network_function_details(context, network_function_id):
    network_function_details = None
    try:
        rpc_nso_client = transport.RPCClient(a_topics.NFP_NSO_TOPIC)
        network_function_details = rpc_nso_client.cctxt.call(
            context,
            'get_network_function_details',
            network_function_id=network_function_id)
        LOG(LOGGER, 'INFO', " %s " % (network_function_details))
        return network_function_details['network_function']

    except Exception as e:
        LOG(LOGGER, 'ERROR', " %s " % (e))


def get_network_function_map(context, network_function_id):
    request_data = None
    try:
        rpc_nso_client = transport.RPCClient(a_topics.NFP_NSO_TOPIC)
        network_function_details = rpc_nso_client.cctxt.call(
            context,
            'get_network_function_details',
            network_function_id=network_function_id)
        ports_info = []
        for id in network_function_details[
                'network_function_instance']['port_info']:
            port_info = rpc_nso_client.cctxt.call(context,
                                                  'get_port_info',
                                                  port_id=id)
            ports_info.append(port_info)
        mngmt_port_info = rpc_nso_client.cctxt.call(
            context,
            'get_port_info',
            port_id=network_function_details[
                'network_function_device'][
                'mgmt_port_id'])
        monitor_port_id = network_function_details[
            'network_function_device']['monitoring_port_id']
        monitor_port_info = None
        if monitor_port_id is not None:
            monitor_port_info = rpc_nso_client.cctxt.call(
                context,
                'get_port_info',
                port_id=monitor_port_id)

        request_data = _prepare_structure(network_function_details, ports_info,
                                          mngmt_port_info, monitor_port_info)
        LOG(LOGGER, 'INFO', " %s " % (request_data))
    except Exception as e:
        LOG(LOGGER, 'ERROR', " %s " % (e))
        return request_data
    return request_data
