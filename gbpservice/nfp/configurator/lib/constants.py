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

supported_service_types = ['firewall', 'vpn', 'loadbalancer']
NFP_SERVICE_LIST = ['heat', 'ansible']
invalid_service_type = 'invalid'
NFP_SERVICE = 'nfp_service'
SUCCESS = 'SUCCESS'
FAILURE = 'FAILURE'
GENERIC_CONFIG = 'generic_config'
FAILED = 'FAILED'
ORCHESTRATOR = 'orchestrator'
EVENT_STASH = 'STASH_EVENT'
EVENT_PROCESS_BATCH = 'PROCESS_BATCH'
NFD_NOTIFICATION = 'network_function_device_notification'
RABBITMQ_HOST = '127.0.0.1'  # send notifications to 'RABBITMQ_HOST'
NOTIFICATION_QUEUE = 'configurator-notifications'
