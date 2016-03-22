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

""" Implements fake objects for assertion.

"""


class FakeObjects(object):
    sc = 'sc'
    empty_dict = {}
    context = {'notification_data': {},
               'resource': 'interfaces'}
    firewall = 'firewall'
    host = 'host'
    conf = 'conf'
    kwargs = {'vmid': 'vmid'}
    rpcmgr = 'rpcmgr'
    drivers = 'drivers'
    vm_mgmt_ip = '172.24.4.5'
    service_vendor = 'service_vendor'
    source_cidrs = ['1.2.3.4/24']
    destination_cidr = 'destination_cidr'
    gateway_ip = '1.2.3.4'
    provider_interface_position = 'provider_interface_position'
    url = 'http://172.24.4.5:8888'
    url_for_add_inte = "%s/add_rule" % url
    url_for_del_inte = "%s/delete_rule" % url
    url_for_add_src_route = "%s/add-source-route" % url
    url_for_del_src_route = "%s/delete-source-route" % url
    url_for_config_fw = "%s/configure-firewall-rule" % url
    url_for_update_fw = "%s/update-firewall-rule" % url
    url_for_delete_fw = "%s/delete-firewall-rule" % url
    data = ('{"stitching_mac": "00:0a:95:9d:68:16",'
            '"provider_mac": "00:0a:95:9d:68:16"}')
    data_for_interface = ('{"stitching_mac": "00:0a:95:9d:68:16",'
                          ' "provider_mac": "00:0a:95:9d:68:16"}')
    data_for_add_src_route = ('[{"source_cidr": "1.2.3.4/24", '
                              '"gateway_ip": "1.2.3.4"}]')
    data_for_del_src_route = '[{"source_cidr": "1.2.3.4/24"}]'
    timeout = 30

    def fake_request_data_generic_bulk(self):
        """ A sample bulk request data for generic APIs

        Returns: data which is the input for generic configuration
        RPC receivers of configurator.

        """

        request_data = {
            "info": {
                "version": 1
            },
            "config": [{
                "resource": "interfaces",
                "kwargs": {
                    "stitching_mac": None,
                    "context": {
                        "domain": None},
                    "vm_mgmt_ip": "120.0.0.15",
                    "service_vendor": "vyos",
                    "request_info": {
                        "network_function_id": (
                                    "940dcdf3-77c8-4119-9f95-ec1e16a50fa8"),
                        "network_function_device_id": (
                                    "940dcdf3-77c8-4119-9f95-ec1e16a50fa8"),
                        "network_function_instance_id": (
                                    "940dcdf3-77c8-4119-9f95-ec1e16a50fa8")
                    },
                    "provider_mac": "fa:16:3e:0f:0f:06",
                    "provider_interface_position": 2,
                    "stitching_cidr": None,
                    "provider_ip": "11.0.0.1",
                    "stitching_interface_position": 3,
                    "rule_info": {
                        'service_id': 'a124581d-e722-42e1-a720-2e437b75f3ee',
                        'active_stitching_mac': 'fa:16:3e:33:05:2b',
                        'active_fip': '11.0.0.6',
                        'active_provider_mac': 'fa: 16: 3e: 17: fe: de ',
                        'tenant_id': 'fa1caba059946dfa7839101a93bac7c '},
                    "provider_cidr": "11.0.0.0/24",
                    "stitching_ip": None,
                    "service_type": 'firewall'
                }
            }, {
                "resource": "routes",
                "kwargs": {
                    "vm_mgmt_ip": "120.0.0.15",
                    "service_vendor": "vyos",
                    "request_info": {
                        "network_function_id": (
                                    "940dcdf3-77c8-4119-9f95-ec1e16a50fa8"),
                        "network_function_device_id": (
                                    "940dcdf3-77c8-4119-9f95-ec1e16a50fa8"),
                        "network_function_instance_id": (
                                    "940dcdf3-77c8-4119-9f95-ec1e16a50fa8")
                    },
                    "provider_interface_position": 2,
                    "gateway_ip": None,
                    "destination_cidr": None,
                    "service_type": 'firewall',
                    "context": {
                        "domain": None},
                    "source_cidrs": ["11.0.0.1/24"]
                }
            }]
        }
        return request_data

    def fake_request_data_generic_single(self, routes=False):
        """ A sample single request data for generic APIs

        Returns: data which is the input for generic configuration
        RPC receivers of configurator.

        """

        request_data = self.fake_request_data_generic_bulk()
        request_data['config'].pop(0) if routes else (
                                            request_data['config'].pop(1))

        return request_data

    def fake_request_data_fw(self):
        """ A sample request data for FwaaS APIs

        Returns: data which is the input for firewall configuration
        RPC receivers of configurator.

        """

        request_data = {
            "info": {
                "version": 1,
                "service_type": 'firewall'
            },
            "config": [{
                "resource": "firewall",
                "kwargs": {
                    "context": self.context,
                    "firewall": self._fake_firewall_obj(),
                    "host": self.host}}]
                        }
        return request_data

    def fake_sa_req_list(self):
        """ A sample data for agent handlers

        Returns: data which is the input for event handler
        functions of agents.

        """

        sa_req_list = [{
            'service_type': 'generic',
            'resource': 'interfaces',
            'method': 'configure_interfaces',
            'context': {
                'domain': None
            },
            'kwargs': {
                'kwargs': {
                    'stitching_mac': None,
                    'service_vendor': 'vyos',
                    'provider_interface_position': 2,
                    'rule_info': {
                        'service_id': 'a124581d-e722-42e1-a720-2e437b75f3ee',
                        'active_stitching_mac': 'fa:16:3e:33:05:2b',
                        'tenant_id': 'fa1caba059946dfa7839101a93bac7c ',
                        'active_fip': '11.0.0.6',
                        'active_provider_mac': 'fa: 16: 3e: 17: fe: de '
                    },
                    'provider_ip': '11.0.0.1',
                    'stitching_interface_position': 3,
                    'stitching_ip': None,
                    'vm_mgmt_ip': '120.0.0.15',
                    'stitching_cidr': None,
                    'request_info': {
                        'network_function_id': (
                                    '940dcdf3-77c8-4119-9f95-ec1e16a50fa8'),
                        'network_function_device_id': (
                                    '940dcdf3-77c8-4119-9f95-ec1e16a50fa8'),
                        'network_function_instance_id': (
                                    '940dcdf3-77c8-4119-9f95-ec1e16a50fa8')
                    },
                    'provider_mac': 'fa:16:3e:0f:0f:06',
                    'service_type': 'firewall',
                    'provider_cidr': '11.0.0.0/24'
                }
            }
        }, {
            'service_type': 'generic',
            'resource': 'routes',
            'method': 'configure_routes',
            'context': {
                'domain': None
            },
            'kwargs': {
                'kwargs': {
                    'provider_interface_position': 2,
                    'service_type': 'firewall',
                    'gateway_ip': None,
                    'vm_mgmt_ip': '120.0.0.15',
                    'source_cidrs': ['11.0.0.1/24'],
                    'service_vendor': 'vyos',
                    'request_info': {
                        'network_function_id': (
                                '940dcdf3-77c8-4119-9f95-ec1e16a50fa8'),
                        'network_function_device_id': (
                                '940dcdf3-77c8-4119-9f95-ec1e16a50fa8'),
                        'network_function_instance_id': (
                                '940dcdf3-77c8-4119-9f95-ec1e16a50fa8')
                    },
                    'destination_cidr': None
                }
            }
        }]
        return sa_req_list

    def _fake_kwargs(self):
        """ A sample keyword arguments for configurator

        Returns: kwargs

        """

        kwargs = {'service_type': 'firewall',
                  'vm_mgmt_ip': '172.24.4.5',
                  'mgmt_ip': '172.24.4.5',
                  'source_cidrs': ['1.2.3.4/24'],
                  'destination_cidr': ['1.2.3.4/24'],
                  'gateway_ip': '1.2.3.4',
                  'provider_interface_position': '1',
                  'request_info': 'some_id',
                  'periodicity': 'initial',
                  'rule_info': {
                        'active_provider_mac': '00:0a:95:9d:68:16',
                        'provider_mac': '00:0a:95:9d:68:16',
                        'active_stitching_mac': '00:0a:95:9d:68:16',
                        'stitching_mac': '00:0a:95:9d:68:16',
                        'active_fip': '172.24.4.5',
                        'fip': '172.24.4.5',
                        'service_id': '1df1cd7a-d82e-4bbd-8b26-a1f106075a6b',
                        'tenant_id': '6bb921bb81254b3e90e3d8c71a6d72dc'},
                  'context': {'notification_data': 'hello'}
                  }
        return kwargs

    def _fake_firewall_obj(self):
        """ A sample firewall resource object

        Returns: firewall object

        """

        firewall = {
                     "admin_state_up": True,
                     "description": "",
                     "firewall_policy_id": (
                                "c69933c1-b472-44f9-8226-30dc4ffd454c"),
                     "id": "3b0ef8f4-82c7-44d4-a4fb-6177f9a21977",
                     "name": "",
                     "status": "PENDING_CREATE",
                     "router_ids": [
                         "650bfd2f-7766-4a0d-839f-218f33e16998"
                     ],
                     "tenant_id": "45977fa2dbd7482098dd68d0d8970117",
                     "firewall_rule_list": True,
                     "description": '{\
                                    "vm_management_ip": "172.24.4.5",\
                                    "service_vendor": "vyos"}',
                     "firewall_rule_list": True
                    }
        return firewall

""" Implements a fake event class for process framework to use

"""


class FakeEvent(object):
    def __init__(self):
        fo = FakeObjects()
        kwargs = fo._fake_kwargs()
        self.data = {
                    'context': {'notification_data': {},
                                'resource': 'firewall'},
                    'firewall': fo._fake_firewall_obj(),
                    'host': fo.host,
                    'kwargs': kwargs,
                    'vm_mgmt_ip': fo.vm_mgmt_ip,
                    'service_vendor': fo.service_vendor,
                    'source_cidrs': fo.source_cidrs,
                    'destination_cidr': fo.destination_cidr,
                    'gateway_ip': fo.gateway_ip,
                    'provider_interface_position': (
                                        fo.provider_interface_position)}
        self.id = 'dummy'
