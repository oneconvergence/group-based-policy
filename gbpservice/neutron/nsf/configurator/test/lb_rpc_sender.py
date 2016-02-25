"""
Test file to send LBaaS standard rpcs to loadbalancer module
"""

import eventlet
from oslo_config import cfg
from oslo_log import log as logging
import oslo_messaging

from gbpservice.neutron.nsf.configurator.modules import \
                                                 loadbalancer_v1 as lb_v1
from neutron.common import rpc as n_rpc
from neutron import context
eventlet.monkey_patch()

LOG = logging.getLogger(__name__)

LB_RPC_TOPIC = "lbaas_agent"
LB_GENERIC_RPC_TOPIC = "lbaas_generic_config"

class LBResources(object):

    def __init__(self):
        self.driver_name = 'haproxy_on_vm'

        self.vip = {
                    "status": "ACTIVE",
                    "protocol": "TCP",
                    "description": {"floating_ip": "192.168.100.148",
                                    "provider_interface_mac": "aa:bb:cc:dd:ee:ff"},
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


class LBRpcSender(object):
    """ Client side of service manager """

    API_VERSION = '1.0'

    def __init__(self, host='devstack', topic=LB_RPC_TOPIC):
        self.host = host
        super(LBRpcSender, self).__init__()
        target = oslo_messaging.Target(
                                       topic=topic,
                                       version=self.API_VERSION)
        n_rpc.init(cfg.CONF)
        self.client = n_rpc.get_client(target)
        self.lb_resources = LBResources()
        self.context = context.get_admin_context_without_session()

    def test_create_pool(self):
        print 'called test_create_pool'
        cctxt = self.client.prepare(server=self.host)
        return cctxt.cast(self.context, 'create_pool',
                          pool=self.lb_resources.pool,
                          driver_name=self.lb_resources.driver_name)

    def test_update_pool(self):
        print 'called test_update_pool'
        cctxt = self.client.prepare(server=self.host)
        return cctxt.cast(self.context, 'update_pool',
                          old_pool=self.lb_resources.old_pool,
                          pool=self.lb_resources.pool)

    def test_delete_pool(self):
        print 'called test_delete_pool'
        cctxt = self.client.prepare(server=self.host)
        return cctxt.cast(self.context, 'delete_pool',
                          pool=self.lb_resources.pool)

    def test_create_vip(self):
        print 'called test_create_vip'
        cctxt = self.client.prepare(server=self.host)
        return cctxt.cast(self.context, 'create_vip',
                          vip=self.lb_resources.vip)

    def test_update_vip(self):
        print 'called test_update_vip'
        cctxt = self.client.prepare(server=self.host)
        return cctxt.cast(self.context, 'update_vip',
                          old_vip=self.lb_resources.vip,
                          vip=self.lb_resources.vip)

    def test_delete_vip(self):
        print 'called test_delete_vip'
        cctxt = self.client.prepare(server=self.host)
        return cctxt.cast(self.context, 'delete_vip',
                          vip=self.lb_resources.vip)

    def test_create_member(self):
        print 'called test_create_member'
        cctxt = self.client.prepare(server=self.host)
        return cctxt.cast(self.context, 'create_member',
                          member=self.lb_resources.member)

    def test_update_member(self):
        print 'called test_update_member'
        cctxt = self.client.prepare(server=self.host)
        return cctxt.cast(self.context, 'update_member',
                          old_member=self.lb_resources.member,
                          member=self.lb_resources.member)

    def test_delete_member(self):
        print 'called test_delete_member'
        cctxt = self.client.prepare(server=self.host)
        return cctxt.cast(self.context, 'delete_member',
                          member=self.lb_resources.member)

    def test_create_health_monitor(self):
        print 'called test_create_health_monitor'
        cctxt = self.client.prepare(server=self.host)
        pool = self.lb_resources.pool
        return cctxt.cast(self.context, 'create_pool_health_monitor',
                          health_monitor=self.lb_resources.health_monitor,
                          pool_id=pool['id'])

    def test_update_health_monitor(self):
        print 'called test_update_health_monitor'
        cctxt = self.client.prepare(server=self.host)
        pool = self.lb_resources.pool
        return cctxt.cast(self.context, 'update_pool_health_monitor',
                          old_health_monitor=self.lb_resources.health_monitor,
                          health_monitor=self.lb_resources.health_monitor,
                          pool_id=pool['id'])

    def test_delete_health_monitor(self):
        print 'called test_delete_health_monitor'
        cctxt = self.client.prepare(server=self.host)
        pool = self.lb_resources.pool
        return cctxt.cast(self.context, 'delete_pool_health_monitor',
                          health_monitor=self.lb_resources.health_monitor,
                          pool_id=pool['id'])

    def configure_interfaces(self):
        cctxt = self.client.prepare(server=self.host)
        rule_info = {
                    'active_provider_mac': '00:0a:95:9d:68:16',
                    'active_stitching_mac': '00:0a:95:9d:68:25',
                    'active_fip': '172.24.4.5',
                    'service_id': '1df1cd7a-d82e-4bbd-8b26-a1f106075a6b',
                    'tenant_id': '6bb921bb81254b3e90e3d8c71a6d72dc'
                   }
        return cctxt.cast(self.context, 'configure_interfaces',
                          rule_info=rule_info)

    def clear_interfaces(self):
        cctxt = self.client.prepare(server=self.host)
        return cctxt.cast(self.context, 'clear_interfaces',
                          vm_mgmt_ip='172.24.4.5',
                          service_vendor='haproxy',
                          provider_interface_position='5',
                          stitching_interface_position='5')

    def configure_source_routes(self):
        cctxt = self.client.prepare(server=self.host)
        return cctxt.cast(self.context, 'configure_source_routes',
                          vm_mgmt_ip='172.24.4.5',
                          service_vendor='vyos',
                          source_cidrs='11.0.1.0/24',
                          destination_cidr='12.0.1.0/24',
                          gateway_ip='192.168.20.254',
                          provider_interface_position='5')

    def clear_source_routes(self):
        cctxt = self.client.prepare(server=self.host)
        return cctxt.cast(self.context, 'clear_source_routes',
                          vm_mgmt_ip='172.24.4.5',
                          service_vendor='vyos', source_cidrs='11.0.1.0/24',
                          provider_interface_position='5')


# LBaaS rpc test cases
client = LBRpcSender("devstack", LB_RPC_TOPIC)
client.test_create_pool()
client.test_create_vip()
client.test_create_member()
client.test_create_health_monitor()

# client.test_update_pool()
# client.test_update_vip()
# client.test_update_member()
# client.test_update_health_monitor()

# client.test_delete_health_monitor()
# client.test_delete_member()
# client.test_delete_vip()
# client.test_delete_pool()

# Generic Config Test cases
# client = LBRpcSender("devstack", LB_GENERIC_RPC_TOPIC)
# client.configure_interfaces()
# client.clear_interfaces()
# client.configure_source_routes()
# client.clear_source_routes()
