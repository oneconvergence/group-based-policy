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

from oslo.config import cfg

from gbpservice.neutron.nsf.core.main import Event
from gbpservice.neutron.nsf.core.main import RpcAgent
from gbpservice.neutron.nsf.core.main import RpcManager
from gbpservice.neutron.nsf.db import nsf_db as nsf_db


def rpc_init(controller):
    rpcmgr = RpcHandler(cfg.CONF, controller)
    agent = RpcAgent(controller, host=cfg.CONF.host,
                     topic="NSF_SERVICE_LIFECYCLE_MANAGER",
                     manager=rpcmgr)
    controller.register_rpc_agents([agent])

def events_init(controller):
    evs = [
        Event(id='DELETE_NETWORK_SERVICE', handler=ServiceLifeCycleManager),
        Event(id='CREATE_NETWORK_SERVICE_INSTANCE',
              handler=ServiceLifeCycleManager),
        Event(id='DELETE_NETWORK_SERVICE_INSTANCE',
              handler=ServiceLifeCycleManager),
        Event(id='DEVICE_ACTIVE', handler=ServiceLifeCycleManager),
        Event(id='USER_CONFIG_IN_PROGRESS', handler=ServiceLifeCycleManager),
        Event(id='USER_CONFIG_APPLIED', handler=ServiceLifeCycleManager),
        Event(id='DEVICE_CREATE_FAILED', handler=ServiceLifeCycleManager),
        Event(id='USER_CONFIG_FAILED', handler=ServiceLifeCycleManager)]
    controller.register_events(evs)


def module_init(controller):
    events_init(controller)
    rpc_init(controller)


class RpcHandler(RpcManager):
    RPC_API_VERSION = '1.0'

    def __init__(self, conf, controller):
        super(RpcHandler, self).__init__()
        self.conf = conf
        self._controller = controller

    def create_network_service(self, context, **kwargs):
        service_lifecycle_handler = ServiceLifeCycleHandler()
        service_lifecycle_handler.create_network_service(context, kwargs)


class ServiceLifeCycleManager(object):

    def __init__(self):
        pass

    def event_method_mapping(self, state, service_lifecycle_handler):
        state_machine = {
            "DELETE_NETWORK_SERVICE": (
                service_lifecycle_handler.delete_network_service),
            "CREATE_NETWORK_SERVICE_INSTANCE": (
                service_lifecycle_handler.create_network_service_instance),
            "DEVICE_ACTIVE": service_lifecycle_handler.handle_device_created,
            "USER_CONFIG_IN_PROGRESS": (
                service_lifecycle_handler.check_for_user_config_complete),
            "USER_CONFIG_APPLIED": (
                service_lifecycle_handler.handle_user_config_applied),
            "DEVICE_CREATE_FAILED": (
                service_lifecycle_handler.handle_device_create_failed),
            "USER_CONFIG_FAILED": (
                service_lifecycle_handler.handle_user_config_failed)
        }
        if state not in state_machine:
            raise Exception("Invalid state")
        else:
            return state_machine[state]

    def handle_event(self, ev):
        service_lifecycle_handler = ServiceLifeCycleHandler()
        self.event_method_mapping(ev.id, service_lifecycle_handler)(ev.data, state=ev.id)


class ServiceLifeCycleHandler(object):
    def __init__(self, request, state="INIT", _id=None):
        self.id = _id
        self.state = state
        self.request = request

    def create_network_service(self):
        # Somewhere here we have to differentiate GBP vs Neutron *aas and do
        # stitching etc
        self._validate_create_service_input()
        network_service = self._create_network_service_db(self.request, state="PENDING_CREATE")
        self.id = network_service['id']
        create_network_service_instance_request = {} # Fill in the data here with which to invoke
        # create Network service instance
        ev = self._controller.event(id='CREATE_NETWORK_SERVICE_INSTANCE',
                                    data=create_network_service_instance_request,
                                    handler=self)
        self._controller.poll_event(ev, self.id) # Not timer taks ??
        return self.id

    def update_network_service(self):
        # Handle config update
        pass

    def delete_network_service(self):
        pass

    def create_network_service_instance(self, request):
        self._create_nsi_db(self.request, state="PENDING_CREATE")

    def handle_device_created(self, request, device):
        self._update_nsi_db(self.request, state=device['state'], device=device)
        if device['state'] == "ACTIVE":
            self.config_driver.apply_user_config() # Heat driver to launch stack

    def handle_devices_create_failed(self):
        pass

    def _update_network_service_instance(self):
        pass

    def _delete_network_service_instance(self):
        pass

    def _validate_create_service_input(self):
        pass

    def check_for_user_config_complete(self):
        pass

    def handle_user_config_failed(self):
        pass
