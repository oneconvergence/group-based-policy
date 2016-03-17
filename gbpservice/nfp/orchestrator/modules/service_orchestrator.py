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

from oslo_log import log as logging
import oslo_messaging

from gbpservice.nfp.common import constants as nfp_constants
from gbpservice.nfp.common import topics as nfp_rpc_topics
from gbpservice.nfp.core.main import Event
from gbpservice.nfp.core.rpc import RpcAgent
from gbpservice.nfp.orchestrator.db import api as nfp_db_api
from gbpservice.nfp.orchestrator.db import nfp_db as nfp_db
from gbpservice.nfp.orchestrator.openstack import heat_driver
from gbpservice.nfp.orchestrator.openstack import openstack_driver


LOG = logging.getLogger(__name__)


def rpc_init(controller, config):
    rpcmgr = RpcHandler(config, controller)
    agent = RpcAgent(controller,
                     host=config.host,
                     topic=nfp_rpc_topics.NFP_NSO_TOPIC,
                     manager=rpcmgr)
    controller.register_rpc_agents([agent])


def events_init(controller, config, service_orchestrator):
    events = ['DELETE_NETWORK_FUNCTION', 'CREATE_NETWORK_FUNCTION_INSTANCE',
              'DELETE_NETWORK_FUNCTION_INSTANCE', 'DEVICE_CREATED',
              'DEVICE_ACTIVE', 'DEVICE_DELETED',
              'APPLY_USER_CONFIG_IN_PROGRESS',
              'DELETE_USER_CONFIG_IN_PROGRESS', 'USER_CONFIG_APPLIED',
              'USER_CONFIG_DELETED', 'USER_CONFIG_DELETE_FAILED',
              'DEVICE_CREATE_FAILED', 'USER_CONFIG_FAILED']
    events_to_register = []
    for event in events:
        events_to_register.append(
            Event(id=event, handler=service_orchestrator))
    controller.register_events(events_to_register)


def module_init(controller, config):
    events_init(controller, config, ServiceOrchestrator(controller))
    rpc_init(controller, config)


class RpcHandler(object):
    RPC_API_VERSION = '1.0'
    target = oslo_messaging.Target(version=RPC_API_VERSION)

    def __init__(self, conf, controller):
        super(RpcHandler, self).__init__()
        self.conf = conf
        self._controller = controller

    def create_network_function(self, context, network_function):
        service_orchestrator = ServiceOrchestrator(self._controller)
        return service_orchestrator.create_network_function(
            context, network_function)

    def get_network_function(self, context, network_function_id):
        service_orchestrator = ServiceOrchestrator(self._controller)
        return service_orchestrator.get_network_function(
            context, network_function_id)

    def get_network_functions(self, context, filters={}):
        service_orchestrator = ServiceOrchestrator(self._controller)
        return service_orchestrator.get_network_functions(
            context, filters)

    def update_network_function(self, context, network_function_id,
                               updated_network_function):
        service_orchestrator = ServiceOrchestrator(self._controller)
        return service_orchestrator.update_network_function(
            context, network_function_id, updated_network_function)

    def delete_network_function(self, context, network_function_id):
        LOG.info(_("RPC call delete_network_function for "
                   "%(network_function_id)s"),
                 {'network_function_id': network_function_id})
        service_orchestrator = ServiceOrchestrator(self._controller)
        return service_orchestrator.delete_network_function(
            context, network_function_id)

    def policy_target_added_notification(self, context, network_function_id,
                                         policy_target):
        service_orchestrator = ServiceOrchestrator(self._controller)
        return service_orchestrator.handle_policy_target_added(
            context, network_function_id, policy_target)

    def policy_target_removed_notification(self, context, network_function_id,
                                           policy_target):
        service_orchestrator = ServiceOrchestrator(self._controller)
        return service_orchestrator.handle_policy_target_removed(
            context, network_function_id, policy_target)

    def consumer_ptg_added_notification(self, context, network_function_id,
                                        policy_target_group):
        service_orchestrator = ServiceOrchestrator(self._controller)
        return service_orchestrator.handle_consumer_ptg_added(
            context, network_function_id, policy_target_group)

    def consumer_ptg_removed_notification(self, context, network_function_id,
                                          policy_target_group):
        service_orchestrator = ServiceOrchestrator(self._controller)
        return service_orchestrator.handle_consumer_ptg_removed(
            context, network_function_id, policy_target_group)


class ServiceOrchestrator(object):

    def __init__(self, controller):
        self._controller = controller
        self.db_handler = nfp_db.NFPDbBase()
        #self.db_session = nfp_db_api.get_session()
        self.gbpclient = openstack_driver.GBPClient()
        self.keystoneclient = openstack_driver.KeystoneClient()
        self.neutronclient = openstack_driver.NeutronClient()
        self.config_driver = heat_driver.HeatDriver()

    @property
    def db_session(self):
        return nfp_db_api.get_session()

    def event_method_mapping(self, event_id):
        event_handler_mapping = {
            "DELETE_NETWORK_FUNCTION": self.delete_network_function,
            "DELETE_NETWORK_FUNCTION_INSTANCE": (
                self.delete_network_function_instance),
            "CREATE_NETWORK_FUNCTION_INSTANCE": (
                self.create_network_function_instance),
            "DEVICE_CREATED": self.handle_device_created,
            "DEVICE_ACTIVE": self.handle_device_active,
            "APPLY_USER_CONFIG_IN_PROGRESS": (
                self.check_for_user_config_complete),
            "USER_CONFIG_APPLIED": self.handle_user_config_applied,
            "DELETE_USER_CONFIG_IN_PROGRESS": (
                self.check_for_user_config_deleted),
            "USER_CONFIG_DELETED": self.handle_user_config_deleted,
            "USER_CONFIG_DELETE_FAILED": self.handle_user_config_delete_failed,
            "DEVICE_DELETED": self.handle_device_deleted,
            "DEVICE_CREATE_FAILED": self.handle_device_create_failed,
            "USER_CONFIG_FAILED": self.handle_user_config_failed
        }
        if event_id not in event_handler_mapping:
            raise Exception("Invalid Event ID")
        else:
            return event_handler_mapping[event_id]

    def handle_event(self, event):
        try:
            event_handler = self.event_method_mapping(event.id)
            event_handler(event)
        except Exception:
            LOG.exception(_("Unhandled exception in handle event for event: %(event_id)s"), {'event_id': event.id})

    def handle_poll_event(self, event):
        LOG.info(_("NSO handle_poll_event, event ID %(id)s"), {'id': event.id})
        try:
            event_handler = self.event_method_mapping(event.id)
            event_handler(event)
        except Exception:
            LOG.exception(_("Unhandled exception in handle event for event: %(event_id)s"), {'event_id': event.id})

    def _log_event_created(self, event_id, event_data):
        LOG.info(_("Created event %s(event_name)s with event "
                    "data: %(event_data)s"),
                  {'event_name': event_id, 'event_data': event_data})

    def _create_event(self, event_id, event_data=None, key=None,
                      binding_key=None, serialize=False, is_poll_event=False):
        event = self._controller.new_event(id=event_id, data=event_data)
        if is_poll_event:
            self._controller.poll_event(event)
        else:
            self._controller.post_event(event)
        self._log_event_created(event_id, event_data)

    def create_network_function(self, context, network_function_info):
        # For neutron mode, we have handle port creation here
        self._validate_create_service_input(context, network_function_info)
        # GBP or Neutron
        mode = network_function_info['network_function_mode']
        service_profile_id = network_function_info['service_profile_id']
        service_id = network_function_info['service_id']
        admin_token = self.keystoneclient.get_admin_token()
        service_profile = self.gbpclient.get_service_profile(
            admin_token, service_profile_id)
        service_chain_id = network_function_info.get('service_chain_id')
        name = "%s.%s.%s" % (service_profile['service_type'],
                             service_profile['service_flavor'],
                             service_chain_id or service_id)
        network_function = {
            'name': name,
            'description': '',
            'tenant_id': network_function_info['tenant_id'],
            'service_id': service_id,  # GBP Service Node or Neutron Service ID
            'service_chain_id': service_chain_id,  # GBP SC instance ID
            'service_profile_id': service_profile_id,
            'service_config': network_function_info.get('service_config'),
            'status': nfp_constants.PENDING_CREATE
        }
        network_function = self.db_handler.create_network_function(
            self.db_session, network_function)

        if mode == nfp_constants.GBP_MODE:
            management_network_info = {
                'id': network_function_info['management_ptg_id'],
                'port_model': nfp_constants.GBP_NETWORK
        }
        create_network_function_instance_request = {
            'network_function': network_function,
            'network_function_port_info': network_function_info['port_info'],
            'management_network_info': management_network_info,
            'service_type': service_profile['service_type'],
            'service_vendor': service_profile['service_flavor'],
            'share_existing_device': False # Extend service profile
        }

        # Create and event to perform Network service instance
        self._create_event('CREATE_NETWORK_FUNCTION_INSTANCE',
                           event_data=create_network_function_instance_request)
        return network_function

    def update_network_function(self):
        # Handle config update
        pass

    def delete_network_function(self, context, network_function_id):
        network_function_info = self.db_handler.get_network_function(
            self.db_session, network_function_id)
        if not network_function_info['network_function_instances']:
            self.db_handler.delete_network_function(
                self.db_session, network_function_id)
            return
        network_function = {
            'status': nfp_constants.PENDING_DELETE
        }
        network_function = self.db_handler.update_network_function(
            self.db_session, network_function_id, network_function)

        if not network_function_info['heat_stack_id']:
            event_data = {
                'network_function_id': network_function_id
            }
            self._create_event('USER_CONFIG_DELETED',
                               event_data=event_data)
            return 

        self.config_driver.delete(network_function_info['heat_stack_id'],
                                  network_function['tenant_id'])
        request_data = {
            'heat_stack_id': network_function_info['heat_stack_id'],
            'tenant_id': network_function['tenant_id'],
            'network_function_id': network_function_id
        }
        self._create_event('DELETE_USER_CONFIG_IN_PROGRESS',
                           event_data=request_data, is_poll_event=True)

    def create_network_function_instance(self, event):
        request_data = event.data
        name = '%s.%s' % (request_data['network_function']['name'],
                          request_data['network_function']['id'])
        create_nfi_request = {
            'name': name,
            'tenant_id': request_data['network_function']['tenant_id'],
            'status': nfp_constants.PENDING_CREATE,
            'network_function_id': request_data['network_function']['id'],
            'service_type': request_data['service_type'],
            'service_vendor': request_data['service_vendor'],
            'share_existing_device': request_data['share_existing_device'],
            'port_info': request_data['network_function_port_info'],
        }
        nfi_db = self.db_handler.create_network_function_instance(
            self.db_session, create_nfi_request)

        create_nfd_request = {
            'network_function': request_data['network_function'],
            'network_function_instance': nfi_db,
            'management_network_info': request_data['management_network_info'],
            'service_type': request_data['service_type'],
            'service_vendor': request_data['service_vendor'],
            'share_existing_device': request_data['share_existing_device'],
        }
        self._create_event('CREATE_NETWORK_FUNCTION_DEVICE',
                           event_data=create_nfd_request)

    def handle_device_created(self, event):
        request_data = event.data
        nfi = {
            'network_function_device_id': request_data[
                'network_function_device_id']
        }
        nfi = self.db_handler.update_network_function_instance(
            self.db_session, request_data['network_function_instance_id'], nfi)
        return

    def handle_device_active(self, event):
        request_data = event.data
        nfi = {
            'status': nfp_constants.ACTIVE,
            'network_function_device_id': request_data[
                'network_function_device_id']
        }
        nfi = self.db_handler.update_network_function_instance(
            self.db_session, request_data['network_function_instance_id'], nfi)
        network_function_details = self.get_network_function_details(
            nfi['network_function_id'])
        request_data['heat_stack_id'] = self.config_driver.apply_user_config(
                network_function_details)  # Heat driver to launch stack
        request_data['tenant_id'] = nfi['tenant_id']
        LOG.debug("handle_device_active heat_stack_id: %s" %(request_data['heat_stack_id']))
        self.db_handler.update_network_function(
            self.db_session, nfi['network_function_id'],
            {'heat_stack_id': request_data['heat_stack_id']})
        request_data['network_function_id'] = nfi['network_function_id']
        self._create_event('APPLY_USER_CONFIG_IN_PROGRESS',
                           event_data=request_data,
                           is_poll_event=True)

    def handle_device_create_failed(self, event):
        request_data = event.data
        LOG.info(_("In handle_device_create_failed request data : %s"), request_data)
        nfi = {
            'status': nfp_constants.ERROR,
            'network_function_device_id': request_data.get(
                'network_function_device_id')
        }
        nfi = self.db_handler.update_network_function_instance(
            self.db_session, request_data['network_function_instance_id'], nfi)
        network_function = {'status': nfp_constants.ERROR}
        self.db_handler.update_network_function(
            self.db_session, nfi['network_function_id'], network_function)
        # Trigger RPC to notify the Create_Service caller with status

    def _update_network_function_instance(self):
        pass

    def delete_network_function_instance(self, event):
        nfi_id = event.data
        nfi = {'status': nfp_constants.PENDING_DELETE}
        nfi = self.db_handler.update_network_function_instance(
            self.db_session, nfi_id, nfi)
        if nfi['network_function_device_id']:
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
                               event_data=device_deleted_event)

    def _validate_create_service_input(self, context, create_service_request):
        required_attributes = ["tenant_id", "service_id", "service_chain_id",
                               "service_profile_id", "network_function_mode"]
        if (set(required_attributes) & set(create_service_request.keys()) !=
            set(required_attributes)):
            raise Exception("Some mandatory arguments are missing in "
                            "create service request")
        if create_service_request['network_function_mode'].lower() == "gbp":
            gbp_required_attributes = ["port_info", "service_chain_id",
                                       "management_ptg_id"]
            if (set(gbp_required_attributes) &
                set(create_service_request.keys()) !=
                set(gbp_required_attributes)):
                raise Exception("Some mandatory arguments for GBP mode are "
                                "missing in create service request")

    def check_for_user_config_complete(self, event):
        request_data = event.data
        config_status = self.config_driver.is_config_complete(
            request_data['heat_stack_id'], request_data['tenant_id'])
        if config_status == nfp_constants.ERROR:
            updated_network_function = {'status': nfp_constants.ERROR}
            self.db_handler.update_network_function(
                self.db_session,
                request_data['network_function_id'],
                updated_network_function)
            self._controller.poll_event_done(event)
            # Trigger RPC to notify the Create_Service caller with status
        elif config_status == "COMPLETED":
            updated_network_function = {'status': nfp_constants.ACTIVE}
            self.db_handler.update_network_function(
                self.db_session,
                request_data['network_function_id'],
                updated_network_function)
            self._controller.poll_event_done(event)
            # Trigger RPC to notify the Create_Service caller with status
        elif config_status == "IN_PROGRESS":
            return

    def check_for_user_config_deleted(self, event):
        request_data = event.data
        try:
            config_status = self.config_driver.is_config_delete_complete(
                request_data['heat_stack_id'], request_data['tenant_id'])
        except Exception as err:
            # FIXME: May be we need a count before removing the poll event
            LOG.error(_("Checking is_config_delete_complete failed. Error: %(err)s"), {'err': err})
            return
        if config_status == nfp_constants.ERROR:
            event_data = {
                'network_function_id': request_data['network_function_id']
            }
            self._create_event('USER_CONFIG_DELETE_FAILED',
                               event_data=event_data)
            self._controller.poll_event_done(event)
            # Trigger RPC to notify the Create_Service caller with status
        elif config_status == "COMPLETED":
            updated_network_function = {'heat_stack_id': None}
            self.db_handler.update_network_function(
                self.db_session,
                request_data['network_function_id'],
                updated_network_function)
            event_data = {
                'network_function_id': request_data['network_function_id']
            }
            self._create_event('USER_CONFIG_DELETED',
                               event_data=event_data)
            self._controller.poll_event_done(event)
            # Trigger RPC to notify the Create_Service caller with status
        elif config_status == "IN_PROGRESS":
            return

    def handle_user_config_applied(self, event):
        request_data = event.data
        network_function = {
            'status': nfp_constants.ACTIVE,
            'heat_stack_id': request_data['heat_stack_id']
        }
        self.db_handler.update_network_function(
            self.db_session,
            request_data['network_function_id'],
            network_function)
        # Trigger RPC to notify the Create_Service caller with status

    def handle_user_config_failed(self, event):
        request_data = event.data
        updated_network_function = {
            'status': nfp_constants.ERROR,
            'heat_stack_id': request_data.get('heat_stack_id')
        }
        self.db_handler.update_network_function(
            self.db_session,
            request_data['network_function_id'],
            updated_network_function)
        # Trigger RPC to notify the Create_Service caller with status

    # TODO: When NDO deletes Device DB, the Foreign key NSI will be nulled
    def handle_user_config_deleted(self, event):
        request_data = event.data
        network_function = self.db_handler.get_network_function(
            self.db_session,
            request_data['network_function_id'])
        for nfi_id in network_function['network_function_instances']:
            self._create_event('DELETE_NETWORK_FUNCTION_INSTANCE',
                               event_data=nfi_id)

    # Change to Delete_failed or continue with instance and device
    # delete if config delete fails? or status CONFIG_DELETE_FAILED ??
    def handle_user_config_delete_failed(self, event):
        request_data = event.data
        updated_network_function = {
            'status': nfp_constants.ERROR,
        }
        self.db_handler.update_network_function(
            self.db_session,
            request_data['network_function_id'],
            updated_network_function)
        # Trigger RPC to notify the Create_Service caller with status ??

    # When NDO deletes Device DB, the Foreign key NSI will be nulled
    # So we have to pass the NSI ID in delete event to NDO and process
    # the result based on that
    def handle_device_deleted(self, event):
        request_data = event.data
        nfi_id = request_data['network_function_instance_id']
        nfi = self.db_handler.get_network_function_instance(
            self.db_session, nfi_id)
        self.db_handler.delete_network_function_instance(
            self.db_session, nfi_id)
        network_function = self.db_handler.get_network_function(
            self.db_session, nfi['network_function_id'])
        if not network_function['network_function_instances']:
            self.db_handler.delete_network_function(
                self.db_session, nfi['network_function_id'])
            # Inform delete service caller with delete completed RPC

    # But how do you get hold of the first event ??
    def _request_completed(self, event):
        self._controller.event_done(event)

    def get_network_function(self, context, network_function_id):
        try:
            network_function = self.db_handler.get_network_function(
                self.db_session, network_function_id)
            LOG.info(_("In get_network_function, returning: %(network_function)s"), {'network_function': network_function['status']})
            return network_function
        except Exception:
            LOG.exception(_("Error in get_network_function"))
            return None

    def get_network_functions(self, context, filters):
        return self.db_handler.get_network_functions(
            self.db_session, filters)

    def handle_policy_target_added(self, context, network_function_id,
                                   policy_target):
        network_function = self.db_handler.get_network_function(
            self.db_session, network_function_id)
        network_function_details = self.get_network_function_details(
            network_function_id)
        required_attributes = ["network_function", "network_function_instance",
                               "network_function_device"]
        if (set(required_attributes) & set(network_function_details.keys()) !=
            set(required_attributes)):
                self.db_handler.update_network_function(
                    self.db_session,
                    network_function['id'],
                    {'status': nfp_constants.ERROR,
                     'status_description': ("Config Update for Policy Target "
                                            "addition event failed")})
                return
        config_id = self.config_driver.handle_policy_target_added(
            network_function_details, policy_target)
        self.db_handler.update_network_function(
            self.db_session,
            network_function['id'],
            {'heat_stack_id': config_id})
        request_data = {
            'heat_stack_id': config_id,
            'tenant_id': network_function['tenant_id'],
            'network_function_id': network_function_id
        }
        self._create_event('APPLY_USER_CONFIG_IN_PROGRESS',
                           event_data=request_data, is_poll_event=True)

    def handle_policy_target_removed(self, context, network_function_id,
                                     policy_target):
        network_function = self.db_handler.get_network_function(
            self.db_session, network_function_id)
        network_function_details = self.get_network_function_details(
            network_function_id)
        required_attributes = ["network_function", "network_function_instance",
                               "network_function_device"]
        if (set(required_attributes) & set(network_function_details.keys()) !=
            set(required_attributes)):
                self.db_handler.update_network_function(
                    self.db_session,
                    network_function['id'],
                    {'status': nfp_constants.ERROR,
                     'status_description': ("Config Update for Policy Target "
                                            "removed event failed")})
                return
        config_id = self.config_driver.handle_policy_target_removed(
            network_function_details, policy_target)
        self.db_handler.update_network_function(
            self.db_session,
            network_function['id'],
            {'heat_stack_id': config_id})
        request_data = {
            'heat_stack_id': config_id,
            'tenant_id': network_function['tenant_id'],
            'network_function_id': network_function_id
        }
        self._create_event('APPLY_USER_CONFIG_IN_PROGRESS',
                           event_data=request_data, is_poll_event=True)

    def handle_consumer_ptg_added(self, context, network_function_id,
                                  consumer_ptg):
        network_function = self.db_handler.get_network_function(
            self.db_session, network_function_id)
        network_function_details = self.get_network_function_details(
            network_function_id)
        config_id = self.config_driver.handle_consumer_ptg_added(
            network_function_details, consumer_ptg)
        required_attributes = ["network_function", "network_function_instance",
                               "network_function_device"]
        if (set(required_attributes) & set(network_function_details.keys()) !=
            set(required_attributes)):
                self.db_handler.update_network_function(
                    self.db_session,
                    network_function['id'],
                    {'status': nfp_constants.ERROR,
                     'status_description': ("Config Update for Consumer Policy"
                                            " Target Group Addition failed")})
                return
        self.db_handler.update_network_function(
            self.db_session,
            network_function['id'],
            {'heat_stack_id': config_id})
        request_data = {
            'heat_stack_id': config_id,
            'tenant_id': network_function['tenant_id'],
            'network_function_id': network_function_id
        }
        self._create_event('APPLY_USER_CONFIG_IN_PROGRESS',
                           event_data=request_data,
                           is_poll_event=True)

    def handle_consumer_ptg_removed(self, context, network_function_id,
                                    consumer_ptg):
        network_function = self.db_handler.get_network_function(
            self.db_session, network_function_id)
        network_function_details = self.get_network_function_details(
            network_function_id)
        required_attributes = ["network_function", "network_function_instance",
                               "network_function_device"]
        if (set(required_attributes) & set(network_function_details.keys()) !=
            set(required_attributes)):
                self.db_handler.update_network_function(
                    self.db_session,
                    network_function['id'],
                    {'status': nfp_constants.ERROR,
                     'status_description': ("Config Update for Consumer Policy"
                                            " Target Group Removal failed")})
                return
        config_id = self.config_driver.handle_consumer_ptg_removed(
            network_function_details, consumer_ptg)
        self.db_handler.update_network_function(
            self.db_session,
            network_function['id'],
            {'heat_stack_id': config_id})
        request_data = {
            'heat_stack_id': config_id,
            'tenant_id': network_function['tenant_id'],
            'network_function_id': network_function_id
        }
        self._create_event('APPLY_USER_CONFIG_IN_PROGRESS',
                           event_data=request_data, is_poll_event=True)

    def get_network_function_details(self, network_function_id):
        network_function = self.db_handler.get_network_function(
            self.db_session, network_function_id)
        network_function_details = {
            'network_function': network_function
        }
        network_function_instances = network_function['network_function_instances']
        if not network_function_instances:
            return network_function_details
        nfi = self.db_handler.get_network_function_instance(
            self.db_session, network_function_instances[0])
        network_function_details['network_function_instance'] = nfi
        if nfi['network_function_device_id']:
            network_function_device = self.db_handler.get_network_function_device(
                self.db_session, nfi['network_function_device_id'])
            network_function_details['network_function_device'] = network_function_device
        return network_function_details
