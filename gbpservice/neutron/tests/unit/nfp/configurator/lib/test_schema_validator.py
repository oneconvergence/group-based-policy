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

import gbpservice.nfp.configurator.lib.schema as schema
import gbpservice.nfp.configurator.lib.schema_validator as sv
import unittest


"""SchemaResources is a helper class which contains all the dummy resources
   needed for TestSchemaValidator class
"""


class SchemaResources(object):
    resource_healthmonitor = 'healthmonitor'
    resource_interfaces = 'interfaces'
    resource_routes = 'routes'

    request_data = {'info': {'version': 'v1'},
                    'config': [{'resource': resource_healthmonitor,
                                'kwargs': {}
                                }]
                    }

    request_data_info = {'version': 'v1'}

    request_data_config = {'resource': resource_healthmonitor,
                           'kwargs': {}
                           }

    interfaces = {'context': {},
                  'request_info': {},
                  'vm_mgmt_ip': '127.0.0.1',
                  'service_vendor': 'vyos',
                  'provider_ip': '11.0.0.4',
                  'provider_cidr': '11.0.0.0/24',
                  'provider_interface_position': '2',
                  'stitching_ip': '33.0.0.4',
                  'stitching_cidr': '33.0.0.0/24',
                  'stitching_interface_position': '3',
                  'provider_mac': 'e1:6d:af:23:b8:91',
                  'stitching_mac': 'e1:6d:af:23:b8:11',
                  'rule_info': {'active_provider_mac': 'e1:6d:af:23:b8:91',
                                'active_stitching_mac': 'e1:6d:af:23:b8:11',
                                'active_fip': '192.168.100.141',
                                'service_id':
                                    '6350c0fd-07f8-46ff-b797-62acd2371234',
                                'tenant_id':
                                    '9950c088-07f8-46ff-b797-62acd2371234'
                                },
                  'service_type': 'firewall'
                  }

    interfaces_rule_info = {'active_provider_mac': 'e1:6d:af:23:b8:91',
                            'active_stitching_mac': 'e1:6d:af:23:b8:11',
                            'active_fip': '192.168.100.141',
                            'service_id':
                                '6350c0fd-07f8-46ff-b797-62acd2371234',
                            'tenant_id': '9950c088-07f8-46ff-b797-62acd2371234'
                            }

    routes = {'context': {},
              'request_info': {},
              'vm_mgmt_ip': '127.0.0.1',
              'service_vendor': 'vyos',
              'source_cidrs': '11.0.0.0/24',
              'destination_cidr': '22.0.0.0/24',
              'gateway_ip': '11.0.0.1',
              'provider_interface_position': '2',
              'service_type': 'firewall',
              }

    healthmonitor = {'context': {},
                     'request_info': {},
                     'service_type': 'loadbalancer',
                     'vmid': '6350c0fd-07f8-46ff-b797-62acd2371234',
                     'mgmt_ip': '127.0.0.1',
                     'periodicity': 'initial'
                     }

"""TestSchemaValidator is a test class to test schema_validator.py using
   unittest framework
"""


class TestSchemaValidator(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(TestSchemaValidator, self).__init__(*args, **kwargs)
        self.sv = sv.SchemaValidator()
        self.sr = SchemaResources()

    def make_request_data(self, resource, kwargs):
        """Prepares request data

        :param resource - resource_name
        :param kwargs - kwargs

        Returns: request_data

        """

        request_data = {'info': {'version': 'v1'},
                        'config': [{'resource': resource,
                                    'kwargs': kwargs
                                    }]
                        }
        return request_data

    def test_validate_schema_for_request_data(self):
        """Test case to test validate_schema() of schema_validator.py for
           'request_data' schema
        """
        result = self.sv.validate_schema(self.sr.request_data,
                                         schema.request_data)
        self.assertTrue(result)

    def test_validate_schema_for_request_data_info(self):
        """Test case to test validate_schema() of schema_validator.py for
           'request_data_info' schema
        """
        result = self.sv.validate_schema(self.sr.request_data_info,
                                         schema.request_data_info)
        self.assertTrue(result)

    def test_validate_schema_for_request_data_config(self):
        """Test case to test validate_schema() of schema_validator.py for
           'request_data_config' schema
        """
        result = self.sv.validate_schema(self.sr.request_data_config,
                                         schema.request_data_config)
        self.assertTrue(result)

    def test_validate_schema_for_interfaces(self):
        """Test case to test validate_schema() of schema_validator.py for
           'interfaces' schema
        """
        result = self.sv.validate_schema(self.sr.interfaces,
                                         schema.interfaces)
        self.assertTrue(result)

    def test_validate_schema_for_interfaces_rule_info(self):
        """Test case to test validate_schema() of schema_validator.py for
           'interfaces_rule_info' schema
        """
        result = self.sv.validate_schema(self.sr.interfaces_rule_info,
                                         schema.interfaces_rule_info)
        self.assertTrue(result)

    def test_validate_schema_for_routes(self):
        """Test case to test validate_schema() of schema_validator.py for
           'routes' schema
        """
        result = self.sv.validate_schema(self.sr.routes,
                                         schema.routes)
        self.assertTrue(result)

    def test_validate_schema_for_healthmonitor(self):
        """Test case to test validate_schema() of schema_validator.py for
           'healthmonitor' schema
        """
        result = self.sv.validate_schema(self.sr.healthmonitor,
                                         schema.healthmonitor)
        self.assertTrue(result)

    def test_decode_for_interfaces(self):
        """Test case to test decode() of schema_validator.py for request_data
           with resource 'interfaces'
        """
        request_data = self.make_request_data(self.sr.resource_interfaces,
                                              self.sr.interfaces)
        result = self.sv.decode(request_data)
        self.assertTrue(result)

    def test_decode_for_routes(self):
        """Test case to test decode() of schema_validator.py for request_data
           with resource 'routes'
        """
        request_data = self.make_request_data(self.sr.resource_routes,
                                              self.sr.routes)
        result = self.sv.decode(request_data)
        self.assertTrue(result)

    def test_decode_for_healthmonitor(self):
        """Test case to test decode() of schema_validator.py for request_data
           with resource 'healthmonitor'
        """
        request_data = self.make_request_data(self.sr.resource_healthmonitor,
                                              self.sr.healthmonitor)
        result = self.sv.decode(request_data)
        self.assertTrue(result)

    def test_decode_for_neutron_apis(self):
        """Test case to test decode() of schema_validator.py for *aaS apis
        """
        request_data = self.make_request_data('firewall',
                                              {})
        request_data['info']['service_type'] = 'firewall'
        result = self.sv.decode(request_data)
        self.assertTrue(result)

if __name__ == '__main__':
    unittest.main()
