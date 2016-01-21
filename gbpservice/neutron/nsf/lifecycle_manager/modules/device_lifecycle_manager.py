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

from gbpservice.neutron.nsf.core.main import ServiceController
from gbpservice.neutron.nsf.core.main import Event
from gbpservice.neutron.nsf.core.main import RpcAgent
from gbpservice.neutron.nsf.core.main import RpcManager
from gbpservice.neutron.nsf.db import nsf_db as nsf_db
from gbpservice.neutron.nsf.lifecycle_manager.drivers import (
    haproxy_lifecycle_driver)
from gbpservice.neutron.nsf.lifecycle_manager.drivers import (
    vyos_lifecycle_driver)


def rpc_init(controller):
    rpcmgr = RpcHandler(cfg.CONF, controller)
    agent = RpcAgent(
        controller,
        host=cfg.CONF.host,
        topic="NSF_DEVICE_LIFECYCLE_MANAGER",
        manager=rpcmgr)
    controller.register_rpc_agents([agent])

def events_init(controller):
    evs = [
        Event(id='CREATE_NETWORK_SERVICE_DEVICE',
              handler=DeviceLifeCycleManager),
        Event(id='DELETE_NETWORK_SERVICE_DEVICE',
              handler=DeviceLifeCycleManager),
        Event(id='DEVICE_SPAWNING', handler=DeviceLifeCycleManager),
        Event(id='DEVICE_ACTIVE', handler=DeviceLifeCycleManager),
        Event(id='DEVICE_HEALTHY', handler=DeviceLifeCycleManager),
        Event(id='DEVICE_LICENSED', handler=DeviceLifeCycleManager),
        Event(id='DEVICE_READY', handler=DeviceLifeCycleManager), # Sharing
        Event(id='DEVICE_INTERFACES_SETUP', handler=DeviceLifeCycleManager),
        Event(id='DEVICE_ROUTES_CONFIGURED', handler=DeviceLifeCycleManager),
        Event(id='DEVICE_CONFIGURED', handler=DeviceLifeCycleManager),

        Event(id='DEVICE_CREATE_FAILED', handler=DeviceLifeCycleManager),
        Event(id='DEVICE_NOT_REACHABLE', handler=DeviceLifeCycleManager),
        Event(id='DEVICE_LICENSING_FAILED', handler=DeviceLifeCycleManager),
        Event(id='DEVICE_INTERFACES_SETUP_FAILED',
              handler=DeviceLifeCycleManager),
        Event(id='DEVICE_ROUTES_CONFIGURE_FAILED',
              handler=DeviceLifeCycleManager)]
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

    # Health check status change notification from Configurator
    def health_check_status_notification(self, context, **kwargs):
        resource = kwargs.get('resource')
        status = kwargs.get('status')
        if status == "HEALTHY":
            ev = self._controller.event(
                id='DEVICE_HEALTHY', data=resource, handler=None)
        else:
            ev = self._controller.event(
                id='DEVICE_NOT_REACHABLE', data=resource, handler=None)
        self._controller.rpc_event(ev, resource['id'])

    # Add license status, interface config status, any other notification required
    def license_status_notification(self, context, **kwargs):
        resource = kwargs.get('resource')
        status = kwargs.get('status')
        if status == "SUCCESS":
            ev = self._controller.event(
                id='LICENSE_APPLIED', data=resource, handler=None)
        else:
            ev = self._controller.event(
                id='LICENSE_FAILED', data=resource, handler=None)
        self._controller.rpc_event(ev, resource['id'])

    def interface_configuration_status_notification(self, context, **kwargs):
        resource = kwargs.get('resource')
        status = kwargs.get('status')
        if status == "SUCCESS":
            ev = self._controller.event(
                id='DEVICE_INTERFACES_SETUP', data=resource, handler=None)
        else:
            ev = self._controller.event(
                id='DEVICE_CONFIGURATION_FAILED', data=resource, handler=None)
        self._controller.rpc_event(ev, resource['id'])

    def routes_configuration_status_notification(self, context, **kwargs):
        resource = kwargs.get('resource')
        status = kwargs.get('status')
        if status == "SUCCESS":
            ev = self._controller.event(
                id='DEVICE_ROUTES_CONFIGURED', data=resource, handler=None)
        else:
            ev = self._controller.event(
                id='DEVICE_CONFIGURATION_FAILED', data=resource, handler=None)
        self._controller.rpc_event(ev, resource['id'])


class DeviceLifeCycleManager(object):
    def __init__(self):
        pass

    def event_method_mapping(self, state, device_lifecycle_handler):
        state_machine = {
            "CREATE_NETWORK_SERVICE_DEVICE": (
                device_lifecycle_handler.create_network_service_device),
            "DELETE_NETWORK_SERVICE_DEVICE": (
                device_lifecycle_handler.delete_network_service_device),
            "DEVICE_SPAWNING": device_lifecycle_handler.check_device_active,
            "DEVICE_ACTIVE": device_lifecycle_handler.perform_health_check,
            "DEVICE_HEALTHY": device_lifecycle_handler.license_device,
            "LICENSE_APPLIED": (
                device_lifecycle_handler.handle_licensing_completed),
            "DEVICE_READY": device_lifecycle_handler.setup_interfaces,
            "DEVICE_INTERFACES_SETUP": (
                device_lifecycle_handler.setup_device_routes),
            "DEVICE_ROUTES_CONFIGURED": (
                device_lifecycle_handler.device_configuration_complete),

            # Failures states, some may not be really required
            "DEVICE_ERROR": device_lifecycle_handler.handle_device_error,
            "DEVICE_NOT_UP": device_lifecycle_handler.handle_device_not_up,
            "DEVICE_NOT_REACHABLE": (
                device_lifecycle_handler.handle_device_not_reachable),
            "DEVICE_CONFIGURATION_FAILED": (
                device_lifecycle_handler.handle_device_config_failed),
            "LICENSE_FAILED": device_lifecycle_handler.handle_license_failed,
        }
        if state not in state_machine:
            raise Exception("Invalid state")
        else:
            return state_machine[state]

    def handle_event(self, ev):
        device_lifecycle_handler = DeviceLifeCycleHandler()
        self.event_method_mapping(ev.id, device_lifecycle_handler)(
            ev.data, state=ev.id)


class DeviceLifeCycleHandler(object):
    def __init__(self, request, state="INIT", _id=None):
        self.id = _id
        self.state = state
        self.request = request
        self.lifecycle_driver = self._get_vendor_lifecycle_driver(
            request.vendor, request.device_classification)

    def create_network_service_device(self, profile, device_classification):
        """ Returns device instance for a new service

        This method either returns existing device which could be reused for a
        new service or it creates new device instance
        """
        device = None
        is_device_sharing_supported = (
            self.lifecycle_driver.is_device_sharing_supported(
                profile, device_classification))
        if is_device_sharing_supported:
            device = self.lifecycle_driver.get_device_to_reuse(
                profile, device_classification)
            # What event to create here ?? Or proceed with next step ??
            # should we return something here so that the state machine 
            # loop itself with create next event ?
        if not device:
            device = self.lifecycle_driver.create_device(
                profile, device_classification)
            self._create_device_instance_in_db() # state = INIT
            # Post a new timer event
            ev = self._controller.event(id='DEVICE_SPAWNING',
                                        data=None, handler=self)
            self._controller.poll_event(ev, self.id)

    def delete_network_service_device(self):
        # Invoke driver deletes, driver informs if ref count is to be
        # decremented or entry deleted from DB. We do the DB handling here
        # accordingly. Then generate an event to Service LCM to inform about
        # the status
        pass

    def update_network_service_device(self):
        pass

    def _increment_device_ref_count(self):
        pass

    def _decrement_device_ref_count(self):
        pass

    def _get_vendor_lifecycle_driver(self, vendor_name,
                                     device_classification=None):
        # Replace with an autoload and auto choose mechanism
        # Each driver either registers the service type and vendor it supports
        # or there is an interface in driver to get that information
        if vendor_name == "haproxy":
            return haproxy_lifecycle_driver.HaproxyLifeCycleDriver()
        elif vendor_name == "vyos":
            return vyos_lifecycle_driver.VyosLifeCycleDriver()
        else:
            raise Exception() # Raise a proper exception class

    def device_configuration_complete(self):
        # Change status to active in DB and generate an event to inform
        # Service LCM
        pass

    def setup_device_routes(self):
        self.lifecycle_driver.setup_device_routes()

    def check_device_active(self):
        pass

    def perform_health_check(self):
        # The driver tells which protocol / port to monitor ??
        hm_req = self.lifecycle_driver.get_device_healthcheck_params()
        self.rpc_handler.monitor_device_health(hm_req)

    def license_device(self):
        # Post an event to config queue with the required details of service VM
        pass

    def handle_licensing_completed(self):
        pass

    def setup_interfaces(self):
        self.lifecycle_driver.plug_interfacess()
        self.lifecycle_driver.configure_interfaces()

    def clear_interfaces(self):
        self.lifecycle_driver.unplug_interfaces()
        self.lifecycle_driver.clear_interfaces()

    def handle_device_error(self):
        pass

    def handle_device_not_up(self):
        pass

    def handle_device_config_failed(self):
        pass

    def handle_license_failed(self):
        pass

    def handle_config_failed(self):
        pass
