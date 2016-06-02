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

DRIVERS_DIR = 'gbpservice.nfp.configurator.drivers.loadbalancer.v2'
SERVICE_TYPE = 'loadbalancerv2'
NEUTRON = 'neutron'

LBAAS_AGENT_RPC_TOPIC = 'lbaasv2_agent'
LBAAS_GENERIC_CONFIG_RPC_TOPIC = 'lbaas_generic_config'
LBAAS_PLUGIN_RPC_TOPIC = 'n-lbaas-plugin'
AGENT_TYPE_LOADBALANCER = 'OC Loadbalancer V2 agent'

# Resources names
LOADBALANCER = 'loadbalancer'
LISTENER = 'listener'
POOL = 'pool'
MEMBER = 'member'
HEALTHMONITOR = 'healthmonitor'
SNI = 'sni'
L7POLICY = 'l7policy'
L7RULE = 'l7rule'
# Resources names for update apis
OLD_LOADBALANCER = 'old_loadbalancer'
OLD_LISTENER = 'old_listener'
OLD_POOL = 'old_pool'
OLD_MEMBER = 'old_member'
OLD_HEALTHMONITOR = 'old_healthmonitor'

# Operations
CREATE = 'create'
UPDATE = 'update'
DELETE = 'delete'

# Service operation status constants
ACTIVE = "ACTIVE"
DOWN = "DOWN"
CREATED = "CREATED"
PENDING_CREATE = "PENDING_CREATE"
PENDING_UPDATE = "PENDING_UPDATE"
PENDING_DELETE = "PENDING_DELETE"
INACTIVE = "INACTIVE"
ERROR = "ERROR"

ACTIVE_PENDING_STATUSES = (
    ACTIVE,
    PENDING_CREATE,
    PENDING_UPDATE
)

# Constants to extend status strings in neutron.plugins.common.constants
ONLINE = 'ONLINE'
OFFLINE = 'OFFLINE'
DEGRADED = 'DEGRADED'
DISABLED = 'DISABLED'
NO_MONITOR = 'NO_MONITOR'

""" HTTP request/response """
HAPROXY_AGENT_LISTEN_PORT = 9443
HTTP_REQ_METHOD_POST = 'POST'
HTTP_REQ_METHOD_GET = 'GET'
HTTP_REQ_METHOD_PUT = 'PUT'
HTTP_REQ_METHOD_DELETE = 'DELETE'
CONTENT_TYPE_HEADER = 'Content-type'
JSON_CONTENT_TYPE = 'application/json'

LB_METHOD_ROUND_ROBIN = 'ROUND_ROBIN'
LB_METHOD_LEAST_CONNECTIONS = 'LEAST_CONNECTIONS'
LB_METHOD_SOURCE_IP = 'SOURCE_IP'

PROTOCOL_TCP = 'TCP'
PROTOCOL_HTTP = 'HTTP'
PROTOCOL_HTTPS = 'HTTPS'

HEALTH_MONITOR_PING = 'PING'
HEALTH_MONITOR_TCP = 'TCP'
HEALTH_MONITOR_HTTP = 'HTTP'
HEALTH_MONITOR_HTTPS = 'HTTPS'

LBAAS = 'lbaas'

""" Event ids """
EVENT_CREATE_LOADBALANCER = 'CREATE_LOADBALANCER'
EVENT_UPDATE_LOADBALANCER = 'UPDATE_LOADBALANCER'
EVENT_DELETE_LOADBALANCER = 'DELETE_LOADBALANCER'

EVENT_CREATE_LISTENER = 'CREATE_LISTENER'
EVENT_UPDATE_LISTENER = 'UPDATE_LISTENER'
EVENT_DELETE_LISTENER = 'DELETE_LISTENER'

EVENT_CREATE_POOL = 'CREATE_POOL'
EVENT_UPDATE_POOL = 'UPDATE_POOL'
EVENT_DELETE_POOL = 'DELETE_POOL'

EVENT_CREATE_MEMBER = 'CREATE_MEMBER'
EVENT_UPDATE_MEMBER = 'UPDATE_MEMBER'
EVENT_DELETE_MEMBER = 'DELETE_MEMBER'

EVENT_CREATE_HEALTH_MONITOR = 'CREATE_HEALTH_MONITOR'
EVENT_UPDATE_HEALTH_MONITOR = 'UPDATE_HEALTH_MONITOR'
EVENT_DELETE_HEALTH_MONITOR = 'DELETE_HEALTH_MONITOR'

EVENT_AGENT_UPDATED = 'AGENT_UPDATED'
EVENT_COLLECT_STATS = 'COLLECT_STATS'
