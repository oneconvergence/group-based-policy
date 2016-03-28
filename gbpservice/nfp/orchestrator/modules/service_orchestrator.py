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
from gbpservice.nfp.orchestrator.openstack.plumber import SCPlumber
import constants as orchestrator_constants

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
        self.neutron_handler = SOHelper()

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

    def neutron_update_nw_function_config(self, context, network_function):
        """
        RPC cast().
        :param context:
        :param network_function:
        :return:
        """
        service_orchestrator = ServiceOrchestrator(self._controller)
        self.neutron_handler.process_update_network_function_request(
            context, service_orchestrator, network_function)

    def neutron_delete_nw_function_config(self, context, network_function):
        """
        RPC cast()
        :param context:
        :param network_function:
        :return:
        """
        service_orchestrator = ServiceOrchestrator(self._controller)
        self.neutron_handler.process_delete_network_function_request(
            service_orchestrator, network_function)


class ServiceOrchestrator(object):
    def __init__(self, controller):
        self._controller = controller
        self.db_handler = nfp_db.NFPDbBase()
        # self.db_session = nfp_db_api.get_session()
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
            LOG.exception(_(
                "Unhandled exception in handle event for event: %(event_id)s"),
                          {'event_id': event.id})

    def handle_poll_event(self, event):
        LOG.info(_("NSO handle_poll_event, event ID %(id)s"), {'id': event.id})
        try:
            event_handler = self.event_method_mapping(event.id)
            event_handler(event)
        except Exception:
            LOG.exception(_(
                "Unhandled exception in handle event for event: %(event_id)s"),
                          {'event_id': event.id})

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
            'description': network_function_info.get('description', ''),
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
        else:
            management_network_info = \
                network_function_info['management_network_info']
        create_network_function_instance_request = {
            'network_function': network_function,
            'network_function_port_info': network_function_info['port_info'],
            'management_network_info': management_network_info,
            'service_type': service_profile['service_type'],
            'service_vendor': service_profile['service_flavor'],
            'share_existing_device': False  # Extend service profile
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
        # REVISIT(VK) For neutron workflow. What if GBP workflow require to
        # fill description field.
        if network_function_details['description']:
            updated_network_function = {'status': nfp_constants.ACTIVE}
            self.db_handler.update_network_function(
                self.db_session, nfi['network_function_id'],
                updated_network_function)
            return
        request_data['heat_stack_id'] = self.config_driver.apply_user_config(
            network_function_details)  # Heat driver to launch stack
        request_data['tenant_id'] = nfi['tenant_id']
        LOG.debug("handle_device_active heat_stack_id: %s" % (
        request_data['heat_stack_id']))
        self.db_handler.update_network_function(
            self.db_session, nfi['network_function_id'],
            {'heat_stack_id': request_data['heat_stack_id']})
        request_data['network_function_id'] = nfi['network_function_id']
        self._create_event('APPLY_USER_CONFIG_IN_PROGRESS',
                           event_data=request_data,
                           is_poll_event=True)

    def handle_device_create_failed(self, event):
        request_data = event.data
        LOG.info(_("In handle_device_create_failed request data : %s"),
                 request_data)
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
            LOG.error(
                _("Checking is_config_delete_complete failed. Error: %(err)s"),
                {'err': err})
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
            LOG.info(
                _("In get_network_function, returning: %(network_function)s"),
                {'network_function': network_function['status']})
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
        network_function_instances = network_function[
            'network_function_instances']
        if not network_function_instances:
            return network_function_details
        nfi = self.db_handler.get_network_function_instance(
            self.db_session, network_function_instances[0])
        network_function_details['network_function_instance'] = nfi
        if nfi['network_function_device_id']:
            network_function_device = \
                self.db_handler.get_network_function_device(
                self.db_session, nfi['network_function_device_id'])
            network_function_details[
                'network_function_device'] = network_function_device
        return network_function_details


class SOHelper(object):
    def __init__(self):
        self.sc_plumber = SCPlumber()

    def process_update_network_function_request(self, context,
                                                service_orchestrator,
                                                nw_function_info):
        """
        :param context:
        :param service_orchestrator:
        :param nw_function_info:
        In Neutron case:
        nw_function_info = {'network_function_model': 'neutron',
                            'tenant_id': tenant_id,
                            'service_profile_id': service_profile_id,
                            'service_type':
                            'vpn_service/ipsec_site_connection/fw',
                            'service_info': [{'router_id': <>, 'port': <>,
                                            'subnet': <>}],
                            'resource_data': <>,
                            }
        :return:
        """
        if nw_function_info['service_type'].lower() == 'vpn_service' or \
                'ipsec_site_connection':
            return self.handle_processing_for_vpn(
                context, service_orchestrator, nw_function_info)
        elif nw_function_info['service_type'].lower() == 'fw':
            self.handle_processing_for_fw(context, service_orchestrator,
                                          nw_function_info)

    def process_delete_network_function_request(self, context,
                                                service_orchestrator,
                                                nw_function_info):
        service = self.get_nw_fun_details(service_orchestrator,
                                          nw_function_info)
        service_orchestrator.delete_network_function(service[0]['id'])

    def handle_processing_for_vpn(self, context, service_orchestrator,
                                  nw_function_info):
        fip_required = (True
                        if nw_function_info['service_type'].lower() ==
                        'vpn_service' else False)
        if not fip_required:
            return self.process_ipsec_request(nw_function_info,
                                              service_orchestrator)
        else:
            # This should return
            # {'port': <port details>, 'floating_ip': <fip>, 'gateway':
            # <gateway_ip>, 'cidr': <cidr>}
            router_id = nw_function_info['service_info'][0].get('router_id',
                                                                None)
            stitching_port = self.sc_plumber.get_stitching_port(
                nw_function_info['tenant_id'],
                router_id=router_id, fip_required=fip_required)
            stitching_port.update(
                port_model=orchestrator_constants.NEUTRON_PORT,
                port_classification=orchestrator_constants.CONSUMER)
            nw_function_info['management_network_info'] = dict(
                # id=self.config.NEUTRON_SERVICE_MGMT_NW,
                id='mgmt_nw',
                port_model=orchestrator_constants.NEUTRON_PORT
            )
            admin_token = service_orchestrator.keystoneclient.get_admin_token()
            provider_subnet = service_orchestrator.neutronclient.get_subnet(
                admin_token, nw_function_info['service_info'][0]['subnet'])[
                                                                   'subnet']
            # REVISIT(VK) - Mgmt Port related info cam't be fill here.
            # That's bad.
            desc = dict(# fip=stitching_port['floatingip'], # mgmt fip
                        tunnel_local_cidr=provider_subnet['cidr'],
                        user_access_ip=stitching_port['floating_ip'],
                        fixed_ip=stitching_port['port']['fixed_ips'][0][
                            'ip_address'],
                        standby_fip=None, service_vendor='vyos',
                        stitching_cidr=stitching_port['cidr'],
                        stitching_gateway=stitching_port['gateway'],
                        mgmt_gw_ip='',
                        network_service='neutron_vpn_service'
                        )
            # Prefix 'neutron' to identify *aaS requests
            nw_function_info['description'] = str(desc)
            nw_function_info['network_function_mode'] = "neutron"
            nw_function_info['port_info'] = [stitching_port]
            nw_function_info['service_chain_id'] = None
            nw_function_info['service_config'] = nw_function_info[
                'service_info'][0].get('router_id', None)
            nw_function_info['service_id'] = nw_function_info[
                'resource_data']['id']
            nw_function_info['share_existing_device'] = False
            return service_orchestrator.create_network_function(
                context, nw_function_info)

    def process_ipsec_request(self, nw_function_info, service_orchestrator):
        vpn_service = self.get_nw_fun_details(
            service_orchestrator, nw_function_info, 'vpn')
        if len(vpn_service) != 1:
            raise Exception()
        vpn_service = vpn_service[0]
        nw_function_info.update(vpn_service)
        vpn_service_instance = (
            service_orchestrator.db_handler.get_network_function_instances(
                service_orchestrator.db_session,
                filters={'network_function_id': [vpn_service['id']]}))
        if len(vpn_service_instance) != 1:
            raise Exception()
        vpn_service_instance = vpn_service_instance[0]
        self.update_nw_fun(service_orchestrator, vpn_service,
                           vpn_service_instance)
        _ports = vpn_service_instance['port_info']
        for u_port in _ports:
            _port = service_orchestrator.db_handler.get_port_info(u_port)
            if _port['port_classification'] == \
                    orchestrator_constants.CONSUMER:
                admin_token = service_orchestrator.keystoneclient \
                    .get_admin_token()
                gateway_ip = service_orchestrator.neutronclient.get_port(
                    admin_token, u_port)['port']['fixed_ips'][0][
                    'ip_address']
            break
        try:
            gateway_ip
        except NameError:
            raise NameError()
        # REVISIT(VK) For VPN, this field currently store router id. It
        # should go.
        router_id = vpn_service['service_config']
        self.sc_plumber.update_router_service_gateway(
            router_id, nw_function_info['resource_data']['peer_cidr'],
            gateway_ip)
        nw_function_info["ipsec_service_status"] = "ACTIVE"
        return nw_function_info

    @staticmethod
    def update_nw_fun(service_orchestrator, service,
                      service_instance):
        try:
            nw_function_device_id = service_instance[
                'network_function_device_id']
            nw_func_device_details = service_orchestrator.db_handler \
                .get_network_function_device(
                    service_orchestrator.db_session, nw_function_device_id)
            mgmt_ip = nw_func_device_details['mgmt_ip_address']
            import ast
            desc = ast.literal_eval(service['description'])
            desc.update(fip=mgmt_ip)
            service_orchestrator.db_handler.update_network_function(
                service_orchestrator.db_session, service['id'],
                {"description": str(desc)})
        except Exception, err:
            raise Exception(err)

    @staticmethod
    def handle_processing_for_fw(nw_function_info):
        provider_port = {'id': nw_function_info['service_info']['port']['id'],
                         'port_model': orchestrator_constants.NEUTRON_PORT,
                         'port_classification':
                             orchestrator_constants.PROVIDER}
        nw_function_info['port_info'].append(provider_port)
        nw_function_info['service_id'] = provider_port['id']

    def get_nw_fun_details(self, service_orchestrator, nw_function_info,
                           svc_type):
        get_details = getattr(self, 'get_%s_service_details' %
                              svc_type.lower())
        return get_details(service_orchestrator, nw_function_info)

    @staticmethod
    def get_vpn_service_details(service_orchestrator, nw_function_info):
        filters = dict(service_id=[nw_function_info['resource_data'][
                                       'vpnservice_id']])
        return service_orchestrator.db_handler.get_network_functions(
            service_orchestrator.db_session, filters=filters)

    @staticmethod
    def get_fw_service_details(service_orchestrator,  nw_function_info):
        filters = dict(service_id=[nw_function_info['service_info']['port'][
                                       'id']])
        return service_orchestrator.db_handler.get_network_functions(
            service_orchestrator.db_session, filters=filters)

    def postprocess_update_network_function_request(self):
        pass
