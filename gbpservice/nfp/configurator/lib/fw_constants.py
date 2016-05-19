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

DRIVERS_DIR = 'gbpservice.nfp.configurator.drivers.firewall'
SERVICE_TYPE = 'firewall'
VYOS = 'vyos'
NEUTRON = 'neutron'

CONFIGURATION_SERVER_PORT = '8888'
REST_TIMEOUT = 120

FIREWALL_CREATE_EVENT = 'CREATE_FIREWALL'
FIREWALL_UPDATE_EVENT = 'UPDATE_FIREWALL'
FIREWALL_DELETE_EVENT = 'DELETE_FIREWALL'

STATUS_ACTIVE = "ACTIVE"
STATUS_DELETED = "DELETED"
STATUS_UPDATED = "UPDATED"
STATUS_ERROR = "ERROR"
STATUS_SUCCESS = "SUCCESS"
UNHANDLED = "UNHANDLED"

request_url = "http://%s:%s/%s"
SUCCESS_CODES = [200, 201, 202, 203, 204]
ERROR_CODES = [400, 404, 500]

INTERFACE_NOT_FOUND = "INTERFACE NOT FOUND"
