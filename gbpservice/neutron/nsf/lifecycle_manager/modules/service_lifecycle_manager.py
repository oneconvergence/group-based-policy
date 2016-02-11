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

from gbpservice.neutron.nsf.common import topics as nsf_rpc_topics
from gbpservice.neutron.nsf.core.main import Event
from gbpservice.neutron.nsf.core.main import RpcAgent
from gbpservice.neutron.nsf.db import api as nsf_db_api
from gbpservice.neutron.nsf.db import nsf_db as nsf_db
from gbpservice.neutron.nsf.lifecycle_manager.openstack import openstack_driver
from gbpservice.neutron.nsf.lifecycle_manager.openstack import heat_driver

LOG = logging.getLogger(__name__)


def rpc_init(controller, config):
    rpcmgr = RpcHandler(config, controller)
    agent = RpcAgent(controller, 
                     topic=nsf_rpc_topics.NSF_SERVICE_LCM_TOPIC,
                     manager=rpcmgr)
    controller.register_rpc_agents([agent])


def events_init(controller, config):
    events = [
        Event(id='DELETE_NETWORK_SERVICE',
              handler=ServiceLifeCycleManager(controller)),
        Event(id='CREATE_NETWORK_SERVICE_INSTANCE',
              handler=ServiceLifeCycleManager(controller)),
        Event(id='DELETE_NETWORK_SERVICE_INSTANCE',
              handler=ServiceLifeCycleManager(controller)),
        Event(id='DEVICE_ACTIVE',
              handler=ServiceLifeCycleManager(controller)),
        Event(id='DEVICE_DELETED',
              handler=ServiceLifeCycleManager(controller)),
        Event(id='USER_CONFIG_IN_PROGRESS',
              handler=ServiceLifeCycleManager(controller)),
        Event(id='USER_CONFIG_APPLIED',
              handler=ServiceLifeCycleManager(controller)),
        Event(id='DEVICE_CREATE_FAILED',
              handler=ServiceLifeCycleManager(controller)),
        Event(id='USER_CONFIG_FAILED',
              handler=ServiceLifeCycleManager(controller))]
    controller.register_events(events)


def module_init(controller, config):
    events_init(controller, config)
    rpc_init(controller, config)


class RpcHandler(object):
    RPC_API_VERSION = '1.0'
    target = oslo_messaging.Target(version=RPC_API_VERSION)

    def __init__(self, conf, controller):
        super(RpcHandler, self).__init__()
        self.conf = conf
        self._controller = controller

    def create_network_service(self, context, network_service):
        service_lifecycle_handler = ServiceLifeCycleHandler(self._controller)
        return service_lifecycle_handler.create_network_service(
            context, network_service)

    def get_network_service(self, context, network_service_id):
        service_lifecycle_handler = ServiceLifeCycleHandler(self._controller)
        return service_lifecycle_handler.get_network_service(
            context, network_service_id)

    def get_network_services(self, context, filters={}):
        service_lifecycle_handler = ServiceLifeCycleHandler(self._controller)
        return service_lifecycle_handler.get_network_service(
            context, filters)

    def delete_network_service(self, context, network_service_id):
        service_lifecycle_handler = ServiceLifeCycleHandler(self._controller)
        return service_lifecycle_handler.delete_network_service(
            context, network_service_id)

    def added_consumer_ptg(self, context, network_service_id, ptg):
        service_lifecycle_handler = ServiceLifeCycleHandler(self._controller)
        return service_lifecycle_handler.added_consumer_ptg(
            context, network_service_id, ptg)
 
    def removed_consumer_ptg(self, context, network_service_id, ptg):
        service_lifecycle_handler = ServiceLifeCycleHandler(self._controller)
        return service_lifecycle_handler.removed_consumer_ptg(
            context, network_service_id, ptg)

    def policy_target_added(self, context, network_service_id, policy_target):
        service_lifecycle_handler = ServiceLifeCycleHandler(self._controller)
        return service_lifecycle_handler.policy_target_added(
            context, network_service_id, policy_target)

    def policy_target_removed(self, context, network_service_id, policy_target):
        service_lifecycle_handler = ServiceLifeCycleHandler(self._controller)
        return service_lifecycle_handler.policy_target_removed(
            context, network_service_id, policy_target)

class ServiceLifeCycleManager(object):

    def __init__(self, controller):
        self.controller = controller

    def event_method_mapping(self, state, service_lifecycle_handler):
        state_machine = {
            "DELETE_NETWORK_SERVICE": (
                service_lifecycle_handler.delete_network_service),
            "DELETE_NETWORK_SERVICE_INSTANCE": (
                service_lifecycle_handler._delete_network_service_instance),
            "CREATE_NETWORK_SERVICE_INSTANCE": (
                service_lifecycle_handler.create_network_service_instance),
            "DEVICE_ACTIVE": service_lifecycle_handler.handle_device_created,
            "USER_CONFIG_IN_PROGRESS": (
                service_lifecycle_handler.check_for_user_config_complete),
            "USER_CONFIG_APPLIED": (
                service_lifecycle_handler.handle_user_config_applied),
            "DEVICE_DELETED": (
                service_lifecycle_handler.handle_device_deleted),
            "DEVICE_CREATE_FAILED": (
                service_lifecycle_handler.handle_device_create_failed),
            "USER_CONFIG_FAILED": (
                service_lifecycle_handler.handle_user_config_failed)
        }
        if state not in state_machine:
            raise Exception("Invalid state")
        else:
            return state_machine[state]

    def handle_event(self, event):
        service_lifecycle_handler = ServiceLifeCycleHandler(self.controller)
        self.event_method_mapping(event.id, service_lifecycle_handler)(
            event)

    def handle_poll_event(self, event):
        service_lifecycle_handler = ServiceLifeCycleHandler(self.controller)
        self.event_method_mapping(event.id, service_lifecycle_handler)(
            event)

class ServiceLifeCycleHandler(object):
    def __init__(self, controller):
        self._controller = controller
        self.db_handler = nsf_db.NSFDbBase()
        self.db_session = nsf_db_api.get_session()
        self.gbpclient = openstack_driver.GBPClient()
        self.keystoneclient = openstack_driver.KeystoneClient()
        self.neutronclient = openstack_driver.NeutronClient()
        self.config_driver = heat_driver.HeatDriver()

    def _log_event_created(self, event_id, event_data):
        LOG.debug(_("Created event %s(event_name)s with event "
                    "data: %(event_data)s"),
                   {'event_name': event_id, 'event_data': event_data})

    def _create_event(self, event_id, event_data=None, key=None,
                    binding_key=None, serialize=False, is_poll_event=False):
        event = self._controller.event(id=event_id, data=event_data)
        if is_poll_event:
            self._controller.poll_event(event)
        else:
            self._controller.rpc_event(event)
        self._log_event_created(event_id, event_data)

    def create_network_service(self, context, network_service_info):
        # We have to differentiate GBP vs Neutron *aas and perform
        # different things here - eg traffic stitching
        self._validate_create_service_input(context, network_service_info)
        # GBP or Neutron
        mode = network_service_info.get('network_service_mode')
        service_profile_id = network_service_info.get('service_profile_id')
        service_id = network_service_info.get('service_id')
        admin_token = self.keystoneclient.get_admin_token()
        service_profile = self.gbpclient.get_service_profile(
            admin_token, service_profile_id)
        service_chain_id = network_service_info.get('service_chain_id')
        name = "%s.%s.%s" % (service_profile['service_type'],
                             service_profile['vendor'],
                             service_chain_id or service_id)
        network_service = {
            'name': name,
            'description': '',
            'tenant_id': network_service_info['tenant_id'],
            'service_id': service_id,  # GBP Service Node or Neutron Service ID
            'service_chain_id': service_chain_id,  # GBP SC instance ID
            'service_profile_id': service_profile_id,
            'service_config': network_service_info.get('service_config'),
            'status': 'PENDING_CREATE'
        }

        network_service_port_info = []
        provider_port_info = {
            'id': network_service_info['provider_port_id'],
            'port_policy': mode,
            'port_classification': 'provider'
        }
        network_service_port_info.append(provider_port_info)
        if network_service_info.get('consumer_port_id'):
            consumer_port_info = {
                'id': network_service_info['consumer_port_id'],
                'port_policy': mode,
                'port_classification': 'consumer'
            }
            network_service_port_info.append(consumer_port_info)

        network_service = self.db_handler.create_network_service(
            self.db_session, network_service)
        create_network_service_instance_request = {
            'network_service': network_service,
            'network_service_port_info': network_service_port_info,
            'service_type': service_profile['service_type'],
            'service_vendor': service_profile['vendor'],
            'share_existing_device': service_profile.get('unique_device', True)
        }
        # Create and event to perform Network service instance
        create_nsi_event = self._controller.event(
            id='CREATE_NETWORK_SERVICE_INSTANCE',
            data=create_network_service_instance_request)
        self._controller.rpc_event(create_nsi_event)
        return network_service['id']

    def update_network_service(self):
        # Handle config update
        pass

    def delete_network_service(self, context, network_service_id):
        network_service_info = self.db_handler.get_network_service(
            self.db_session, network_service_id)
        network_service = {}
        network_service['status'] = "PENDING_DELETE"
        network_service = self.db_handler.update_network_service(
            self.db_session, network_service_id, network_service)
        for nsi_id in network_service_info['network_service_instances']:
            delete_nsi_event = self._controller.event(
                id='DELETE_NETWORK_SERVICE_INSTANCE',
                data=nsi_id)
            self._controller.rpc_event(delete_nsi_event)

    def create_network_service_instance(self, event):
        request_data = event.data
        name = '%s.%s' % (request_data['network_service']['name'],
                          request_data['network_service']['id'])
        create_nsi_request = {
            'name': name,
            'tenant_id': request_data['network_service']['tenant_id'],
            'status': 'PENDING_CREATE',
            'network_service_id': request_data['network_service']['id'],
            'service_type': request_data['service_type'],
            'service_vendor': request_data['service_vendor'],
            'share_existing_device': request_data['share_existing_device'],
            'port_info': request_data[
                'network_service_port_info'],
        }
        nsi_db = self.db_handler.create_network_service_instance(
            self.db_session, create_nsi_request)

        '''
        create_nsd_request = {
            'network_service': request_data['network_service'],
            'network_service_instance': nsi_db,
            'service_type': request_data['service_type'],
            'service_vendor': request_data['service_vendor'],
            'share_existing_device': request_data['network_service_port_info'],
        }
        '''
        nsi = {
            'network_service_instance_id': nsi_db['id']
        }
        create_nsi_event = self._controller.event(
            #id='CREATE_NETWORK_SERVICE_DEVICE',
            id='DEVICE_ACTIVE',
            data=nsi)
        self._controller.rpc_event(create_nsi_event)
        #self._controller.rpc_event(nsi_db)

    def get_provider_policy_target_group(self, provider_port):
        
        admin_token = self.keystoneclient.get_admin_token()
        provider_port_id = provider_port['id']
        policy_target = self.gbpclient.get_policy_targets(admin_token,
                filters={'port_id': provider_port_id })[0]
        policy_target_group = self.gbpclient.get_policy_target_groups(
                admin_token, filters={'id': policy_target['policy_target_group_id']})

        return policy_target_group[0]

    def get_service_details(self, nsi):
        network_service = self.db_handler.get_network_service(
                self.db_session, nsi['network_service_id'])
        #network_service_device = self.db_handler.get_network_service_device(
        #        self.db_session, nsi['network_service_device_id'])

        heat_stack_id = network_service['heat_stack_id']
        service_profile_id = network_service['service_profile_id']
        admin_token = self.keystoneclient.get_admin_token()
        service_profile = self.gbpclient.get_service_profile(admin_token, 
                service_profile_id)
        service_id = network_service['service_id']
        servicechain_node = self.gbpclient.get_servicechain_node(admin_token, 
                service_id)
        service_chain_id = network_service['service_chain_id']
        servicechain_instance = self.gbpclient.get_servicechain_instance(
                admin_token, 
                service_chain_id)
        #mgmt_ip = network_service_device['mgmt_data_ports'][0]['mgmt_ip_address']
        mgmt_ip = "11.0.0.24" #network_service_device['mgmt_ip_address']
        consumer_port = 'None'
        provider_port = 'None'
        for port in nsi['port_info']:
	    port_info = self.db_handler.get_port_info(self.db_session, port)
            port_classification = port_info['port_classification']
            if port_info['port_policy'] == "GBP":
                policy_target_id = port_info['id']
                port_id = self.gbpclient.get_policy_targets(admin_token,
                     filters={'id': policy_target_id })[0]['port_id']
            else:
                port_id = port_info['id']

            if port_classification == "consumer":
                consumer_port = self.neutronclient.get_port(admin_token, 
                        port_id)['port']
            else:
                provider_port = self.neutronclient.get_port(admin_token, 
                        port_id)['port']

        policy_target_group = self.get_provider_policy_target_group(provider_port)
        service_details = {
            'service_profile': service_profile,
            'servicechain_node': servicechain_node,
            'servicechain_instance': servicechain_instance,
            'consumer_port': consumer_port,
            'provider_port': provider_port,
            'mgmt_ip': mgmt_ip,
            'policy_target_group': policy_target_group,
            'heat_stack_id': heat_stack_id,
        }
        return service_details

    def handle_device_created(self, event):
        request_data = event.data
        nsi = self.db_handler.get_network_service_instance(
            self.db_session, request_data['network_service_instance_id'])
        
        port_info = self.db_handler.get_port_info(self.db_session, nsi['port_info'][0])
        nsi['status'] = "DEVICE_CREATED"
        #nsi['network_service_device_id'] = request_data[
        #    'network_service_device_id']
	del nsi['port_info']
        nsi = self.db_handler.update_network_service_instance(
            self.db_session, nsi['id'], nsi)
        service_details = self.get_service_details(nsi)
        request_data['heat_stack_id'] = self.config_driver.apply_user_config(
                service_details) # Heat driver to launch stack
        request_data['network_service_id'] = nsi['network_service_id']
        self._create_event(event_id='USER_CONFIG_IN_PROGRESS',
                event_data=request_data, is_poll_event=True)

    def handle_device_create_failed(self, event):
        request_data = event.data
        nsi = {}
        nsi['status'] = "DEVICE_CREATE_FAILED"
        nsi['id'] = request_data['network_service_instance_id']
        nsi['network_service_device_id'] = request_data.get(
            'network_service_device_id')
        self.db_handler.update_network_service_instance(
            self.db_session, nsi['id'], nsi)
        network_service = {}
        network_service['id'] = request_data['network_service_id']
        network_service['status'] = "ERROR"
        self.db_handler.update_network_service(
            self.db_session, network_service['id'], network_service)
        # Trigger RPC to notify the Create_Service caller with status

    def _update_network_service_instance(self):
        pass

    def _delete_network_service_instance(self, event):
        nsi_id = event.data
        nsi_info = self.db_handler.get_network_service_instance(
            self.db_session, nsi_id)
        nsi = {}
        nsi['status'] = "PENDING_DELETE"
        self.db_handler.update_network_service_instance(
            self.db_session, nsi_id, nsi)

        #Adding below four lines for DEVICE_DELETED event only
        request_data = {}
        request_data['network_service_instance_id'] = nsi_info['id']
        network_service = self.db_handler.get_network_service(
            self.db_session, nsi_info['network_service_id'])
        request_data['heat_stack_id'] = network_service['heat_stack_id']

        delete_nsd_event = self._controller.event(
            #id='DELETE_NETWORK_SERVICE_DEVICE',
            #data=nsi['network_service_device_id'])
            id="DEVICE_DELETED",
            data=request_data)
        self._controller.rpc_event(delete_nsd_event)

    def _validate_create_service_input(self, context, create_service_request):
        required_attributes = ["tenant_id", "service_id",
                               "service_chain_id", "service_profile_id"]
        if (set(required_attributes) & set(create_service_request.keys()) !=
            set(required_attributes)):
            raise Exception("Some mandatory arguments are missing in "
                            "create service request")

    def check_for_user_config_complete(self, event):
        request_data = event.data
        config_status = self.config_driver.is_config_complete(
            request_data['heat_stack_id'])
        if config_status == "COMPLETED":
            self._controller.poll_event_done(event)
            self._create_event(event_id='USER_CONFIG_APPLIED',
                    event_data=request_data)
        elif config_status == "ERROR":
            self._controller.poll_event_done(event)
            self._create_event(event_id='USER_CONFIG_FAILED',
                    event_data=request_data)
        elif config_status == "IN_PROGRESS":
            return

    def handle_user_config_failed(self, event):
        request_data = event.data
        network_service = {}
        network_service['status'] = "ERROR"
        network_service['heat_stack_id'] = request_data['heat_stack_id']
        network_service['id'] = request_data['network_service_id']
        self.db_handler.update_network_service(
            self.db_session, network_service['id'], network_service)
        # Trigger RPC to notify the Create_Service caller with status

    # When Device LCM deletes Device DB, the Foreign key NSI will be nulled
    # So we have to pass the NSI ID in delete event to device LCM and process
    # the result based on that
    def handle_device_deleted(self, event):
        request_data = event.data
        nsi_id = request_data['network_service_instance_id']
        config_id = request_data['heat_stack_id']
        nsi = self.db_handler.get_network_service_instance(
            self.db_session, nsi_id)
        service_details = self.get_service_details(nsi)
        provider_policy_target_group = service_details['policy_target_group']
        self.config_driver.delete(provider_policy_target_group, config_id)
        self.db_handler.delete_network_service_instance(
            self.db_session, nsi_id)
        network_service = self.db_handler.get_network_service(
            self.db_session, nsi['network_service_id'])
        if not network_service['network_service_instances']:
            self.db_handler.delete_network_service(
                self.db_session, nsi['network_service_id'])
            # Inform delete service caller with delete completed RPC

    # But how do you get hold of the first event ??
    def _request_completed(self, event):
        self._controller.event_done(event)

    def handle_user_config_applied(self, event):
        request_data = event.data
        network_service = {}
        network_service['id'] = request_data['network_service_id']
        network_service['status'] = "ACTIVE"
        network_service['heat_stack_id'] = request_data['heat_stack_id']
        self.db_handler.update_network_service(
                self.db_session, network_service['id'], network_service)
        # Trigger RPC to notify the Create_Service caller with status

    def added_consumer_ptg(self, context, network_service_id, ptg):
        network_service = self.db_handler.get_network_service(
                    self.db_session, network_service_id)
        nsi_id = network_service['network_service_instances'][0]
        nsi = self.db_handler.get_network_service_instance(
                    self.db_session, nsi_id)
        service_details = self.get_service_details(nsi)
        config_id = self.config_driver.update_node_consumer_ptg_added(
            service_details, ptg)
        request_data = {}
        request_data['heat_stack_id'] = config_id 
        request_data['network_service_id'] = nsi['network_service_id']
        self._create_event(event_id='USER_CONFIG_IN_PROGRESS',
                event_data=request_data, is_poll_event=True)
 
    def removed_consumer_ptg(self, context, network_service_id, ptg):
        network_service = self.db_handler.get_network_service(
                    self.db_session, network_service_id)
        nsi_id = network_service['network_service_instances'][0]
        nsi = self.db_handler.get_network_service_instance(
                    self.db_session, nsi_id)
        service_details = self.get_service_details(nsi)
        config_id = self.config_driver.update_node_consumer_ptg_added(
            service_details, ptg)
        request_data = {}
        request_data['heat_stack_id'] = config_id
        request_data['network_service_id'] = nsi['network_service_id']
        self._create_event(event_id='USER_CONFIG_IN_PROGRESS',
                event_data=request_data, is_poll_event=True)

    def policy_target_added(self, context, network_service_id, policy_target):
        network_service = self.db_handler.get_network_service(
                    self.db_session, network_service_id)
        nsi_id = network_service['network_service_instances'][0]
        nsi = self.db_handler.get_network_service_instance(
                    self.db_session, nsi_id)
        service_details = self.get_service_details(nsi)
        config_id = self.config_driver.update_policy_target_added(
            service_details, policy_target)
        request_data = {}
        request_data['heat_stack_id'] = config_id
        request_data['network_service_id'] = nsi['network_service_id']
        self._create_event(event_id='USER_CONFIG_IN_PROGRESS',
                event_data=request_data, is_poll_event=True)

    def policy_target_removed(self, context, network_service_id, policy_target):
        network_service = self.db_handler.get_network_service(
                    self.db_session, network_service_id)
        nsi_id = network_service['network_service_instances'][0]
        nsi = self.db_handler.get_network_service_instance(
                    self.db_session, nsi_id)
        service_details = self.get_service_details(nsi)
        config_id = self.config_driver.update_policy_target_removed(
            service_details, policy_target)
        request_data = {}
        request_data['heat_stack_id'] = config_id
        request_data['network_service_id'] = nsi['network_service_id']
        self._create_event(event_id='USER_CONFIG_IN_PROGRESS',
                event_data=request_data, is_poll_event=True)

 
    def get_network_service(self, context, network_service_id):
        return self.db_handler.get_network_service(
            self.db_session, network_service_id)

    def get_network_services(self, context, filters):
        return self.db_handler.get_network_services(
            self.db_session, filters)
