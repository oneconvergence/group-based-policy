from oslo_config import cfg as oslo_config

es_openstack_opts = [
    oslo_config.StrOpt('auth_host',
                       default='localhost',
                       help='Openstack controller IP Address'),
    oslo_config.StrOpt('admin_user',
                       help='Admin user name to create service VMs'),
    oslo_config.StrOpt('admin_password',
                       help='Admin password to create service VMs'),
    oslo_config.StrOpt('admin_tenant_name',
                       help='Admin tenant name to create service VMs'),
    oslo_config.StrOpt('admin_tenant_id',
                       help='Admin tenant ID to create service VMs'),
    oslo_config.StrOpt('auth_protocol',
                       default='http', help='Auth protocol used.'),
    oslo_config.IntOpt('auth_port',
                       default='5000', help='Auth protocol used.'),
    oslo_config.IntOpt('bind_port',
                       default='9696', help='Auth protocol used.'),
    oslo_config.StrOpt('auth_version',
                       default='v2.0', help='Auth protocol used.'),
    oslo_config.StrOpt('auth_uri',
                       default='', help='Auth URI.'),
]

oslo_config.CONF.register_opts(es_openstack_opts, "keystone_authtoken")
