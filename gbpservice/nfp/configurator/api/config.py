# Server Specific Configurations
server = {
    'port': '8080',
    'host': '0.0.0.0'
}

# Pecan Application Configurations
app = {
    'root': 'root_controller.RootController',
    'modules': ['v1'],
    'debug': False,
    'errors': {
        404: '/error/404',
        '__force_dict__': True
    }
}
