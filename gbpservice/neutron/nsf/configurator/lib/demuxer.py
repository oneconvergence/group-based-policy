
class ConfiguratorDemuxer(object):
    def __init__(self):
        pass

    def get_service_agent_info(self, operation, request_data):
        sa_info_list = []

        service_type = request_data['info'].get('type')
        for config_data in request_data['config']:
            sa_info = {}
            if service_type:
                sa_info.update({'service_type': service_type})

                if service_type == 'firewall':
                    method = operation + '_' + config_data['resource']
                elif service_type == 'vpn':
                    method = 'vpn_service_updated'
                elif service_type == 'loadbalancer':
                    method = operation + '_' + config_data['resource']
            else:
                sa_info.update({'service_type': 'generic_config'})
                if operation == 'create':
                    method = 'configure_' + config_data['resource']
                elif operation == 'clear':
                    method = 'clear_' + config_data['resource']
            sa_info.update({'method': method})

            ''' [DEE]: We need a mapping between the data and the agent
                       information present in a list. We can achieve this
                       either by mapping data in the sa_info or by popping
                       the list as list is ordered.
            '''
            data = config_data['kwargs']
            sa_info.update({'kwargs': data})

            sa_info_list.append(sa_info)

        return sa_info_list
