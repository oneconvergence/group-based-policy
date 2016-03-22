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

from oslo_config import cfg
from oslo_messaging import target
from oslo_log import log as logging
from neutron import manager
from neutron.common import rpc as n_rpc
from neutron.plugins.common import constants
from neutron.common import topics as n_topics
from neutron.common import constants as n_constants
LOG = logging.getLogger(__name__)
Version = 'v1'  # v1/v2/v3#


def get_dummy_context():
    context = {
        u'read_only': False,
        u'domain': None,
        u'project_name': None,
        u'user_id': None,
        u'show_deleted': False,
        u'roles': [],
        u'user_identity': u'',
        u'project_domain': None,
        u'tenant_name': None,
        u'auth_token': None,
        u'resource_uuid': None,
        u'project_id': None,
        u'tenant_id': None,
        u'is_admin': True,
        u'user': None,
        u'request_id': u'',
        u'user_domain': None,
        u'timestamp': u'',
        u'tenant': None,
        u'user_name': None}
    return context


def prepare_request_data(resource, kwargs, service_type):

    request_data = {'info': {
        'version': Version,
        'service_type': service_type
    },

        'config': [{
            'resource': resource,
            'kwargs': kwargs
        }]
    }

    return request_data


def _filter_data(routers, networks, filters):
    tenant_id = filters['tenant_id'][0]
    _filtered_routers = []
    _filtered_subnets = []
    _filtered_ports = []
    for router in routers:
        if router['tenant_id'] == tenant_id:
            _filtered_routers.append(router)
    for network in networks:
        subnets = network['subnets']
        ports = network['ports']
        for subnet in subnets:
            if subnet['tenant_id'] == tenant_id:
                _filtered_subnets.append(subnet)
        for port in ports:
            if port['tenant_id'] == tenant_id:
                _filtered_ports.append(port)

    return {'subnets': _filtered_subnets,
            'routers': _filtered_routers,
            'ports': _filtered_ports}


def get_core_context(context, filters, host):
    routers = get_routers(context, host)
    networks = get_networks(context, host)
    return _filter_data(routers, networks, filters)


def get_routers(context, host):
    _target = target.Target(topic=n_topics.L3PLUGIN, version='1.0')
    client = n_rpc.get_client(_target)
    cctxt = client.prepare()
    return cctxt.call(context, 'sync_routers', host=host,
                      router_ids=None)


def get_networks(context, host):
    _target = target.Target(
        topic=n_topics.PLUGIN,
        namespace=n_constants.RPC_NAMESPACE_DHCP_PLUGIN,
        version='1.0')
    client = n_rpc.get_client(_target)
    cctxt = client.prepare(version='1.1')
    return cctxt.call(context, 'get_active_networks_info',
                      host=host)
