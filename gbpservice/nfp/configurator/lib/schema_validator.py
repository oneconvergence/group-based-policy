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

from oslo_log import log
import gbpservice.nfp.configurator.lib.schema as schema

LOG = log.getLogger(__name__)

""" Validates request data against standard resource schemas given in schema.py

    Validation is focused on keys. It cross checks if resources in
    request_data has all the keys given in the schema of that resource.
"""


class SchemaValidator():

    def decode(self, request_data):
        """ Validate request data against resource schema.

        :param: request_data

        Returns: True - If schema validation is successful.
                 False - If schema validation fails.

        """
        try:
            if not self.validate_schema(request_data, schema.request_data):
                return False

            if ('service_type' in request_data['info'] and
                    'version' in request_data['info']):
                service_type = request_data['info']['service_type']
            elif ('service_type' not in request_data['info'] and
                    'version' in request_data['info']):
                service_type = 'generic'
            elif not self.validate_schema(request_data['info'],
                                          schema.request_data_info):
                return False

            for config in request_data['config']:
                if not self.validate_schema(config,
                                            schema.request_data_config):
                    return False

                resource_type = config['resource']
                resource = config['kwargs']

                """Do not validate kwargs for
                   1) *aaS apis
                   2) generic config of loadbalancer for resource
                      interfaces and routes
                """
                if (service_type in schema.skip_kwargs_validation_for or
                        (resource['service_type'] == 'loadbalancer' and
                            resource_type != 'healthmonitor')):
                        continue

                resource_schema = getattr(schema, resource_type)
                if not self.validate_schema(resource, resource_schema):
                    return False

                if 'rule_info' in resource:
                    interface_rule_info = resource['rule_info']
                    interface_rule_info_schema = schema.interfaces_rule_info

                    if not self.validate_schema(interface_rule_info,
                                                interface_rule_info_schema):
                        return False
        except Exception as e:
            LOG.error(e)
            return False

        LOG.debug("Schema validation successful for"
                  " request_data=%s" % (request_data))
        return True

    def validate_schema(self, resource, resource_schema):
        """ Validate resource against resource_schema

        :param resource
        :param resource_schema

        Returns: True/False
        """
        diff = set(resource_schema.keys()) - set(resource.keys())

        # If resource has unexpected extra keywords
        if len(resource.keys()) > len(resource_schema.keys()):
            diff = set(resource.keys()) - set(resource_schema.keys())
            LOG.error("FAILED: resource=%s has unexpected extra keys=%s,"
                      " expected keys are= %s " % (resource, list(diff),
                                                   resource_schema.keys()))
            return False
        elif len(diff) == 0:
            return True
        else:
            LOG.error("FAILED: resource=%s does not contain keys=%s,"
                      " expected keys are= %s " % (resource, list(diff),
                                                   resource_schema.keys()))
            return False
