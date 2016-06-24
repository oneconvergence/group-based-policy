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
        self.interface_type_map = {
                    'mgmt': 'mgmt_',
                    'monitor': 'monitoring_',
                    'provider': 'provider_',
                    'stitching': 'stitching_',
                    'failover': 'failover_'}

    ''' Expects resource and resource data to be passed '''
    def parse_data(self, resource, data):
        self.resource_data = dict()
        if data['nfds']:
            tenant_id = data['tenant_id']
            data = data['nfds'][0]
        else:
            tenant_id = data['resource_data']['tenant_id']
            data = data['resource_data']['nfs'][0]

        self.resource_data.update({
                        'tenant_id': tenant_id,
                        'role': data['role'],
                        'mgmt_ip': data['svc_mgmt_fixed_ip']})

        method = '_parse_' + resource + '_data'
        getattr(self, method)(data)
        return self.resource_data

    def _parse_interfaces_data(self, nfd):
        networks = nfd['networks']
        for network in networks:
            prefix = self.interface_type_map[network['type']]
            if network['type'] in [PROVIDER, STITCHING]:
                port = network['ports'][0]
                self.resource_data.update({
                                (prefix + 'cidr'): network['cidr'],
                                (prefix + 'ip'): port['fixed_ip'],
                                (prefix + 'mac'): port['mac'],
                                (prefix + 'interface_position'): port[
                                                        'interface_index']})

    def _parse_routes_data(self, nfd):
        networks = nfd['networks']
        cidrs = list()
        for network in networks:
            prefix = self.interface_type_map[network['type']]
            if network['type'] in PROVIDER:
                port = network['ports'][0]
                self.resource_data.update({
                                (prefix + 'mac'): port['mac'],
                                (prefix + 'interface_position'): port[
                                                        'interface_index']})
                cidrs.append(network['cidr'])

            if network['type'] in STITCHING:
                self.resource_data.update({'gateway_ip': network['gw_ip']})
                self.resource_data.update({'destination_cidr': network[
                                                                    'cidr']})
                cidrs.append(network['cidr'])
        self.resource_data.update({'source_cidrs': cidrs})

    def _parse_healthmonitor_data(self, nfd):
        self.resource_data.update({'periodicity': nfd['periodicity'],
                                   'vmid': nfd['vmid']})

    def _parse_firewall_data(self, nfs):
        networks = nfs['networks']
        for network in networks:
            prefix = self.interface_type_map[network['type']]
            if network['type'] in PROVIDER:
                port = network['ports'][0]
                self.resource_data.update({
                                (prefix + 'cidr'): network['cidr'],
                                (prefix + 'mac'): port['mac']})
