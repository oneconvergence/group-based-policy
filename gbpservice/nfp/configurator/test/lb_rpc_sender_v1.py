import eventlet
import oslo_messaging
from oslo_config import cfg
from oslo_log import log as logging
from gbpservice.nfp.configurator.agents import loadbalancer_v1
from neutron.common import rpc as n_rpc
from neutron import context
eventlet.monkey_patch()

LOG = logging.getLogger(__name__)

CONFIGURATOR_TOPIC = "configurator"
HOST = "Devstack-8"

"""
Test file to send LBaaS standard rpcs to configurator module using
generic apis
"""


class LBResources(object):

    def __init__(self):
        self.driver_name = 'loadbalancer'

        self.vip = {
                    "status": "ACTIVE",
                    "protocol": "TCP",
                    "description": {"floating_ip": "192.168.100.149",
                                    "provider_interface_mac":
                                        "aa:bb:cc:dd:ee:ff"},
                    "address": "42.0.0.14",
                    "protocol_port": 22,
                    "port_id": "cfd9fcc0-c27b-478b-985e-8dd73f2c16e8",
                    "id": "7a755739-1bbb-4211-9130-b6c82d9169a5",
                    "status_description": None,
                    "name": "lb-vip",
                    "admin_state_up": True,
                    "subnet_id": "b31cdafe-bdf3-4c19-b768-34d623d77d6c",
                    "tenant_id": "f6b09b7a590642d8ac6de73df0ab0686",
                    "connection_limit": -1,
                    "pool_id": "6350c0fd-07f8-46ff-b797-62acd23760de",
                    "session_persistence": None
                    }

        self.pool = {"status": "ACTIVE",
                     "lb_method": "ROUND_ROBIN",
                     "protocol": "TCP",
                     "description": "",
                     "health_monitors": [],
                     "members":
                     [
                        "4910851f-4af7-4592-ad04-08b508c6fa21",
                        "76d2a5fc-b39f-4419-9f33-3b21cf16fe47"
                     ],
                     "status_description": None,
                     "id": "6350c0fd-07f8-46ff-b797-62acd23760de",
                     "vip_id": "7a755739-1bbb-4211-9130-b6c82d9169a5",
                     "name": "lb-pool",
                     "admin_state_up": True,
                     "subnet_id": "b31cdafe-bdf3-4c19-b768-34d623d77d6c",
                     "tenant_id": "f6b09b7a590642d8ac6de73df0ab0686",
                     "health_monitors_status": [],
                     "provider": "haproxy"
                     }

        self.old_pool = {"status": "ACTIVE",
                         "lb_method": "ROUND_ROBIN",
                         "protocol": "TCP",
                         "description": "",
                         "health_monitors": [],
                         "members":
                         [
                            "4910851f-4af7-4592-ad04-08b508c6fa21",
                            "76d2a5fc-b39f-4419-9f33-3b21cf16fe47"
                         ],
                         "status_description": None,
                         "id": "6350c0fd-07f8-46ff-b797-62acd23760de",
                         "vip_id": "7a755739-1bbb-4211-9130-b6c82d9169a5",
                         "name": "lb-pool",
                         "admin_state_up": True,
                         "subnet_id": "b31cdafe-bdf3-4c19-b768-34d623d77d6c",
                         "tenant_id": "f6b09b7a590642d8ac6de73df0ab0686",
                         "health_monitors_status": [],
                         "provider": "haproxy"
                         }

        self.member = {
                    "admin_state_up": True,
                    "status": "ACTIVE",
                    "status_description": None,
                    "weight": 1,
                    "address": "42.0.0.11",
                    "tenant_id": "f6b09b7a590642d8ac6de73df0ab0686",
                    "protocol_port": 80,
                    "id": "4910851f-4af7-4592-ad04-08b508c6fa21",
                    "pool_id": "6350c0fd-07f8-46ff-b797-62acd23760de"
                    }

        self.health_monitor = {
                    "admin_state_up": True,
                    "tenant_id": "f6b09b7a590642d8ac6de73df0ab0686",
                    "delay": 10,
                    "max_retries": 3,
                    "timeout": 10,
                    "pools": [],
                    "type": "PING",
                    "id": "c30d8a88-c719-4b93-aa64-c58efb397d86"
                     }


class LBContext(object):
    def __init__(self):
        self.ports = [
            {"status": "ACTIVE",
             "name": "",
             "allowed_address_pairs": [],
             "admin_state_up": True,
             "network_id": "92f423a7-f44e-4726-b453-c8a1369a3ad0",
             "tenant_id": "5e67167662f94fd5987e12a68ea6c1d8",
             "extra_dhcp_opts": [],
             "binding:vnic_type": "normal",
             "device_owner": "network:dhcp",
             "mac_address": "fa:16:3e:01:19:11",
             "fixed_ips": [
                 {
                     "subnet_id": "2670bdcd-1bcf-4b97-858d-ab0d621983cc",
                     "ip_address": "11.0.0.3"
                     },
                 {
                     "subnet_id": "94aee832-935b-4e23-8f90-b6a81b0195b1",
                     "ip_address": "192.168.0.2"
                        }
                ],
             "id": "cfd9fcc0-c27b-478b-985e-8dd73f2c16e8",
             "security_groups": [],
             "device_id": ("dhcpf986c817-fd54-5bae-a8e4-e473b69100d2-"
                           "92f423a7-f44e-4726-b453-c8a1369a3ad0")
             },
            {"status": "ACTIVE",
             "name": ("aff8163b-f964-4ad7-a222-0e0a6e5593fe-"
                      "ea9ff596-51bc-4381-8aff-ee9f0ef7e319"),
             "allowed_address_pairs": [],
             "admin_state_up": True,
             "network_id": "0ced2567-47a0-4b67-be52-0e9695e8b0e6",
             "tenant_id": "5e67167662f94fd5987e12a68ea6c1d8",
             "extra_dhcp_opts": [],
             "binding:vnic_type": "normal",
             "device_owner": "network:router_interface",
             "mac_address": "fa:16:3e:1b:f2:44",
             "fixed_ips": [
                 {
                     "subnet_id": "ea9ff596-51bc-4381-8aff-ee9f0ef7e319",
                     "ip_address": "11.0.3.2"
                 }
               ],
             "id": "31df0d68-e9ea-4713-a629-29e6d87c2727",
             "security_groups": ["fb44b3f5-a319-4176-9e3b-361c5faafb66"],
             "device_id": "aff8163b-f964-4ad7-a222-0e0a6e5593fe"
             },
            {
             "status": "ACTIVE",
             "name": (
                "aff8163b-f964-4ad7-a222-0e0a6e5593fe-8eacf5cf"
                "-1e92-4e7b-90c4-cc68ef8c4e88"),
             "allowed_address_pairs": [],
             "admin_state_up": True,
             "network_id": "2e9652e8-bd95-472a-96b5-6a7939ae0f8d",
             "tenant_id": "5e67167662f94fd5987e12a68ea6c1d8",
             "extra_dhcp_opts": [],
             "binding:vnic_type": "normal",
             "device_owner": "network:router_interface",
             "mac_address": "fa:16:3e:49:44:b3",
             "fixed_ips": [
                 {
                     "subnet_id": "8eacf5cf-1e92-4e7b-90c4-cc68ef8c4e88",
                     "ip_address": "11.0.4.2"
                     }
                 ],
             "id": "214eaa12-36c9-45b1-8fee-350ce2ff2dae",
             "security_groups": ["fb44b3f5-a319-4176-9e3b-361c5faafb66"],
             "device_id": "aff8163b-f964-4ad7-a222-0e0a6e5593fe"
             }
            ]

        self.subnets = [
                {
                    "name": "apic_owned_ew-consumer",
                    "enable_dhcp": True,
                    "network_id": "0ced2567-47a0-4b67-be52-0e9695e8b0e6",
                    "tenant_id": "5e67167662f94fd5987e12a68ea6c1d8",
                    "dns_nameservers": [],
                    "gateway_ip": "11.0.3.1",
                    "ipv6_ra_mode": None,
                    "allocation_pools": [
                        {
                            "start": "11.0.3.2",
                            "end": "11.0.3.254"
                            }
                        ],
                    "host_routes": [],
                    "ip_version": 4,
                    "ipv6_address_mode": None,
                    "cidr": "11.0.3.0/24",
                    "id": "ea9ff596-51bc-4381-8aff-ee9f0ef7e319"
                    },
                {
                    "name": "apic_owned_ew-provider",
                    "enable_dhcp": True,
                    "network_id": "2e9652e8-bd95-472a-96b5-6a7939ae0f8d",
                    "tenant_id": "5e67167662f94fd5987e12a68ea6c1d8",
                    "dns_nameservers": [],
                    "gateway_ip": "11.0.4.1",
                    "ipv6_ra_mode": None,
                    "allocation_pools": [
                        {
                            "start": "11.0.4.2",
                            "end": "11.0.4.254"
                            }
                        ],
                    "host_routes": [],
                    "ip_version": 4,
                    "ipv6_address_mode": None,
                    "cidr": "11.0.4.0/24",
                    "id": "94aee832-935b-4e23-8f90-b6a81b0195b1"
                    }
                ]
        self.pools = [
                {"status": "ACTIVE",
                    "lb_method": "ROUND_ROBIN",
                    "protocol": "TCP",
                    "description": "",
                    "health_monitors": [],
                    "members":
                    [
                        "4910851f-4af7-4592-ad04-08b508c6fa21",
                        "76d2a5fc-b39f-4419-9f33-3b21cf16fe47"
                        ],
                    "status_description": None,
                    "id": "6350c0fd-07f8-46ff-b797-62acd23760de",
                    "vip_id": "7a755739-1bbb-4211-9130-b6c82d9169a5",
                    "name": "lb-pool",
                    "admin_state_up": True,
                    "subnet_id": "b31cdafe-bdf3-4c19-b768-34d623d77d6c",
                    "tenant_id": "f6b09b7a590642d8ac6de73df0ab0686",
                    "health_monitors_status": [],
                    "provider": "haproxy"},
                ]

        self.vips = [
                {
                    "status": "ACTIVE",
                    "protocol": "TCP",
                    "description": {"floating_ip": "192.168.100.149",
                                    "provider_interface_mac":
                                        "aa:bb:cc:dd:ee:ff"},
                    "address": "42.0.0.14",
                    "protocol_port": 22,
                    "port_id": "cfd9fcc0-c27b-478b-985e-8dd73f2c16e8",
                    "id": "7a755739-1bbb-4211-9130-b6c82d9169a5",
                    "status_description": None,
                    "name": "lb-vip",
                    "admin_state_up": True,
                    "subnet_id": "b31cdafe-bdf3-4c19-b768-34d623d77d6c",
                    "tenant_id": "f6b09b7a590642d8ac6de73df0ab0686",
                    "connection_limit": -1,
                    "pool_id": "6350c0fd-07f8-46ff-b797-62acd23760de",
                    "session_persistence": None
                    }
                ]

        self.health_monitors = [
                {
                    "admin_state_up": True,
                    "tenant_id": "f6b09b7a590642d8ac6de73df0ab0686",
                    "delay": 10,
                    "max_retries": 3,
                    "timeout": 10,
                    "pools": [],
                    "type": "PING",
                    "id": "c30d8a88-c719-4b93-aa64-c58efb397d86"
                     }
                ]
        self.members = [
                {
                    "admin_state_up": True,
                    "status": "ACTIVE",
                    "status_description": None,
                    "weight": 1,
                    "address": "42.0.0.11",
                    "tenant_id": "f6b09b7a590642d8ac6de73df0ab0686",
                    "protocol_port": 80,
                    "id": "4910851f-4af7-4592-ad04-08b508c6fa21",
                    "pool_id": "6350c0fd-07f8-46ff-b797-62acd23760de"},
                {
                    "admin_state_up": True,
                    "status": "ACTIVE",
                    "status_description": None,
                    "weight": 1,
                    "address": "42.0.0.13",
                    "tenant_id": "f6b09b7a590642d8ac6de73df0ab0686",
                    "protocol_port": 22,
                    "id": "76d2a5fc-b39f-4419-9f33-3b21cf16fe47",
                    "pool_id": "6350c0fd-07f8-46ff-b797-62acd23760de"
                    }
                ]

    def get_service_info(self):
        service_info = {}
        service_info['pools'] = self.pools
        service_info['members'] = self.members
        service_info['vips'] = self.vips
        service_info['health_monitors'] = self.health_monitors
        service_info['ports'] = self.ports
        service_info['subnets'] = self.subnets
        return service_info


class LBRpcSenderV1(object):
    """ Client side of service manager """

    API_VERSION = '1.0'

    def __init__(self, host=HOST, topic=CONFIGURATOR_TOPIC):
        self.host = host
        super(LBRpcSenderV1, self).__init__()
        target = oslo_messaging.Target(
                                       topic=topic,
                                       version=self.API_VERSION)
        n_rpc.init(cfg.CONF)
        self.client = n_rpc.get_client(target)
        self.lb_resources = LBResources()
        self.context = context.get_admin_context_without_session()
        self.lb_context = LBContext()

    def _prepare_request_data(self, resource, kwargs):
        request_data = {
             'info':   {'version': 'v1',
                        'service_type': 'loadbalancer'},
             'config': [{'resource': resource,
                         'kwargs': kwargs}]
            }
        return request_data

    def test_create_pool(self):
        print 'called test_create_pool'
        pool_info = {'context': {'service_info':
                                 self.lb_context.get_service_info()},
                     'pool': self.lb_resources.pool,
                     'driver_name': 'loadbalancer'
                     }

        pool_data = self._prepare_request_data('pool', pool_info)
        cctxt = self.client.prepare(server=self.host)
        return cctxt.call(self.context, 'create_network_function_config',
                          request_data=pool_data)

    def test_update_pool(self):
        print 'called test_update_pool'
        cctxt = self.client.prepare(server=self.host)
        pool_info = {'context': {'service_info':
                                 self.lb_context.get_service_info()},
                     'old_pool': self.lb_resources.pool,
                     'pool': self.lb_resources.pool,
                     }

        pool_data = self._prepare_request_data('pool', pool_info)
        return cctxt.cast(self.context, 'update_network_function_config',
                          request_data=pool_data)

    def test_delete_pool(self):
        print 'called test_delete_pool'
        pool_info = {'context': {'service_info':
                                 self.lb_context.get_service_info()},
                     'pool': self.lb_resources.pool
                     }

        pool_data = self._prepare_request_data('pool', pool_info)
        cctxt = self.client.prepare(server=self.host)
        return cctxt.call(self.context, 'delete_network_function_config',
                          request_data=pool_data)

    def test_create_vip(self):
        print 'called test_create_vip'
        vip_info = {'context': {'service_info':
                                self.lb_context.get_service_info()},
                    'vip': self.lb_resources.vip
                    }

        vip_data = self._prepare_request_data('vip', vip_info)
        cctxt = self.client.prepare(server=self.host)
        return cctxt.call(self.context, 'create_network_function_config',
                          request_data=vip_data)

    def test_update_vip(self):
        print 'called test_update_vip'
        vip_info = {'context': {'service_info':
                                self.lb_context.get_service_info()},
                    'old_vip': self.lb_resources.vip,
                    'vip': self.lb_resources.vip
                    }

        vip_data = self._prepare_request_data('vip', vip_info)
        cctxt = self.client.prepare(server=self.host)
        return cctxt.call(self.context, 'update_network_function_config',
                          request_data=vip_data)

    def test_delete_vip(self):
        print 'called test_delete_vip'
        vip_info = {'context': {'service_info':
                                self.lb_context.get_service_info()},
                    'vip': self.lb_resources.vip
                    }

        vip_data = self._prepare_request_data('vip', vip_info)
        cctxt = self.client.prepare(server=self.host)
        return cctxt.call(self.context, 'delete_network_function_config',
                          request_data=vip_data)

    def test_create_member(self):
        print 'called test_create_member'
        member_info = {'context': {'service_info':
                                   self.lb_context.get_service_info()},
                       'member': self.lb_resources.member
                       }

        member_data = self._prepare_request_data('member', member_info)
        cctxt = self.client.prepare(server=self.host)
        return cctxt.call(self.context, 'create_network_function_config',
                          request_data=member_data)

    def test_update_member(self):
        print 'called test_update_member'
        member_info = {'context': {'service_info':
                                   self.lb_context.get_service_info()},
                       'old_member': self.lb_resources.member,
                       'member': self.lb_resources.member
                       }

        member_data = self._prepare_request_data('member', member_info)
        cctxt = self.client.prepare(server=self.host)
        return cctxt.call(self.context, 'update_network_function_config',
                          request_data=member_data)

    def test_delete_member(self):
        print 'called test_delete_member'
        member_info = {'context': {'service_info':
                                   self.lb_context.get_service_info()},
                       'member': self.lb_resources.member
                       }

        member_data = self._prepare_request_data('member', member_info)
        cctxt = self.client.prepare(server=self.host)
        return cctxt.call(self.context, 'delete_network_function_config',
                          request_data=member_data)

    def test_create_pool_health_monitor(self):
        print 'called test_create_health_monitor'
        hm_info = {'context': {'service_info':
                               self.lb_context.get_service_info()},
                   'health_monitor': self.lb_resources.health_monitor,
                   'pool_id': self.lb_resources.pool['id']
                   }

        hm_data = self._prepare_request_data('pool_health_monitor',
                                             hm_info)
        cctxt = self.client.prepare(server=self.host)
        return cctxt.call(self.context, 'create_network_function_config',
                          request_data=hm_data)

    def test_update_pool_health_monitor(self):
        print 'called test_update_health_monitor'
        hm_info = {'context': {'service_info':
                               self.lb_context.get_service_info()},
                   'old_health_monitor': self.lb_resources.health_monitor,
                   'health_monitor': self.lb_resources.health_monitor,
                   'pool_id': self.lb_resources.pool['id']
                   }

        hm_data = self._prepare_request_data('pool_health_monitor',
                                             hm_info)
        cctxt = self.client.prepare(server=self.host)
        return cctxt.call(self.context, 'update_network_function_config',
                          request_data=hm_data)

    def test_delete_pool_health_monitor(self):
        print 'called test_delete_health_monitor'
        hm_info = {'context': {'service_info':
                               self.lb_context.get_service_info()},
                   'health_monitor': self.lb_resources.health_monitor,
                   'pool_id': self.lb_resources.pool['id']
                   }

        hm_data = self._prepare_request_data('pool_health_monitor',
                                             hm_info)
        cctxt = self.client.prepare(server=self.host)
        return cctxt.call(self.context, 'delete_network_function_config',
                          request_data=hm_data)

    def test_configure_interfaces(self):
        print 'called test_configure_interfaces'
        data = {'context': {},
                'service_type': 'loadbalancer',
                'request_info': {},
                }
        request_data = {
                     'info':   {'version': 'v1'},
                     'config': [{'resource': 'interfaces',
                                'kwargs': data}]
                       }
        cctxt = self.client.prepare(server=self.host)
        return cctxt.call(self.context,
                          'create_network_function_device_config',
                          request_data=request_data)

    def test_clear_interfaces(self):
        print 'called test_clear_interfaces'
        data = {'context': {},
                'service_type': 'loadbalancer',
                'request_info': {},
                }
        request_data = {
                     'info':   {'version': 'v1'},
                     'config': [{'resource': 'interfaces',
                                'kwargs': data}]
                       }
        cctxt = self.client.prepare(server=self.host)
        return cctxt.call(self.context,
                          'delete_network_function_device_config',
                          request_data=request_data)

    def test_configure_source_routes(self):
        print 'called test_configure_source_routes'
        data = {'context': {},
                'service_type': 'loadbalancer',
                'request_info': {},
                }
        request_data = {
                     'info':   {'version': 'v1'},
                     'config': [{'resource': 'routes',
                                'kwargs': data}]
                       }
        cctxt = self.client.prepare(server=self.host)
        return cctxt.call(self.context,
                          'create_network_function_device_config',
                          request_data=request_data)

    def test_clear_source_routes(self):
        print 'called test_clear_source_routes'
        data = {'context': {},
                'service_type': 'loadbalancer',
                'request_info': {},
                }
        request_data = {
                     'info':   {'version': 'v1'},
                     'config': [{'resource': 'routes',
                                'kwargs': data}]
                       }
        cctxt = self.client.prepare(server=self.host)
        return cctxt.call(self.context,
                          'delete_network_function_device_config',
                          request_data=request_data)

    def test_configure_healthmonitor(self, periodicity):
        print 'called test_configure_healthmonitor'
        data = {'context': {},
                'service_type': 'loadbalancer',
                'vmid': '6350c0fd-07f8-46ff-b797-62acd2371234',
                'mgmt_ip': '127.0.0.1',
                'periodicity': periodicity,
                'request_info': {}
                }

        request_data = {
                     'info':   {'version': 'v1'},
                     'config': [{'resource': 'healthmonitor',
                                'kwargs': data}]
                       }
        cctxt = self.client.prepare(server=self.host)
        return cctxt.call(self.context,
                          'create_network_function_device_config',
                          request_data=request_data)

    def test_clear_healthmonitor(self):
        print 'called test_clear_healthmonitor'
        data = {'context': {},
                'service_type': 'loadbalancer',
                'vmid': '6350c0fd-07f8-46ff-b797-62acd2371234',
                'request_info': {}
                }
        request_data = {
                     'info':   {'version': 'v1'},
                     'config': [{'resource': 'healthmonitor',
                                'kwargs': data}]
                       }
        cctxt = self.client.prepare(server=self.host)
        return cctxt.call(self.context,
                          'delete_network_function_device_config',
                          request_data=request_data)

# LBaaS rpc test cases
client = LBRpcSenderV1(HOST, CONFIGURATOR_TOPIC)
client.test_create_pool()
client.test_create_vip()
client.test_create_member()
client.test_create_pool_health_monitor()

# client.test_update_pool()
# client.test_update_vip()
# client.test_update_member()
# client.test_update_pool_health_monitor()
#
# client.test_delete_pool_health_monitor()
# client.test_delete_member()
# client.test_delete_vip()
# client.test_delete_pool()

# Generic Config Test cases
# client.test_configure_interfaces()
# client.test_clear_interfaces()
# client.test_configure_source_routes()
# client.test_clear_source_routes()

# client.test_configure_healthmonitor('initial')
# client.test_configure_healthmonitor('forever')
# client.test_clear_healthmonitor()
