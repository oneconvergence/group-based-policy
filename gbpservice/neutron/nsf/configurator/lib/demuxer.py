
from gbpservice.neutron.nsf.configurator.lib import constants as const

class ConfiguratorDemuxer(object):
    def __init__(self):
        pass

    def validate_request_data(self, request_data):
        #TODO: Prepare pre-defined dict and compare
        pass

    def get_service_type(self, request_data):
        service_type = request_data['info'].get('type')
        if (service_type not in const.supported_service_types):
            return const.invalid_service_type
        elif not service_type:
            service_type = 'generic_config'
            return service_type
        else:
            return service_type
        
    def get_service_agent_info(self, operation, service_type, request_data):
        sa_info_list = []
     
        for config_data in request_data['config']:
            sa_info = {}
            if service_type in const.supported_service_types:
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

            sa_info_list.append(sa_info)

        return sa_info_list
