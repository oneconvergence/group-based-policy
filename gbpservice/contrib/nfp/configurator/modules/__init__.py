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
from oslo_config import cfg as oslo_config

nfp_configurator_opts = [
    oslo_config.StrOpt('policy_file',
                       default='/etc/policy.json',
                       help='use credentials file path'),
    oslo_config.StrOpt('rabbit_password',
                       default='guest',
                       help='RabbitMq server login password'),
    oslo_config.StrOpt('rabbit_userid',
                       default='guest',
                       help='RabbiMq server User ID'),
    oslo_config.StrOpt('rabbit_hosts',
                       default='127.0.0.1',
                       help='RabbitMq server IP address for multi node setup'),
    oslo_config.IntOpt('rabbit_port',
                       default=5672,
                       help='RabbitMq server port number'),
    oslo_config.FloatOpt('kombu_reconnect_delay',
                         default=1.0, help='Kombu reconnection delay'),
    oslo_config.StrOpt('rabbit_host',
                       default='<openstack controller ip address>',
                       help='RabbitMq server IP addr for single node setup'),
    oslo_config.StrOpt('control_exchange',
                       default='openstack',
                       help='RabbitMq control exchange name'),
    oslo_config.BoolOpt('rabbit_use_ssl',
                        default=False, help='RabbitMq SSL mode True/False'),
    oslo_config.StrOpt('rabbit_virtual_host',
                       default='/', help='RabbitMq virtual host path')
]

oslo_config.CONF.register_opts(nfp_configurator_opts, "configurator")
