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

from neutron._i18n import _LE
from neutron._i18n import _LI

from gbpservice.nfp.common import constants as nfp_constants
from gbpservice.nfp.common import exceptions as nfp_exc
from gbpservice.nfp.common import topics as nfp_rpc_topics
from gbpservice.nfp.core import context as nfp_core_context
from gbpservice.nfp.core.event import Event
from gbpservice.nfp.core import module as nfp_api
from gbpservice.nfp.core.rpc import RpcAgent
from gbpservice.nfp.lib import transport
from gbpservice.nfp.orchestrator.config_drivers import heat_driver
from gbpservice.nfp.orchestrator.db import nfp_db as nfp_db
from gbpservice.nfp.orchestrator.openstack import openstack_driver

import sys
import traceback

from gbpservice.nfp.core import log as nfp_logging


from gbpservice.nfp.orchestrator.modules.service_orchestrator import (
    ServiceOrchestrator, events_init, rpc_init)

LOG = nfp_logging.getLogger(__name__)

STOP_POLLING = {'poll': False}
CONTINUE_POLLING = {'poll': True}


def nfp_module_init(controller, config):
    events_init(controller, config, ServiceOrchestratorNSD(controller, config))
    rpc_init(controller, config)


class ServiceOrchestratorNSD(ServiceOrchestrator):

    def _get_network_function_instance_for_multi_service_sharing(self,
                                                                 port_info):
        network_function_instances = (
            self.db_handler.get_network_function_instances(self.db_session,
                                                           filters={}))
        provider_port_id = None
        for port in port_info:
            if port['port_classification'] == 'provider':
                provider_port_id = port['id']
                break
        for network_function_instance in network_function_instances:
            if (provider_port_id in network_function_instance['port_info'] and
                network_function_instance['network_function_device_id']
                    is not None):
                return network_function_instance
        return None


    def create_network_function_instance(self, event):
        nfp_context = event.data

        network_function = nfp_context['network_function']
        # service_profile = nfp_context['service_profile']
        service_details = nfp_context['service_details']
        consumer = nfp_context['consumer']
        provider = nfp_context['provider']

        port_info = []
        for ele in [consumer, provider]:
            if ele['pt']:
                # REVISIT(ashu): Only pick few chars from id
                port_info.append(
                    {'id': ele['pt']['id'],
                     'port_model': ele['port_model'],
                     'port_classification': ele['port_classification']
                     })

        # REVISIT(ashu): Only pick few chars from id
        name = '%s_%s' % (network_function['name'],
                          network_function['id'])
        network_function_instance = (
            self._get_network_function_instance_for_multi_service_sharing(
                port_info))
        if network_function_instance:
            port_info = []
        create_nfi_request = {
            'name': name,
            'tenant_id': network_function['tenant_id'],
            'status': nfp_constants.PENDING_CREATE,
            'network_function_id': network_function['id'],
            'service_type': service_details['service_type'],
            'service_vendor': service_details['service_vendor'],
            'share_existing_device': nfp_context['share_existing_device'],
            'port_info': port_info,
        }
        nfi_db = self.db_handler.create_network_function_instance(
            self.db_session, create_nfi_request)
        if network_function_instance:
            port_info = []
            for port_id in network_function_instance['port_info']:
                port_info.append(self.db_handler.get_port_info(self.db_session,
                                                               port_id))
            nfi = {
                'port_info': port_info
            }
            nfi_db = self.db_handler.update_network_function_instance(
                self.db_session, nfi_db['id'], nfi)
            nfd_data = {}
            nfd_data['network_function_instance_id'] = nfi_db['id']
            nfd_data['network_function_device_id'] = (
                network_function_instance['network_function_device_id'])
            self._create_event('DEVICE_ACTIVE',
                               event_data=nfd_data)

            return
        # Sending LogMeta Details to visibility
        self._report_logging_info(network_function,
                                  nfi_db,
                                  service_details['service_type'],
                                  service_details['service_vendor'])

        nfp_context['network_function_instance'] = nfi_db

        LOG.info(_LI("[Event:CreateService]"))
        self._create_event('CREATE_NETWORK_FUNCTION_DEVICE',
                           event_data=nfp_context)


    def delete_network_function_instance(self, event):
        nfi_id = event.data
        nfi = {'status': nfp_constants.PENDING_DELETE}
        nfi = self.db_handler.update_network_function_instance(
            self.db_session, nfi_id, nfi)
        if nfi['network_function_device_id']:

            filters = {
                'network_function_device_id': [
                    nfi['network_function_device_id']],
                'status': ['ACTIVE']
            }
            network_function_instances = (
                self.db_handler.get_network_function_instances(
                    self.db_session, filters=filters))
            if network_function_instances:
                device_deleted_event = {
                    'network_function_instance_id': nfi['id']
                }
                network_function = self.db_handler.get_network_function(
                    self.db_session, nfi['network_function_id'])
                nf_id = network_function['id']
                self.db_handler.delete_network_function(
                    self.db_session, nfi['network_function_id'])
                LOG.info(_LI("NSO: Deleted network function: %(nf_id)s"),
                         {'nf_id': nf_id})

                return
            delete_nfd_request = {
                'network_function_device_id': nfi[
                    'network_function_device_id'],
                'network_function_instance': nfi,
                'network_function_id': nfi['network_function_id']
            }
            self._create_event('DELETE_NETWORK_FUNCTION_DEVICE',
                               event_data=delete_nfd_request)
        else:
            device_deleted_event = {
                'network_function_instance_id': nfi['id']
            }
            self._create_event('DEVICE_DELETED',
                               event_data=device_deleted_event,
                               is_internal_event=True)


