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
    context = 'APIcontext'
    timeout = 120
    host = 'host'
    content_headers = {'Content-Type': 'application/json'}
    asav_url = 'https://172.24.4.5'
    asav_bulk_cli_url = '%s/api/cli' % asav_url
    asav_api_cli_url = '%s/api' % asav_url

    def fake_asav_resources(self, resource):
        resource_data_map = {
            'configure_interface': [
                'interface gigabitEthernet 0/2',
                'nameif interface-192.168.0.0_28',
                {}, 'ip address 192.168.0.3 255.255.255.240',
                'no shutdown', 'same-security-traffic permit inter-interface',
                'write memory'],
            'clear_interface': [
                "clear configure interface GigabitEthernet0/1",
                "clear configure interface GigabitEthernet0/2",
                "write memory"],
            'configure_routes': [
                "route interface-192.168.0.0_28 0 0 1.2.3.4 3",
                "dns domain-lookup interface-192.168.0.0_28",
                "write memory"],
            'clear_routes': [
                "interface GigabitEthernet0/1",
                "no policy-route route-map pbrmap1.2.3.4_24",
                "no route-map pbrmap1.2.3.4_24",
                "clear configure access-list pbracl1.2.3.4_24",
                "clear configure interface GigabitEthernet0/1",
                "write memory"],
            'create_fw': [
                {"resourceUri": "/api/access/out/interface-11.0.1.0_24/rules",
                 "data": dict(destinationAddress={
                            "kind": "AnyIPAddress", "value": "0.0.0.0"},
                          destinationService={"kind": "NetworkProtocol",
                                              "value": "ip"},
                          sourceAddress={"kind": "AnyIPAddress",
                                         "value": "0.0.0.0"},
                          permit=False), "method": "Post"}],
            'update_fw': [
                {"resourceUri": "/api/access/out/interface-11.0.1.0_24/rules",
                 "data": dict(destinationAddress={
                            "kind": "AnyIPAddress", "value": "0.0.0.0"},
                          destinationService={"kind": "NetworkProtocol",
                                              "value": "ip"},
                          sourceAddress={"kind": "AnyIPAddress",
                                         "value": "0.0.0.0"},
                          permit=False), "method": "Post"}],
            'delete_fw': [
                "clear configure access-list interface-11.0.1.0_24_access_out",
                "wr mem"]}

        return resource_data_map[resource]

    def _fake_resource_data(self):
        """ A sample keyword arguments for configurator

        Returns: kwargs

        """

        resource_data = {
                    'fake_resource_data': 'data',
                    'periodicity': 'initial',
                    'provider_ip': '11.0.1.1',
                    'provider_cidr': '11.0.1.0/24',
                    'provider_mac': '00:0a:95:9d:68:16',
                    'stitching_ip': '192.168.0.3',
                    'stitching_cidr': '192.168.0.0/28',
                    'destination_cidr': '192.168.0.0/28',
                    'stitching_mac': '00:0a:95:9d:68:16',
                    'provider_interface_index': 'provider_interface_index',
                    'stitching_interface_index': 'stitching_interface_index',
                    'mgmt_ip': '172.24.4.5',
                    'source_cidrs': ['1.2.3.4/24'],
                    'gateway_ip': '1.2.3.4'
                        }
        return resource_data

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
                     "description": '{\
                                    "vm_management_ip": "172.24.4.5",\
                                    "provider_cidr": "11.0.1.0/24",\
                                    "service_vendor": "vyos"}',
                     "firewall_rule_list": True
                    }
        return firewall
