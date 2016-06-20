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

PROVIDER = 'provider'
STITCHING = 'stitching'


class DataParser(object):
    def __init__(self):
        self.resource_data = dict()
        self.interface_type_map = {
                    'mgmt': 'mgmt_',
                    'monitor': 'monitoring_',
                    'provider': 'provider_',
                    'stitching': 'stitching_',
                    'failover': 'failover_'}

    ''' Expects resource and resource data to be passed '''
    def parse_data(self, resource, resource_data):
        nfd = resource_data['nfds'][0]
        self.resource_data.update({
                        'tenant_id': resource_data['tenant_id'],
                        'role': nfd['role'],
                        'mgmt_ip': nfd['svc_mgmt_fixed_ip']})
        method = 'parse' + resource + 'data'
        getattr(self, method)(nfd)
        return self.resource_data

    def parse_interfaces_data(self, nfd):
        networks = nfd['networks']
        for network in networks:
            prefix = self.interface_type_map(network['type'])
            if network['type'] in [PROVIDER, STITCHING]:
                port = network['ports'][0]
                self.resource_data.update({
                                (prefix + 'cidr'): network['cidr'],
                                (prefix + 'ip'): port['fixed_ip'],
                                (prefix + 'mac'): port['mac'],
                                (prefix + 'interface_position'): network[
                                                        'interface_index']})

    def parse_routes_data(self, nfd):
        networks = nfd['networks']
        for network in networks:
            prefix = self.interface_type_map(network['type'])
            cidrs = list()
            if network['type'] is PROVIDER:
                port = network['ports'][0]
                self.resource_data.update({
                                (prefix + 'mac'): port['mac'],
                                (prefix + 'interface_position'): network[
                                                        'interface_index']})
                self.resource_data.update({'source_cidrs': cidrs.append(
                                                        network['cidr'])})

            if network['type'] is STITCHING:
                self.resource_data.update({'gateway_ip': network['gw_ip']})
                self.resource_data.update({'destination_cidr': network[
                                                                    'cidr']})
                self.resource_data.update({'source_cidrs': cidrs.append(
                                                        network['cidr'])})

    def parse_healthmonitor_data(self, nfd):
        self.resource_data.update({'periodicity': nfd['periodicity'],
                                   'vmid': nfd['vmid']})
