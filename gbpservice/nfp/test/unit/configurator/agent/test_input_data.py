class FakeObjects(object):

    sc = 'sc'
    context = {'notification_data': {},
               'resource': 'context_resource'}
    conf = 'conf'
    rpcmgr = 'rpcmgr'
    nqueue = 'nqueue'
    drivers = 'drivers'
    vip_context = {'notification_data': {}, 'resource': 'vip'}
    method = {'CREATE_VIP': 'create_network_device_config',
              'DELETE_VIP': 'delete_network_device_config',
              'UPDATE_VIP': 'update_network_device_config',
              'CREATE_POOL': 'create_network_device_config',
              'DELETE_POOL': 'delete_network_device_config',
              'UPDATE_POOL': 'update_network_device_config',
              'CREATE_MEMBER': 'create_network_device_config',
              'DELETE_MEMBER': 'delete_network_device_config',
              'UPDATE_MEMBER': 'update_network_device_config',
              'CREATE_HEALTH_MONITOR': 'create_network_device_config',
              'DELETE_HEALTH_MONITOR': 'delete_network_device_config',
              'UPDATE_HEALTH_MONITOR': 'update_network_device_config'}

    def fake_request_data_vip(self):
        request_data = {
            "info": {
                "version": 1,
                "service_type": 'loadbalancer'
            },
            "config": [{
                "resource": "vip",
                "kwargs": {
                    "context": self.context,
                    "vip": self._fake_vip_obj()
                }}]}
        return request_data

    def fake_request_data_vip_update(self):
        request_data = {
            "info": {
                "version": 1,
                "service_type": 'loadbalancer'
            },
            "config": [{
                "resource": "vip",
                "kwargs": {
                    "context": self.context,
                    "vip": self._fake_vip_obj(),
                    "old_vip": self._fake_vip_obj()
                }}]}
        return request_data

    def fake_request_data_create_pool(self):
        request_data = {
            "info": {
                "version": 1,
                "service_type": 'loadbalancer'
            },
            "config": [{
                "resource": "pool",
                "kwargs": {
                    "context": self.context,
                    "pool": self._fake_pool_obj(),
                    "driver_name": "loadbalancer"
                }}]}
        return request_data

    def fake_request_data_delete_pool(self):
        request_data = {
            "info": {
                "version": 1,
                "service_type": 'loadbalancer'
            },
            "config": [{
                "resource": "pool",
                "kwargs": {
                    "context": self.context,
                    "pool": self._fake_pool_obj()
                }}]}
        return request_data

    def fake_request_data_update_pool(self):
        request_data = {
            "info": {
                "version": 1,
                "service_type": 'loadbalancer'
            },
            "config": [{
                "resource": "pool",
                "kwargs": {
                    "context": self.context,
                    "pool": self._fake_pool_obj(),
                    "old_pool": self._fake_pool_obj()
                }}]}
        return request_data

    def fake_request_data_create_member(self):
        request_data = {
            "info": {
                "version": 1,
                "service_type": 'loadbalancer'
            },
            "config": [{
                "resource": "member",
                "kwargs": {
                    "context": self.context,
                    "member": self._fake_member_obj()[0],
                }}]}
        return request_data

    def fake_request_data_create_pool_hm(self):
        request_data = {
            "info": {
                "version": 1,
                "service_type": 'loadbalancer'
            },
            "config": [{
                "resource": "pool_health_monitor",
                "kwargs": {
                    "context": self.context,
                    "health_monitor": self._fake_hm_obj()[0],
                    "pool_id": self._fake_pool_obj()['id']
                }}]}
        return request_data

    def fake_request_data_update_pool_hm(self):
        request_data = {
            "info": {
                "version": 1,
                "service_type": 'loadbalancer'
            },
            "config": [{
                "resource": "pool_health_monitor",
                "kwargs": {
                    "context": self.context,
                    "health_monitor": self._fake_hm_obj()[0],
                    "pool_id": self._fake_pool_obj()['id'],
                    "old_health_monitor": self._fake_hm_obj()[0]
                }}]}
        return request_data

    def fake_request_data_update_member(self):
        request_data = {
            "info": {
                "version": 1,
                "service_type": 'loadbalancer'
            },
            "config": [{
                "resource": "member",
                "kwargs": {
                    "context": self.context,
                    "member": self._fake_member_obj()[0],
                    "old_member": self._fake_member_obj()[0]
                }}]}
        return request_data

    def _fake_vip_obj(self):
        vip = {"status": "ACTIVE",
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
               "session_persistence": None}
        return vip

    def _fake_pool_obj(self):
        pool = {"status": "ACTIVE",
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
                    "provider": "haproxy"}
        return pool

    def _fake_member_obj(self):
        member = [{
            "admin_state_up": True,
            "status": "ACTIVE",
            "status_description": None,
            "weight": 1,
            "address": "42.0.0.11",
            "tenant_id": "f6b09b7a590642d8ac6de73df0ab0686",
            "protocol_port": 80,
            "id": "4910851f-4af7-4592-ad04-08b508c6fa21",
            "pool_id": "6350c0fd-07f8-46ff-b797-62acd23760de"}]
        return member

    def _fake_hm_obj(self):
        hm = [{
            "admin_state_up": True,
            "tenant_id": "f6b09b7a590642d8ac6de73df0ab0686",
            "delay": 10,
            "max_retries": 3,
            "timeout": 10,
            "pools": [],
            "type": "PING",
                    "id": "c30d8a88-c719-4b93-aa64-c58efb397d86"
        }]
        return hm


class FakeEvent(object):

    def __init__(self):
        fo = FakeObjects()
        kwargs = 'kwargs'
        self.data = {
            'context': {'notification_data': {},
                        'resource': 'vip'},
            'vip': fo._fake_vip_obj(),
            'old_vip': fo._fake_vip_obj(),
            'pool': fo._fake_pool_obj(),
            'old_pool': fo._fake_pool_obj(),
            'member': fo._fake_member_obj()[0],
            'old_member': fo._fake_member_obj()[0],
            'health_monitor': fo._fake_hm_obj()[0],
            'old_health_monitor': fo._fake_hm_obj()[0],
            'pool_id': '6350c0fd-07f8-46ff-b797-62acd23760de',
            'driver_name': 'loadbalancer',
            'host': 'host',
            'kwargs': kwargs,
        }
