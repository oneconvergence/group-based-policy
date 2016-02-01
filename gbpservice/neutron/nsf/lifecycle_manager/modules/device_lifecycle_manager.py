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
from oslo import messaging

from gbpservice.neutron.nsf.core.main import ServiceController
from gbpservice.neutron.nsf.core.main import Event
from gbpservice.neutron.nsf.core.main import RpcAgent
from gbpservice.neutron.nsf.db import nsf_db as nsf_db
from gbpservice.neutron.nsf.db import api as nsf_db_api
from gbpservice.neutron.nsf.lifecycle_manager.compute.drivers import (
    nova_driver)
from gbpservice.neutron.nsf.lifecycle_manager.drivers import (
    haproxy_lifecycle_driver)
from gbpservice.neutron.nsf.lifecycle_manager.drivers import (
    vyos_lifecycle_driver)
from neutron.common import rpc as n_rpc
from neutron import context as n_context

import logging as LOG

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
        Event(id='DEVICE_SPAWNING', handler=DeviceLifeCycleManager),
        Event(id='DEVICE_UP', handler=DeviceLifeCycleManager),
        Event(id='DEVICE_HEALTHY', handler=DeviceLifeCycleManager),
        Event(id='LICENSE_APPLIED', handler=DeviceLifeCycleManager),
        Event(id='DEVICE_LICENSED', handler=DeviceLifeCycleManager),
        Event(id='DEVICE_READY', handler=DeviceLifeCycleManager), # Sharing
        Event(id='DEVICE_INTERFACES_SETUP', handler=DeviceLifeCycleManager),
        Event(id='DEVICE_ROUTES_CONFIGURED', handler=DeviceLifeCycleManager),
        Event(id='DEVICE_CONFIGURED', handler=DeviceLifeCycleManager),

        Event(id='DELETE_NETWORK_SERVICE_DEVICE',
              handler=DeviceLifeCycleManager),
        Event(id='DELETE_ROUTES', handler=DeviceLifeCycleManager),
        Event(id='DELETE_INTERFACES', handler=DeviceLifeCycleManager),
        Event(id='DELETE_CONFIGURATION', handler=DeviceLifeCycleManager),
        Event(id='DELETE_CONFIGURATION_COMPLETED', handler=DeviceLifeCycleManager),

        Event(id='DEVICE_CREATE_FAILED', handler=DeviceLifeCycleManager),
        Event(id='DEVICE_NOT_UP', handler=DeviceLifeCycleManager),
        Event(id='DEVICE_NOT_REACHABLE', handler=DeviceLifeCycleManager),
        Event(id='DEVICE_CONFIGURATION_FAILED', handler=DeviceLifeCycleManager),
        Event(id='DEVICE_LICENSING_FAILED', handler=DeviceLifeCycleManager),
        Event(id='DEVICE_INTERFACES_SETUP_FAILED',
              handler=DeviceLifeCycleManager),
        Event(id='DEVICE_ROUTES_CONFIGURE_FAILED',
              handler=DeviceLifeCycleManager)]
    controller.register_events(evs)


def module_init(controller):
    events_init(controller)
    rpc_init(controller)


class RpcHandler(RpcAgent):
    RPC_API_VERSION = '1.0'

    def __init__(self, conf, controller):
        super(RpcHandler, self).__init__()
        self.conf = conf
        self._controller = controller

    # Health check status change notification from Configurator
    def monitor_device_health_status_notification(self, context, **kwargs):
        resource = kwargs.get('resource')
        status = kwargs.get('status')
        if status == "HEALTHY":
            ev = self._controller.event(
                id='DEVICE_HEALTHY', data=resource)
        else:
            ev = self._controller.event(
                id='DEVICE_NOT_REACHABLE', data=resource)
        self._controller.rpc_event(ev, resource['id'])

    def setup_interfaces_status_notification(self, context, **kwargs):
        resource = kwargs.get('resource')
        status = kwargs.get('status')
        if status == "SUCCESS":
            ev = self._controller.event(
                id='DEVICE_INTERFACES_SETUP', data=resource)
        else:
            ev = self._controller.event(
                id='DEVICE_INTERFACES_SETUP_FAILED', data=resource)
        self._controller.rpc_event(ev, resource['id'])

    def setup_device_routes_status_notification(self, context, **kwargs):
        resource = kwargs.get('resource')
        status = kwargs.get('status')
        if status == "SUCCESS":
            ev = self._controller.event(
                id='DEVICE_ROUTES_CONFIGURED', data=resource)
        else:
            ev = self._controller.event(
                id='DEVICE_ROUTES_CONFIGURE_FAILED', data=resource)
        self._controller.rpc_event(ev, resource['id'])

    # Add license status, interface config status, any other notification required
    def license_status_notification(self, context, **kwargs):
        resource = kwargs.get('resource')
        status = kwargs.get('status')
        if status == "SUCCESS":
            ev = self._controller.event(
                id='LICENSE_APPLIED', data=resource)
        else:
            ev = self._controller.event(
                id='LICENSE_FAILED', data=resource)
        self._controller.rpc_event(ev, resource['id'])

    def setup_device_config_status_notification(self, context, **kwargs):
        resource = kwargs.get('resource')
        status = kwargs.get('status')
        if status == "SUCCESS":
            ev = self._controller.event(
                id='DEVICE_CONFIGURED', data=resource)
        else:
            ev = self._controller.event(
                id='DEVICE_CONFIGURATION_FAILED', data=resource)
        self._controller.rpc_event(ev, resource['id'])


    def delete_device_routes_status_notification(self, context, **kwargs):
        status = kwargs.get('status')
        resource = kwargs.get('resource')
        if status == "SUCCESS":
            ev = self._controller.event(
                id='DELETE_INTERFACES', data=resource)
        else:
            ev = self._controller.event(
                id='DEVICE_CONFIGURATION_FAILED', data=resource)
        self._controller.rpc_event(ev, resource['id'])

    def clear_interfaces_status_notification(self, context, **kwargs):
        status = kwargs.get('status')
        resource = kwargs.get('resource')
        if status == "SUCCESS":
            ev = self._controller.event(
                id='DELETE_CONFIGURATION', data=resource)
        else:
            ev = self._controller.event(
                id='DEVICE_CONFIGURATION_FAILED', data=resource)
        self._controller.rpc_event(ev, resource['id'])

    def delete_device_config_status_notification(self, context, **kwargs):
        status = kwargs.get('status')
        resource = kwargs.get('resource')
        if status == "SUCCESS":
            ev = self._controller.event(
                id='DELETE_CONFIGURATION_COMPLETED', data=resource)
        else:
            ev = self._controller.event(
                id='DEVICE_CONFIGURATION_FAILED', data=resource)
        self._controller.rpc_event(ev, resource['id'])




class DeviceLifeCycleManager(object):
    def __init__(self):
        pass

    def event_method_mapping(self, state, device_lifecycle_handler):
        state_machine = {
            "CREATE_NETWORK_SERVICE_DEVICE": (
                device_lifecycle_handler.create_network_service_device),
            "DEVICE_SPAWNING": device_lifecycle_handler.check_device_is_up,
            "DEVICE_UP": device_lifecycle_handler.perform_health_check,
            "DEVICE_HEALTHY": device_lifecycle_handler.license_device,
            "LICENSE_APPLIED": (
                device_lifecycle_handler.handle_licensing_completed),
            "DEVICE_READY": device_lifecycle_handler.setup_interfaces,
            "DEVICE_INTERFACES_SETUP": (
                device_lifecycle_handler.setup_device_routes),
            "DEVICE_ROUTES_CONFIGURED": (
                device_lifecycle_handler.create_device_configuration),
            "DEVICE_CONFIGURED": (
                device_lifecycle_handler.device_configuration_complete),

            "DELETE_NETWORK_SERVICE_DEVICE": (
                device_lifecycle_handler.delete_network_service_device),
            "DELETE_ROUTES": device_lifecycle_handler.delete_device_routes,
            "DELETE_INTERFACES": (
                device_lifecycle_handler.clear_interfaces),
            "DELETE_CONFIGURATION": (
                device_lifecycle_handler.delete_device_configuration),
            "DELETE_CONFIGURATION_COMPLETED": device_lifecycle_handler.device_delete,

            # Failures states, some may not be really required
            "DEVICE_CREATE_FAILED": (
                device_lifecycle_handler.handle_device_create_failed),
            "DEVICE_NOT_UP": device_lifecycle_handler.handle_device_not_up,
            "DEVICE_NOT_REACHABLE": (
                device_lifecycle_handler.handle_device_not_reachable),
            "DEVICE_CONFIGURATION_FAILED": (
                device_lifecycle_handler.handle_device_config_failed),
            "DEVICE_LICENSING_FAILED": device_lifecycle_handler.handle_license_failed,
            "DEVICE_ERROR": device_lifecycle_handler.handle_device_error,
            "DEVICE_INTERFACES_SETUP_FAILED": device_lifecycle_handler.handle_interfaces_setup_failed,
            "DEVICE_ROUTES_CONFIGURE_FAILED": device_lifecycle_handler.handle_routes_config_failed,
        }
        if state not in state_machine:
            raise Exception("Invalid state")
        else:
            return state_machine[state]

    def handle_event(self, ev):
        device_lifecycle_handler = DeviceLifeCycleHandler()
        self.event_method_mapping(ev.id, device_lifecycle_handler)(
            ev.data, state=ev.id)

    def handle_poll_event(self, ev):
        device_lifecycle_handler = DeviceLifeCycleHandler()
        self.event_method_mapping(ev.id, device_lifecycle_handler)(
            ev.data, state=ev.id)


class DeviceLifeCycleHandler(object):
    def __init__(self, request, state="INIT", _id=None):
        self.id = _id
        self.state = state
        self.request = request
        self.nsf_db = nsf_db.NSFDbBase()
        self.db_session = nsf_db_api.get_session()
        self.lifecycle_driver = self._get_vendor_lifecycle_driver(
            request.vendor, request.device_classification)
        self.compute_driver = self._get_compute_driver(
            request.vendor, request.device_classification)

        neutron_context = n_context.get_admin_context()
        self.configurator_rpc = DLCMConfiguratorRpcApi(neutron_context,
                                                  cfg.CONF.host)

        self.state_map = {
                'INIT': 'Created Network Service Device with status INIT.',
                'PENDING_CREATE': '',
                'DEVICE_SPAWNING': 'Creating NSD, launched the new device, ' +
                                    'polling on its status',
                'DEVICE_UP': 'Device is UP/ACTIVE',
                'HEALTH_CHECK_PENDING': 'Device health check is going on ' +
                                        ' through configurator',
                'HEALTH_CHECK_COMPLETED': 'Health check successfull for device',
                'INTERFACES_PLUGGED': 'Interfaces Plugging successfull',
                'PENDING_CONFIGURATION_CREATE': 'Started configuring device ' +
                                                'for routes, license, etc',
                'DEVICE_READY': 'Device is ready to use',
                'ACTIVE': 'Device is Active.',
                'DEVICE_NOT_UP': 'Device not became UP/ACTIVE',
                }

    # Helper functions
    def _log_event_created(self, event_id, event_data):
        LOG.debug(_("Created event %s(event_name)s with event "
                    "data: %(event_data)s"),
                  {'event_name': event_id, 'event_data': event_data})

    def _update_device_status(self, device, state):
        device['status'] = state
        device['status_description'] = self.state_map[state]

    def _create_network_service_device_db(self, device_info, state):
        self._update_device_status(device_info, state)
        #(ashu) driver should return device_id as vm_id
        device_id = device_info.pop('device_id')
        device_info['id'] = device_id
        device_info['reference_count'] = 0
        device_info['interfaces_in_use'] = 0
        #device_info['mgmt_data_ports']['id'] = device_id
        device = self.nsf_db.create_network_service_device(self.db_session,
                                                           device_info)
        return device

    def _update_network_service_device_db(self, device, state):
        self._update_device_status(device, state)
        self.nsf_db.update_network_service_device(self.db_session, device)

    def _delete_network_service_device_db(self, device, state):
        self._update_device_status(device, state)
        self.nsf_db.delete_network_service_device(self.db_session, device)

    def _get_network_service_devices(self, filters=None):
        network_service_devices = self.nsf_db.get_network_service_devices(
                                                            filters)
        return network_service_devices

    def _increment_device_ref_count(self, device):
        device['reference_count'] += 1

    def _decrement_device_ref_count(self, device):
        device['reference_count'] -= 1
        #self._update_network_service_device_db(device,
        #                                       device['status'],
        #                                       device['status_description'])

    def _increment_device_interface_count(self, device):
        device['interfaces_in_use'] += 1
        self._update_network_service_device_db(device,
                                               device['status'],
                                               device['status_description'])

    def _decrement_device_interface_count(self, device):
        device['interfaces_in_use'] -= 1
        self._update_network_service_device_db(device,
                                               device['status'],
                                               device['status_description'])

    def _get_vendor_lifecycle_driver(self):
        # Replace with an autoload and auto choose mechanism
        # Each driver either registers the service type and vendor it supports
        # or there is an interface in driver to get that information
        #vendor_name = data['service_vendor']
        vendor_name = 'haproxy'
        if vendor_name == "haproxy":
            return haproxy_lifecycle_driver.HaproxyLifeCycleDriver()
        elif vendor_name == "vyos":
            return vyos_lifecycle_driver.VyosLifeCycleDriver()
        else:
            raise Exception() # Raise a proper exception class

    def _get_compute_driver(self):
        # Replace with an autoload and auto choose mechanism
        # Each driver either registers the service type and vendor it supports
        # or there is an interface in driver to get that information
        vendor_name = 'compute'
        if vendor_name == "compute":
            return nova_driver.NovaAPIDriver()
        else:
            raise Exception() # Raise a proper exception class

    def _get_device_to_reuse(self, data):
        device_filters = self.lifecycle_driver.get_device_filters(data)
        devices = self._get_network_service_devices(device_filters)

        device = self.lifecycle_driver.get_device_to_reuse(devices)
        return device

    # Create path
    def create_network_service_device(self, data):
        """ Returns device instance for a new service

        This method either returns existing device which could be reused for a
        new service or it creates new device instance
        """
        profile = data['profile']
        # device_classification = data['device_classification']
        device = None
        device_id = data['network_service_id']
        service_type = data['service_type']
        service_vendor = data['service_vendor']
        LOG.info(_("Received create network service device request with data"
                   "%(data)s"), {'data': data})

        is_device_sharing_supported = (
            self.lifecycle_driver.is_device_sharing_supported(
                device))
        if is_device_sharing_supported:
            device = self._get_device_to_reuse(device)

        if is_device_sharing_supported and device:
            # Device is already active, no need to change status
            ev = self._controller.event(id='DEVICE_READY', data=device)
            self._controller.rpc_event(ev, device['id'])
            LOG.info(_("Sharing existing device: %s(device)s for reuse"),
                      {'device': device})
            self._log_event_created('DEVICE_READY', device)
            # What event to create here ?? Or proceed with next step ??
            # should we return something here so that the state machine
            # loop itself with create next event ?
        else:
            LOG.info(_("No Device exists for sharing, Creating new "
                       "device: %(device)s"), {'device': data})
            # Return mgmt_data_ports as list of dict
            # [{'id': port_id, 'port_policy': port_policy,
            #   'port_classification': port_classification, 'port_type': port_type}]
            device_info = self.lifecycle_driver.create_device(device)
            if not device_info:
                LOG.info(_("Device creation failed"))
                ev = self._controller.event(id='DEVICE_ERROR',
                                            data=data)
                self._controller.rpc_event(ev, device['id'])
                self._log_event_created('DEVICE_ERROR', device)
                return
            device = self._create_network_service_device_db(device_info, 'INIT')

            # Post a new timer event
            ev = self._controller.event(id='DEVICE_SPAWNING',
                                        data=device)
            self._controller.poll_event(ev, self.id)
            self._log_event_created('DEVICE_SPAWNING', device)

    def check_device_is_up(self, device):
        is_device_up = self.lifecycle_driver.is_device_up(device)
        if is_device_up:
            # create event DEVICE_UP
            self._controller.event_done('DEVICE_SPAWNING')

            ev = self._controller.event(id='DEVICE_UP', data=device)
            self._controller.rpc_event(ev, device['id'])
            self._log_event_created('DEVICE_UP', device)
            self._update_network_service_device_db(device['id'],
                                                   'DEVICE_UP')
        elif device['status'] == 'INIT':
            self._update_network_service_device_db(device['id'],
                                                   'DEVICE_SPAWNING')
        elif device['status'] == 'ERROR':
            # create event DEVICE_NOT_UP
            self._controller.event_done('DEVICE_SPAWNING')

            ev = self._controller.event(id='DEVICE_NOT_UP', data=device)
            self._controller.rpc_event(ev, device['id'])
            self._log_event_created('DEVICE_NOT_UP', device)
            self._update_network_service_device_db(device['id'],
                                                   'DEVICE_NOT_UP')

    def perform_health_check(self, device):
        self._controller.event_done('DEVICE_UP')
        # The driver tells which protocol / port to monitor ??
        hm_req = self.lifecycle_driver.get_device_healthcheck_params(device)
        self.configurator_rpc.monitor_device_health(hm_req)
        LOG.debug(_("Health Check RPC sent to configurator for device: "
                    "%(device_id)s with health check parameters: %(hm_req)s"),
                  {'device_id': device['id'], 'hm_req': hm_req})
        self._update_network_service_device_db(device['id'],
                                               'HEALTH_CHECK_PENDING')

    def license_device(self, device):
        self._controller.event_done('DEVICE_HEALTHY')
        LOG.info(_("Health check successfull for %(device)s"),
                 {'device': device})
        self._update_network_service_device_db(device['id'],
                                               'HEALTH_CHECK_COMPLETED')
        # Post an event to config queue with the required details of service VM
        self.configurator_rpc.license_device(device)
        # ev = self._controller.event(id='LICENSE_APPLIED', data=device)
        # self._controller.rpc_event(ev, device['id'])
        # self._log_event_created('LICENSE_APPLIED', device)
        # self._update_network_service_device_db(device['id'],
        #                                        'LICENSE_APPLIED')

    def handle_licensing_completed(self, device):
        self._controller.event_done('LICENSE_APPLIED')
        ev = self._controller.event(id='DEVICE_READY', data=device)
        self._controller.rpc_event(ev, device['id'])
        self._log_event_created('DEVICE_READY', device)
        self._update_network_service_device_db(device['id'],
                                               'DEVICE_READY')

    def setup_interfaces(self, device):
        self._controller.event_done('DEVICE_READY')
        _ifaces_plugged_in = self.lifecycle_driver.plug_interfacess()
        if _ifaces_plugged_in:
            self._increment_device_interface_count(device)
            interfaces_params = (
                    self.lifecycle_driver.get_setup_interface_params(device))
            self.configurator_rpc.setup_interface(interfaces_params)
        else:
            ev = self._controller.event(id='DEVICE_CONFIGURATION_FAILED',
                                        data=device)
            self._controller.rpc_event(ev, device['id'])
            self._log_event_created('DEVICE_CONFIGURATION_FAILED', device)

    def setup_device_routes(self, device):
        self._controller.event_done('DEVICE_INTERFACES_SETUP')
        self._update_network_service_device_db(device['id'],
                                               'INTERFACES_SETUP')
        routes_params = self.lifecycle_driver.get_create_route_params(device)
        self.configurator_rpc.setup_device_routes(routes_params)

    def create_device_configuration(self, device):
        self._controller.event_done('DEVICE_ROUTES_CONFIGURED')
        config_params = self.lifecycle_driver.get_create_config_params(device)
        self.configurator_rpc.create_device_config(config_params)

    def device_configuration_complete(self, device):
        self._controller.event_done('DEVICE_CONFIGURATION_COMPLETE')
        # Change status to active in DB and generate an event DEVICE_ACTIVE
        # to inform Service LCM
        self._increment_device_ref_count(device)
        self._update_network_service_device_db(device['id'], 'ACTIVE')
        LOG.info(_("Device Configuration completed for device: %(device_id)s"
                    "Updated DB status to ACTIVE, Incremented device "
                    "reference count for %s(device)s"),
                  {'device_id': device['id'], 'device': device})

        # DEVICE_ACTIVE event for Service LCM.
        ev = self._controller.event(id='DEVICE_ACTIVE', data=device)
        self._controller.rpc_event(ev, device['id'])
        self._log_event_created('DEVICE_ACTIVE', device)


    # Delete path
    def delete_network_service_device(self, data):
        # Invoke driver deletes, driver informs if ref count is to be
        # decremented or entry deleted from DB. We do the DB handling here
        # accordingly. Then generate an event to Service LCM to inform about
        # the status
        LOG.info(_("Received delete network service device request for device"
                   "%(device)s"), {'device': data})
        #self.delete_device_routes(device)
        ev = self._controller.event(id='DELETE_ROUTES',
                                        data=data)
        self._controller.rpc_event(ev, self.id)
        self._log_event_created('DELETE_ROUTES', data)

    def delete_device_routes(self, device):
        self._controller.event_done('DELETE_ROUTES')
        routes_params = self.lifecycle_driver.get_delete_route_params(device)
        self.configurator_rpc.delete_device_routes(routes_params)

    def clear_interfaces(self, device):
        self._controller.event_done('DELETE_INTERFACES')

        is_interface_unplugged = self.lifecycle_driver.unplug_interfaces()
        if is_interface_unplugged:
            self._decrement_device_interface_count(device)
        else:
            # handle unplug error
            pass
        interface_params = self.lifecycle_driver.get_delete_interface_params(device)
        self.configurator_rpc.clear_interfaces(interface_params)

        self.lifecycle_driver.unplug_interfaces()

    def delete_device_configuration(self, device):
        self._controller.event_done('DELETE_CONFIGURATION')
        # Delete any additional config remains to delete here.
        #_is_config_deleted = self.lifecycle_driver.delete_configuration()
        config_params = self.lifecycle_driver.get_delete_config_params(device)
        self.configurator_rpc.delete_device_config(config_params)

    def device_delete(self, device):
        self._controller.event_done('DELETE_CONFIGURATION_COMPLETED')
        # Update status in DB, send DEVICE_DELETED event to service LCM.

        self._decrement_device_ref_count(device)
        device_ref_count = device['reference_count']
        if device_ref_count == 0:
            self.lifecycle_driver.delete_device(device)
            self._delete_network_service_device_db(device['id'],
                                                   'PENDING_DELETE')
        else:
            #self._decrement_device_ref_count(device)
            desc = 'Network Service Device can be reuse'
            self._update_network_service_device_db(device,
                                                   device['status'],
                                                   desc)
        # DEVICE_DELETED event for Service LCM
        ev = self._controller.event(id='DEVICE_DELETED', data=device)
        self._controller.rpc_event(ev, device['id'])
        self._log_event_created('DEVICE_DELETED', device)


    # Error Handling
    def handle_device_error(self, device):
        status = 'ERROR'
        desc = 'Internal Server Error'
        self._update_network_service_device_db(device['id'], status, desc)
        ev = self._controller.event(id='DEVICE_CREATE_FAILED', data=device)
        self._controller.rpc_event(ev, device['id'])
        self._log_event_created('DEVICE_CREATE_FAILED', device)

    def handle_device_create_failed(self, device):
        status = device['status']
        desc = device['status_description']
        self._update_network_service_device_db(device['id'], status, desc)
        # is event is DEVICE_CREATE_FAILED or device_error
        ev = self._controller.event(id='DEVICE_CREATE_FAILED', data=device)
        self._controller.rpc_event(ev, device['id'])
        self._log_event_created('DEVICE_CREATE_FAILED', device)



    def handle_device_not_up(self, device):
        self._controller.event_done('DELETE_NOT_UP')
        status = 'ERROR'
        desc = 'Device not became ACTIVE'
        self._update_network_service_device_db(device['id'], status, desc)
        ev = self._controller.event(id='DEVICE_CREATE_FAILED', data=device)
        self._controller.rpc_event(ev, device['id'])
        self._log_event_created('DEVICE_CREATE_FAILED', device)

    def handle_device_not_reachable(self, device):
        self._controller.event_done('DEVICE_NOT_REACHABLE')
        status = 'ERROR'
        desc = 'Device not reachable, Health Check Failed'
        self._update_network_service_device_db(device['id'], status, desc)
        ev = self._controller.event(id='DEVICE_CREATE_FAILED', data=device)
        self._controller.rpc_event(ev, device['id'])
        self._log_event_created('DEVICE_CREATE_FAILED', device)

    def handle_device_config_failed(self, device):
        self._controller.event_done('DEVICE_CONFIGURATION_FAILED')
        # change device status to error only in case of health check fail
        #status = 'ERROR'
        status = device['status']
        desc = 'Configuring Device Failed.'
        self._update_network_service_device_db(device['id'], status, desc)
        ev = self._controller.event(id='DEVICE_CREATE_FAILED', data=device)
        self._controller.rpc_event(ev, device['id'])
        LOG.debug(_("Device create failed for device: %(device_id)s, "
                    "data = %(device_data)s"),
                  {'device_id': device['id'], 'device_data': device})

    def handle_interfaces_setup_failed(self, device):
        self._controller.event_done('DEVICE_INTERFACES_SETUP_FAILED')
        status = device['status']
        desc = 'Interfaces configuration failed'
        self._update_network_service_device_db(device['id'], status, desc)
        ev = self._controller.event(id='DEVICE_CREATE_FAILED', data=device)
        self._controller.rpc_event(ev, device['id'])
        self._log_event_created('DEVICE_CREATE_FAILED', device)
        LOG.debug(_("Interfaces configuration failed for device: %(device_id)s,"
                    "with config: %(routes_config)s"),
                  {'device_id': device['id'], 'routes_config': device})

    def handle_routes_config_failed(self, device):
        self._controller.event_done('DEVICE_ROUTES_CONFIGURE_FAILED')
        status = device['status']
        desc = 'Routes configuration Failed'
        self._update_network_service_device_db(device['id'], status, desc)
        ev = self._controller.event(id='DEVICE_CREATE_FAILED', data=device)
        self._controller.rpc_event(ev, device['id'])
        self._log_event_created('DEVICE_CREATE_FAILED', device)
        LOG.debug(_("Routes configuration failed for device: %(device_id)s,"
                    "with config: %(routes_config)s"),
                  {'device_id': device['id'], 'routes_config': device})


class DLCMConfiguratorRpcApi(object):
    """Service Manager side of the Service Manager to Service agent RPC API"""
    API_VERSION = '1.0'
    topic = 'dlcm-configurator-rpc-api'
    target = messaging.Target(topic=topic, version=API_VERSION)

    def __init__(self, context, host):
        super(DLCMConfiguratorRpcApi, self).__init__(self.API_VERSION)

        self.client = n_rpc.get_client(self.target)
        self.rpc_api = self.client.prepare(version=self.API_VERSION,
                                           topic=self.topic)

    def monitor_device_health(self, hm_req_params):
        return self.rpc_api.cast(
                self.context,
                'monitor_device_health',
                hm_req_params=hm_req_params
                )

    def license_device(self, device):
        return self.rpc_api.cast(
                self.context,
                'license_device',
                device=device
                )

    def setup_interface(self, interface_params):
        return self.rpc_api.cast(
                self.context,
                'setup_interface',
                interface_params=interface_params
                )

    def setup_device_routes(self, route_params):
        return self.rpc_api.cast(
                self.context,
                'setup_device_routes',
                              route_params=route_params
                )

    def create_device_config(self, config_params):
        return self.rpc_api.cast(
                self.context,
                'setup_device_config',
                              config_params=config_params
                )

    def delete_device_routes(self, route_params):
        return self.rpc_api.cast(
                self.context,
                'delete_device_routes',
                              route_params=route_params
                )

    def clear_interfaces(self, interface_params):
        return self.rpc_api.cast(
                self.context,
                'clear_interfaces',
                              interface_params=interface_params
                )

    def delete_device_config(self, config_params):
        return self.rpc_api.cast(
                self.context,
                'delete_device_config',
                              config_params=config_params
                )
