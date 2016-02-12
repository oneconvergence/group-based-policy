# Server Specific Configurations
server = {
    'port': '8080',
    'host': '0.0.0.0'
}

# Pecan Application Configurations
app = {
    'root': 'root_controllers.RootController',
    'modules': ['pecanserver'],
    'static_root': '%(confdir)s/public',
    'template_path': '%(confdir)s/pecanserver/templates',
    'debug': True,
    'errors': {
        404: '/error/404',
        '__force_dict__': True
    }
}
