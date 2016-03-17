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

from gbpservice.nfp.configurator.lib import constants
from oslo_log import log as logging

LOG = logging.getLogger(__name__)

"""Implements supporting methods for configurator module.

Provides methods that take configurator API request data and helps
configurator to de-multiplex the API calls to different service agents
and drivers.

Format of request data for network device configuration API:
request_data {
    info {
        version: <v1/v2/v3>
    }
    config [
        {
            'resource': <healthmonitor/routes/interfaces>,
            'kwargs': <resource parameters>
        },
        {
        'resource': <healthmonitor/routes/interfaces>,
        'kwargs': <resource parameters>
        }, ...
    ]
}
Format of request data for network service configuration API:
request_data {
    info {
        version: <v1/v2/v3>
        type: <firewall/vpn/loadbalancer>
    }
    config [
        {
            'resource': <healthmonitor/routes/interfaces>,
            'kwargs': <resource parameters>
        },
        {
        'resource': <healthmonitor/routes/interfaces>,
        'kwargs': <resource parameters>
        }, ...
    ]
}

"""


class ServiceAgentDemuxer(object):
    def __init__(self):
        pass

    def get_service_type(self, request_data):
        """Retrieves service type from request data.

        :param request_data: API input data (format specified at top of file)

        Returns:
        (1) "firewall"/"vpn"/"loadbalancer"
        (2) "generic_config" if service_type field is absent in request_data
        (3) "invalid" if any other service type is provided in request_data

        """

        # Get service type based on the fact that for some request data
        # formats the 'type' key is absent. Check for invalid types
        service_type = request_data['info'].get('service_type')
        if (service_type not in constants.supported_service_types):
            return constants.invalid_service_type
        elif not service_type:
            service_type = 'generic_config'
            return service_type
        else:
            return service_type

    def get_service_agent_info(self, operation, service_type, request_data):
        """Prepares information for service agent consumption.

        :param operation: create/delete/update
        :param service_type: firewall/vpn/loadbalancer/generic_config
        :param request_data: API input data (format specified at top of file)

        Returns: List with the following format.
        sa_info_list [
            {
                'context': <context dictionary>
                'service_type': <firewall/vpn/loadbalancer/generic_config>
                'method': <*aas RPC methods/generic configuration methods>
                'kwargs' <kwargs taken from request data of API>
            }
        ]

        """

        sa_info_list = []

        for config_data in request_data['config']:
            sa_info = {}
            if service_type in constants.supported_service_types:
                sa_info.update({'service_type': service_type})
                if service_type == 'firewall':
                    method = operation + '_' + config_data['resource']
                elif service_type == 'vpn':
                    method = 'vpnservice_updated'
                elif service_type == 'loadbalancer':
                    method = operation + '_' + config_data['resource']
            else:
                sa_info.update({'service_type': 'generic'})
                if operation == 'create':
                    method = 'configure_' + config_data['resource']
                elif operation == 'delete':
                    method = 'clear_' + config_data['resource']
                elif operation == 'update':
                    method = 'update_' + config_data['resource']
                else:
                    return None

            sa_info.update({'method': method})
            sa_info.update({'resource': config_data['resource']})

            data = config_data['kwargs']
            if not data:
                return None

            context = config_data['kwargs']['context']
            sa_info.update({'context': context})
            del config_data['kwargs']['context']
            if 'generic' in sa_info['service_type']:
                sa_info.update({'kwargs': {'kwargs': data}})
            else:
                sa_info.update({'kwargs': data})
            sa_info_list.append(sa_info)

        return sa_info_list
