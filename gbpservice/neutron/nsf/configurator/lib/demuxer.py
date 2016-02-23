
from gbpservice.neutron.nsf.configurator.lib import constants

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


class ConfiguratorDemuxer(object):
    def __init__(self):
        pass

    def validate_request(self, request_data):
        """Validates request data and its parameter format.

        :param request_data: API input data

        Returns:
        (1) "firewall"/"vpn"/"loadbalancer"
        (2) "generic_config" if service_type field is absent in request_data
        (3) "invalid" if any other service type is provided in request_data

        """

        # Type checks
        if (isinstance(request_data, dict) and
                isinstance(request_data['info'], dict) and
                isinstance(request_data['config'], list)):
            return True
        else:
            return False

        # Validation for malformed request data
        if not (request_data and
                request_data['info'] and
                request_data['config'] and
                request_data['info']['version'] and
                (len(request_data['config']) > 0)):
            return False
        else:
            return True

        # Validation for malformed configuration
        for config in request_data['config']:
            if not (config['resource'] and
                    config['kwargs']):
                return False
            else:
                return True

    def get_service_type(self, request_data):
        """Retrieves service type from request data.

        :param request_data: API input data (format specified at top of file)

        Returns:
        (1) "firewall"/"vpn"/"loadbalancer"
        (2) "generic_config" if service_type field is absent in request_data
        (3) "invalid" if any other service type is provided in request_data

        """

        if not self.validate_request(request_data):
            return constants.invalid_service_type

        # Get service type based on the fact that for some request data
        # formats the 'type' key is absent. Check for invalid types
        service_type = request_data['info'].get('type')
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
                    method = 'vpn_service_updated'
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

            data = config_data['kwargs']
            if not data:
                return None

            sa_info.update({'kwargs': data})
            sa_info.update({'context': sa_info['kwargs']['context']})
            del sa_info['kwargs']['context']
            sa_info_list.append(sa_info)

        return sa_info_list
