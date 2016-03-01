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
import oslo_messaging as messaging

from gbpservice.nfp.core.main import Event
from gbpservice.nfp.core.rpc import RpcAgent
from gbpservice.nfp.common import topics as nsf_topics
from gbpservice.nfp.db import nfp_db as nfp_db
from gbpservice.nfp.db import api as nfp_db_api
from gbpservice.nfp.lib import extension_manager as ext_mgr
from gbpservice.nfp.lifecycle_manager.openstack import openstack_driver
#from gbpservice.nfp.lifecycle_manager.compute.drivers import (
#    nova_driver)
'''from gbpservice.nfp.lifecycle_manager.drivers import (
    haproxy_lifecycle_driver)
from gbpservice.nfp.lifecycle_manager.drivers import (
    vyos_lifecycle_driver)
'''
from neutron.common import rpc as n_rpc
from neutron import context as n_context

LOG = logging.getLogger(__name__)


def rpc_init(controller, config):
    rpcmgr = RpcHandler(config, controller)
    agent = RpcAgent(
        controller,
        host=config.host,
        topic=nsf_topics.NFP_CONFIGURATOR_DLCM_TOPIC,
        manager=rpcmgr)
    controller.register_rpc_agents([agent])


def events_init(controller, config):
    device_lifecycle_mgr_obj = DeviceLifeCycleManager(controller, config)
    evs = [
        Event(id='CREATE_NETWORK_FUNCTION_DEVICE',
              handler=device_lifecycle_mgr_obj),
        Event(id='DEVICE_SPAWNING', handler=device_lifecycle_mgr_obj),
        Event(id='DEVICE_UP', handler=device_lifecycle_mgr_obj),
        Event(id='DEVICE_HEALTHY', handler=device_lifecycle_mgr_obj),
        Event(id='CONFIGURE_DEVICE', handler=device_lifecycle_mgr_obj),
        Event(id='DEVICE_CONFIGURED', handler=device_lifecycle_mgr_obj),

        Event(id='DELETE_NETWORK_FUNCTION_DEVICE',
              handler=device_lifecycle_mgr_obj),
        Event(id='DELETE_CONFIGURATION', handler=device_lifecycle_mgr_obj),
        Event(id='DELETE_CONFIGURATION_COMPLETED',
              handler=device_lifecycle_mgr_obj),
        Event(id='DELETE_DEVICE', handler=device_lifecycle_mgr_obj),

        Event(id='DEVICE_NOT_UP', handler=device_lifecycle_mgr_obj),
        Event(id='DEVICE_NOT_REACHABLE', handler=device_lifecycle_mgr_obj),
        Event(id='DEVICE_CONFIGURATION_FAILED',
              handler=device_lifecycle_mgr_obj),
        Event(id='DEVICE_ERROR', handler=device_lifecycle_mgr_obj),
        ]
    controller.register_events(evs)


def module_init(controller, config):
    events_init(controller, config)
    rpc_init(controller, config)
    LOG.info(_("DLCM: module_init"))


class RpcHandler(object):
    RPC_API_VERSION = '1.0'

    def __init__(self, conf, controller):
        super(RpcHandler, self).__init__()
        self.conf = conf
        self._controller = controller
        self.rpc_event_mapping = {'healthmonitor': ['DEVICE_HEALTHY',
                                                   'DEVICE_NOT_REACHABLE'],
                                  'interfaces':    ['DEVICE_CONFIGURED',
                                                   'DEVICE_CONFIGURED_FAILED'],
                                  'routes':        ['DEVICE_CONFIGURED',
                                                   'DEVICE_CONFIGURED_FAILED'],
                                  }

    # RPC APIs status notification from Configurator
    def network_function_device_notification(self, context, notification_data):
        #context = kwargs.get('context')
        #notification_data = kwargs.get('notification_data')
        responses = notification_data.get('kwargs')

        for response in responses:
            resource = response.get('resource')
            request_info = response.get('request_info')
            result = response.get('result')

            if resource == 'healthmonitor':
                LOG.info(_("healthmonitor not implemented yet, so ignoring for now."))
                return None

            event_id = self.rpc_event_mapping[resource][0]
            if result != 'success':
                event_id = self.rpc_event_mapping[resource][1]
                break

        event_data = request_info
        self._create_event(event_id=event_id,
                           event_data=event_data)


class DeviceLifeCycleManager(object):
    def __init__(self, controller, config):
        self._controller = controller
        self.config = config

    def event_method_mapping(self, state, device_lifecycle_handler):
        state_machine = {
            "CREATE_NETWORK_FUNCTION_DEVICE": (
                device_lifecycle_handler.create_network_function_device),
            "DEVICE_SPAWNING": device_lifecycle_handler.check_device_is_up,
            #"DEVICE_UP": device_lifecycle_handler.perform_health_check,
            #"DEVICE_HEALTHY": (
            #            device_lifecycle_handler.plug_interfaces),
            "DEVICE_UP": device_lifecycle_handler.plug_interfaces,
            "CONFIGURE_DEVICE": (
                        device_lifecycle_handler.create_device_configuration),
            "DEVICE_CONFIGURED": (
                device_lifecycle_handler.device_configuration_complete),

            "DELETE_NETWORK_FUNCTION_DEVICE": (
                device_lifecycle_handler.delete_network_function_device),
            "DELETE_CONFIGURATION": (
                device_lifecycle_handler.delete_device_configuration),
            "DELETE_CONFIGURATION_COMPLETED": (
                device_lifecycle_handler.unplug_interfaces),
            #"DELETE_HEALTH_MONITOR": (
            #    device_lifecycle_handler.delete_device_health_monitor),
            #"HEALTH_MONITOR_DELETED": (
            #    device_lifecycle_handler.delete_device), # should we wait for
                                                # this, or simply delete device
            "DELETE_DEVICE": device_lifecycle_handler.delete_device,
            "DEVICE_NOT_REACHABLE": (
                device_lifecycle_handler.handle_device_not_reachable),
            "DEVICE_CONFIGURATION_FAILED": (
                device_lifecycle_handler.handle_device_config_failed),
            "DEVICE_ERROR": device_lifecycle_handler.handle_device_error,
            "DEVICE_NOT_UP": device_lifecycle_handler.handle_device_not_up,
        }
        if state not in state_machine:
            raise Exception("Invalid state")
        else:
            return state_machine[state]

    def handle_event(self, ev):
        device_lifecycle_handler = DeviceLifeCycleHandler(self._controller,
                                                          self.config)
        self.event_method_mapping(ev.id, device_lifecycle_handler)(
            ev)

    def handle_poll_event(self, ev):
        LOG.info(_("DLCM: handle_poll_event: %s" % (ev.id)))
        device_lifecycle_handler = DeviceLifeCycleHandler(self._controller,
                                                         self.config)
        self.event_method_mapping(ev.id, device_lifecycle_handler)(
            ev)


class DeviceLifeCycleHandler(object):
    def __init__(self, controller, config, request=None,
                 state="INIT", _id=None):
        self.id = _id
        self._controller = controller
        self.config = config
        self.state = state
        self.request = request
        self.nsf_db = nfp_db.NFPDbBase()
        self.db_session = nfp_db_api.get_session()
        self.gbpclient = openstack_driver.GBPClient()
        self.keystoneclient = openstack_driver.KeystoneClient()

        #self.ext_mgr = ext_mgr.ExtensionManager(self._controller, self.config)
        #self.drivers = self.ext_mgr.drivers

        from gbpservice.nfp.lifecycle_manager.drivers import vyos_lifecycle_driver
        vyos_driver = vyos_lifecycle_driver.VyosLifeCycleDriver()

        self.drivers = {'vyos': vyos_driver}
        LOG.info(_("self.drivers = %s" % self.drivers))
        self.compute_driver = self._get_compute_driver(
            'compute')

        neutron_context = n_context.get_admin_context()
        self.configurator_rpc = DLCMConfiguratorRpcApi(neutron_context)

        self.state_map = {
                'INIT': 'Created Network Service Device with status INIT.',
                'PENDING_CREATE': '',
                'DEVICE_SPAWNING': 'Creating NSD, launched the new device, ' +
                                    'polling on its status',
                'DEVICE_UP': 'Device is UP/ACTIVE',
                'HEALTH_CHECK_PENDING': 'Device health check is going on ' +
                                        ' through configurator',
                'HEALTH_CHECK_COMPLETED': 'Health check succesfull for device',
                'INTERFACES_PLUGGED': 'Interfaces Plugging successfull',
                'PENDING_CONFIGURATION_CREATE': 'Started configuring device ' +
                                                'for routes, license, etc',
                'DEVICE_READY': 'Device is ready to use',
                'ACTIVE': 'Device is Active.',
                'DEVICE_NOT_UP': 'Device not became UP/ACTIVE',
        }

    # Helper functions
    def _log_event_created(self, event_id, event_data):
        LOG.info(_("Created event %s(event_name)s with event "
                    "data: %(event_data)s"),
                  {'event_name': event_id, 'event_data': event_data})

    def _create_event(self, event_id, event_data=None,
                      is_poll_event=False, original_event=False):
        if is_poll_event:
            ev = self._controller.new_event(
                id=event_id, data=event_data,
                serialize=original_event.serialize,
                binding_key=original_event.binding_key,
                key=original_event.key)
            LOG.debug(_("_create_event - poll event %s" % ev.id))
            self._controller.poll_event(ev, max_times=10)
        else:
            ev = self._controller.new_event(id=event_id, data=event_data)
            self._controller.post_event(ev)
        self._log_event_created(event_id, event_data)

    def _update_device_status(self, device, state, status_desc=None):
        device['status'] = state
        if status_desc:
            device['status_description'] = status_desc
        else:
            device['status_description'] = self.state_map[state]

    def _get_ports(self, port_ids):
        data_ports = []
        for port_id in port_ids:
            port_info = self.nsf_db.get_port_info(self.db_session, port_id)
            data_ports.append(port_info)
        return data_ports

    def _create_network_function_device_db(self, device_info, state):
        self._update_device_status(device_info, state)
        #(ashu) driver should return device_id as vm_id
        device_id = device_info.pop('id')
        device_info['id'] = device_id
        device_info['reference_count'] = 0
        #(ashu) driver is sending that info
        #device_info['interfaces_in_use'] = 0
        #device_info['mgmt_data_ports']['id'] = device_id
        device = self.nsf_db.create_network_function_device(self.db_session,
                                                            device_info)
        # Fix me : handle device create failed, driver returns None
        mgmt_port_ids = device.pop('mgmt_data_ports')
        mgmt_data_ports = self._get_ports(mgmt_port_ids)
        device['mgmt_data_ports'] = mgmt_data_ports
        return device

    def _update_network_function_device_db(self, device, state,
                                           status_desc=''):
        self._update_device_status(device, state, status_desc)
        self.nsf_db.update_network_function_device(self.db_session,
                                                   device['id'], device)

    def _delete_network_function_device_db(self, device_id):
        self.nsf_db.delete_network_function_device(self.db_session, device_id)

    def _get_network_function_devices(self, filters=None):
        network_function_devices = self.nsf_db.get_network_function_devices(
                                                self.db_session, filters)
        for device in network_function_devices:
            mgmt_port_ids = device.pop('mgmt_data_ports')
            mgmt_data_ports = self._get_ports(mgmt_port_ids)
            device['mgmt_data_ports'] = mgmt_data_ports
        return network_function_devices

    def _increment_device_ref_count(self, device):
        device['reference_count'] += 1

    def _decrement_device_ref_count(self, device):
        device['reference_count'] -= 1
        #self._update_network_function_device_db(device,
        #                                       device['status'],
        #                                       device['status_description'])

    def _increment_device_interface_count(self, device):
        device['interfaces_in_use'] += len(device['ports'])
        self._update_network_function_device_db(device, device['status'])

    def _decrement_device_interface_count(self, device):
        device['interfaces_in_use'] -= len(device['ports'])
        self._update_network_function_device_db(device, device['status'])

    def _get_vendor_lifecycle_driver(self, vendor_name):
        # Replace with an autoload and auto choose mechanism
        # Each driver either registers the service type and vendor it supports
        # or there is an interface in driver to get that information
        #vendor_name = data['service_vendor']
        return self.drivers[vendor_name.lower()]
 
    def _get_compute_driver(self, drvr_name):
        # Replace with an autoload and auto choose mechanism
        # Each driver either registers the service type and vendor it supports
        # or there is an interface in driver to get that information
        vendor_name = 'compute'
        if vendor_name == "compute":
            pass
            #return nova_driver.NovaAPIDriver()
        else:
            raise Exception()   # Raise a proper exception class

    def _get_lifecycle_driver(self, service_vendor):
        return self.drivers[service_vendor.lower()]

    def _get_device_to_reuse(self, device_data, dev_sharing_info):
        device_filters = dev_sharing_info['filters']
        lifecycle_driver = self._get_lifecycle_driver(
                                        device_data['service_vendor'])

        # TODO (ashu) should DLCM return whole dict, or selective fields.
        devices = self._get_network_function_devices(device_filters)

        device = lifecycle_driver.select_network_function_device(devices,
                                                                 device_data)
        return device

    def _get_device_data(self, nfd_request):
        device_data = {}
        network_function = nfd_request.get('network_function')
        network_function_instance = nfd_request['network_function_instance']
        service_type = nfd_request.get('service_type')
        service_vendor = nfd_request.get('service_vendor')
        device_data['share_existing_device'] = (
                                    nfd_request.get('share_existing_device'))
        device_data['management_network_info'] = (
                                    nfd_request.get('management_network_info'))

        if network_function:
            device_data['network_function_id'] = network_function['id']
            device_data['service_chain_id'] = network_function['service_chain_id']

        device_data['network_function_instance_id'] = (
                                    network_function_instance['id'])
        device_data['tenant_id'] = network_function_instance['tenant_id']

        nsi_port_info = []
        for port_id in network_function_instance.pop('port_info'):
            port_info = self.nsf_db.get_port_info(self.db_session, port_id)
            nsi_port_info.append(port_info)

        device_data['ports'] = nsi_port_info

        if service_vendor:
            device_data['service_vendor'] = service_vendor
        if service_type:
            device_data['service_type'] = service_type
        # TODO: Get these values from SLCM, it should be available in service
        # profile.
        device_data['compute_policy'] = 'nova'
        # To get the network mode, fetch it from port_info
        device_data['network_policy'] = nsi_port_info[0]['port_policy'].lower()

        return device_data

    def _get_nsf_db_resource(self, resource_name, resource_id):
        db_method = getattr(self.nsf_db, 'get_' + resource_name)
        return db_method(self.db_session, resource_id)

    def _update_device_data(self, device, device_data):
        device.update(device_data)
        return device

    # Create path
    def create_network_function_device(self, event):
        """ Returns device instance for a new service

        This method either returns existing device which could be reused for a
        new service or it creates new device instance
        """
        nfd_request = event.data
        device = None

        LOG.info(_("Received create network service device request with data"
                   "%(data)s"), {'data': nfd_request})

        device_data = self._get_device_data(nfd_request)
        lifecycle_driver = self._get_lifecycle_driver(
                                    device_data['service_vendor'])
        dev_sharing_info = (
            lifecycle_driver.get_network_function_device_sharing_info(
                device_data))
        if dev_sharing_info:
            device = self._get_device_to_reuse(device_data, dev_sharing_info)
            if device:
                device = self._update_device_data(device, device_data)

        # To handle case, when device sharing is supported but device not
        # exists to share, so create a new device.
        if dev_sharing_info and device:
            # Device is already active, no need to change status
            self._create_event(event_id='DEVICE_HEALTHY',
                               event_data=device)
            LOG.info(_("Sharing existing device: %s(device)s for reuse"),
                     {'device': device})
        else:
            LOG.info(_("No Device exists for sharing, Creating new device,"
                       "device request: %(device)s"), {'device': nfd_request})
            driver_device_info = (
                lifecycle_driver.create_network_function_device(device_data))
            if not driver_device_info:
                LOG.info(_("Device creation failed"))
                self._create_event(event_id='DEVICE_ERROR',
                                   event_data=nfd_request)
                return

            # Update newly created device with required params
            device = self._update_device_data(driver_device_info, device_data)
            device['network_function_device_id'] = device['id']
            #device = self._update_device_data(device, device_data)

            self._create_network_function_device_db(device,
                                                   'DEVICE_SPAWNING')
            # TODO (ashu) - create an event to SLCM, to give device_id
            #self._create_event(event_id='DEVICE_CREATED',
            #                   event_data=device)

            self._create_event(event_id='DEVICE_SPAWNING',
                               event_data=device)
                               #is_poll_event=True,
                               #original_event=event,
                               #)

    def check_device_is_up(self, event):
        device = event.data
        print 'sleeping for 15 secs'
        import time;time.sleep(15)
        lifecycle_driver = self._get_lifecycle_driver(device['service_vendor'])
        # TODO (ashu) return value from driver, this should be true/false
        is_device_up = (
            lifecycle_driver.get_network_function_device_status(device))
        if is_device_up == 'ACTIVE':
            #self._controller.poll_event_done(event)

            # create event DEVICE_UP
            self._create_event(event_id='DEVICE_UP',
                               event_data=device)
            self._update_network_function_device_db(device,
                                                   'DEVICE_UP')
        elif is_device_up == 'ERROR':
            #self._controller.poll_event_done(event)
            # create event DEVICE_NOT_UP

            self._create_event(event_id='DEVICE_NOT_UP',
                               event_data=device)
            self._update_network_function_device_db(device,
                                                   'DEVICE_NOT_UP')

    def perform_health_check(self, event):
        # The driver tells which protocol / port to monitor ??
        device = event.data
        lifecycle_driver = self._get_lifecycle_driver(device['service_vendor'])
        hm_req = (
            lifecycle_driver.get_network_function_device_healthcheck_info(
                                                                device))
        self.configurator_rpc.create_network_function_device_config(device,
                                                                    hm_req)
        LOG.debug(_("Health Check RPC sent to configurator for device: "
                    "%(device_id)s with health check parameters: %(hm_req)s"),
                  {'device_id': device['id'], 'hm_req': hm_req})
        self._update_network_function_device_db(device,
                                               'HEALTH_CHECK_PENDING')

    def _get_service_vendor(self, service_profile_id):
        admin_token = self.keystoneclient.get_admin_token()
        service_profile = self.gbpclient.get_service_profile(
            admin_token, service_profile_id)
        return service_profile['service_flavor']      # service_flovor
        
    def _prepare_device_data(self, device_info):
        network_function_id = device_info['network_function_id']
        network_function_device_id = device_info['network_function_device_id']
        #network_function_device_id = device_info['id']
        network_function_instance_id = (
                                device_info['network_function_instance_id'])
        #service_vendor = device_info['service_vendor']

        network_function = self._get_nsf_db_resource(
                                'network_function',
                                network_function_id)
        network_function_device = self._get_nsf_db_resource(
                                'network_function_device',
                                network_function_device_id)
        network_function_instance = self._get_nsf_db_resource(
                                'network_function_instance',
                                network_function_instance_id)

        # either keep service vendor in request_info or get it from gbpclient
        service_vendor = self._get_service_vendor(
                                    network_function['service_profile_id'])

        device_info.update({
                    'network_function_instance': network_function_instance})
        device_info.update({'id': network_function_device_id})
        device_info.update({'service_vendor': service_vendor})

        device = self._get_device_data(device_info)
        device = self._update_device_data(device, network_function_device)

        mgmt_port_ids = network_function_device.pop('mgmt_data_ports')
        mgmt_data_ports = self._get_ports(mgmt_port_ids)
        device['mgmt_data_ports'] = mgmt_data_ports
        device['network_function_id'] = network_function_id
        return device

    def plug_interfaces(self, event):
        device_info = event.data
        # Get event data, as configurator sends back only request_info, which
        # contains nf_id, nfi_id, nfd_id.
        device = self._prepare_device_data(device_info)
        lifecycle_driver = self._get_lifecycle_driver(device['service_vendor'])
        _ifaces_plugged_in = (
            lifecycle_driver.plug_network_function_device_interfaces(device))
        if _ifaces_plugged_in:
            self._increment_device_interface_count(device)
            self._create_event(event_id='CONFIGURE_DEVICE',
                               event_data=device)
        else:
            self._create_event(event_id='DEVICE_CONFIGURATION_FAILED',
                               event_data=device)

    def create_device_configuration(self, event):
        device = event.data
        lifecycle_driver = self._get_lifecycle_driver(device['service_vendor'])
        config_params = (
            lifecycle_driver.get_network_function_device_config_info(device))
        self.configurator_rpc.create_network_function_device_config(
                                                    device, config_params)

    def device_configuration_complete(self, event):
        device_info = event.data
        device = self._prepare_device_data(device_info)
        # Change status to active in DB and generate an event DEVICE_ACTIVE
        # to inform Service LCM
        self._increment_device_ref_count(device)
        self._update_network_function_device_db(device, 'ACTIVE')
        LOG.info(_("Device Configuration completed for device: %(device_id)s"
                   "Updated DB status to ACTIVE, Incremented device "
                   "reference count for %(device)s"),
                 {'device_id': device['id'], 'device': device})

        device_created_data = {
                               'network_function_id': (
                                            device['network_function_id']),
                               'network_function_instance_id': (
                                    device['network_function_instance_id']),
                               'network_function_device_id': device['id']
        }
        # DEVICE_ACTIVE event for Service LCM.
        self._create_event(event_id='DEVICE_ACTIVE',
                           event_data=device_created_data)


    # Delete path
    def delete_network_function_device(self, event):
        delete_nfd_request = event.data
        network_function_instance = (
                            delete_nfd_request['network_function_instance'])
        nfd_id = delete_nfd_request['network_function_device_id']

        LOG.info(_("Received delete network service device request for device "
                   "%(device)s"), {'device': delete_nfd_request})
        device = self.nsf_db.get_network_function_device(self.db_session,
                                                         nfd_id)
        mgmt_port_ids = device.pop('mgmt_data_ports')
        mgmt_data_ports = self._get_ports(mgmt_port_ids)
        device['mgmt_data_ports'] = mgmt_data_ports
        device['compute_policy'] = 'nova'
        device['network_policy'] = mgmt_data_ports[0]['port_policy']
        device['network_function_instance_id'] = network_function_instance['id']
        #self._update_device_data(device, event.data)

        data_port_ids = network_function_instance.pop('port_info')
        data_ports = self._get_ports(data_port_ids)
        device['ports'] = data_ports

        self._create_event(event_id='DELETE_CONFIGURATION',
                           event_data=device)

    def delete_device_configuration(self, event):
        device = event.data
        lifecycle_driver = self._get_lifecycle_driver(device['service_vendor'])
        config_params = (
            lifecycle_driver.get_network_function_device_config_info(
                                                                device))
        self.configurator_rpc.delete_network_function_device_config(device,
                                                                    config_params)

    def unplug_interfaces(self, event):
        device_info = event.data
        device = self._prepare_device_data(device_info)
        lifecycle_driver = self._get_lifecycle_driver(device['service_vendor'])

        is_interface_unplugged = (
            lifecycle_driver.unplug_network_function_device_interfaces(device))
        if is_interface_unplugged:
            mgmt_data_ports = device['mgmt_data_ports']
            self._decrement_device_interface_count(device)
            device['mgmt_data_ports'] = mgmt_data_ports
        else:
            # Ignore unplug error
            pass
        self._create_event(event_id='DELETE_DEVICE',
                           event_data=device)

    def delete_device(self, event):
        # Update status in DB, send DEVICE_DELETED event to service LCM.
        device = event.data
        lifecycle_driver = self._get_lifecycle_driver(device['service_vendor'])

        self._decrement_device_ref_count(device)
        device_ref_count = device['reference_count']
        if device_ref_count == 0:
            #(TODO) (ashu) - delete health monitor
            lifecycle_driver.delete_network_function_device(device)
            self._delete_network_function_device_db(device['id'])
        else:
            desc = 'Network Service Device can be reuse'
            self._update_network_function_device_db(device,
                                                   device['status'],
                                                   desc)
        # DEVICE_DELETED event for Service LCM
        self._create_event(event_id='DEVICE_DELETED',
                           event_data=device)

    # Error Handling
    def handle_device_error(self, event):
        device = event.data
        status = 'ERROR'
        desc = 'Internal Server Error'
        self._update_network_function_device_db(device, status, desc)
        device['network_function_device_id'] = device['id']
        self._create_event(event_id='DEVICE_CREATE_FAILED',
                           event_data=device)

    def handle_device_create_failed(self, event):
        device = event.data
        status = device['status']
        desc = device['status_description']
        self._update_network_function_device_db(device, status, desc)
        device['network_function_device_id'] = device['id']
        # is event is DEVICE_CREATE_FAILED or device_error
        self._create_event(event_id='DEVICE_CREATE_FAILED',
                           event_data=device)

    def handle_device_not_up(self, event):
        device = event.data
        status = 'ERROR'
        desc = 'Device not became ACTIVE'
        self._update_network_function_device_db(device, status, desc)
        device['network_function_device_id'] = device['id']
        self._create_event(event_id='DEVICE_CREATE_FAILED',
                           event_data=device)

    def handle_device_not_reachable(self, event):
        device = event.data
        status = 'ERROR'
        desc = 'Device not reachable, Health Check Failed'
        self._update_network_function_device_db(device, status, desc)
        device['network_function_device_id'] = device['id']
        self._create_event(event_id='DEVICE_CREATE_FAILED',
                           event_data=device)

    def handle_device_config_failed(self, event):
        # change device status to error only in case of health check fail
        device = event.data
        status = device['status']
        desc = 'Configuring Device Failed.'
        self._update_network_function_device_db(device, status, desc)
        device['network_function_device_id'] = device['id']
        self._create_event(event_id='DEVICE_CREATE_FAILED',
                           event_data=device)
        LOG.debug(_("Device create failed for device: %(device_id)s, "
                    "data = %(device_data)s"),
                  {'device_id': device['id'], 'device_data': device})

    def handle_interfaces_setup_failed(self, event):
        device = event.data
        status = device['status']
        desc = 'Interfaces configuration failed'
        self._update_network_function_device_db(device, status, desc)
        device['network_function_device_id'] = device['id']
        self._create_event(event_id='DEVICE_CREATE_FAILED',
                           event_data=device)
        LOG.debug(_("Interface configuration failed for device: %(device_id)s,"
                    "with config: %(routes_config)s"),
                  {'device_id': device['id'], 'routes_config': device})

    def handle_routes_config_failed(self, event):
        device = event.data
        status = device['status']
        desc = 'Routes configuration Failed'
        self._update_network_function_device_db(device, status, desc)
        device['network_function_device_id'] = device['id']
        self._create_event(event_id='DEVICE_CREATE_FAILED',
                           event_data=device)
        LOG.debug(_("Routes configuration failed for device: %(device_id)s,"
                    "with config: %(routes_config)s"),
                  {'device_id': device['id'], 'routes_config': device})

    def handle_license_failed(self, event):
        device = event.data
        status = 'ERROR'
        desc = 'Licensing failed for device'
        self._update_network_function_device_db(device, status, desc)
        device['network_function_device_id'] = device['id']
        self._create_event(event_id='DEVICE_CREATE_FAILED',
                           event_data=device)


class DLCMConfiguratorRpcApi(object):
    """Service Manager side of the Service Manager to Service agent RPC API"""
    API_VERSION = '1.0'
    target = messaging.Target(version=API_VERSION)

    def __init__(self, context):
        super(DLCMConfiguratorRpcApi, self).__init__()

        self.context = context
        self.client = n_rpc.get_client(self.target)
        self.rpc_api = self.client.prepare(version=self.API_VERSION,
                                topic=nsf_topics.NFP_DLCM_CONFIGURATOR_TOPIC)

    def _get_request_info(self, device):
        request_info = {
                'network_function_id': device['network_function_id'],
                'network_function_instance_id': (
                                device['network_function_instance_id']),
                'network_function_device_id': device['id']
        }
        return request_info

    def _update_params(self, device_data, config_params):
        request_info = self._get_request_info(device_data)
        for config in config_params['config']:
            #config['kwargs'] = request_info
            config['kwargs']['request_info'] = request_info

    def create_network_function_device_config(self, device_data,
                                              config_params):
        self._update_params(device_data, config_params)
        LOG.info(_("create_network_function_device_config - config_params = %s" % config_params))
        return self.rpc_api.cast(
                    self.context,
                    'create_network_function_device_config',
                    request_data=config_params
                    )

    def delete_network_function_device_config(self, device_data,
                                              config_params):
        self._update_params(device_data, config_params)
        LOG.info(_("delete_network_function_device_config - config_params = %s" % config_params))
        return self.rpc_api.cast(
                    self.context,
                    'delete_network_function_device_config',
                    request_data=config_params
                    )
