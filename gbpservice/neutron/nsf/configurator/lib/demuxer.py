
class ConfiguratorDemuxer(object):
    def __init__(self):
        pass
    
    def get_service_agent_info(self, method, data):
        sa_info = {}
        
        if (data['info'].has_key('service_type')):
            sa_info['service_type'] = data['info']['service_type']
        else:
            sa_info['service_type'] = None
        
        if data['info']['service_type'] == 'firewall':
            sa_info['method'] = method + data['config']['resource']
        elif data['info']['service_type'] == 'vpn':
            sa_info['method'] = 'vpn_service_updated'
        elif data['info']['service_type'] == 'loadbalancer':
            sa_info['method'] = method + data['config']['resource']
        else:
            if method == 'create':
                sa_info['method'] = 'configure' + data['config']['resource']
            elif method == 'delete':
                sa_info['method'] = 'clear' + data['config']['resource']
            elif method == 'update':
                sa_info['method'] = 'update' + data['config']['resource']

        
