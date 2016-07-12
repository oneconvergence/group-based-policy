
from neutron._i18n import _LE
from neutron._i18n import _LI
import oslo_messaging as messaging

from gbpservice.nfp.common import constants as nfp_constants
from gbpservice.nfp.common import topics as nsf_topics
from gbpservice.nfp.core import event as nfp_event
from gbpservice.nfp.core.event import Event
from gbpservice.nfp.core import module as nfp_api
from gbpservice.nfp.core.rpc import RpcAgent
from gbpservice.nfp.lib import transport
from gbpservice.nfp.orchestrator.db import nfp_db_NSD as nfp_db
from gbpservice.nfp.orchestrator.drivers import orchestration_driver_NSD as orchestration_driver
from gbpservice.nfp.orchestrator.modules.device_orchestrator import (
        DeviceOrchestrator, events_init, rpc_init)
from gbpservice.nfp.orchestrator.openstack import openstack_driver
from neutron.common import rpc as n_rpc
from neutron import context as n_context
from neutron.db import api as db_api

import sys
import traceback

from gbpservice.nfp.core import log as nfp_logging
LOG = nfp_logging.getLogger(__name__)

STOP_POLLING = {'poll': False}
CONTINUE_POLLING = {'poll': True}



def nfp_module_init(controller, config):
    events_init(controller, config, DeviceOrchestratorNSD(controller, config))
    rpc_init(controller, config)
    LOG.debug("Device Orchestrator: module_init")



class DeviceOrchestratorNSD(DeviceOrchestrator):

    def __init__(self, controller, config):
        super(DeviceOrchestratorNSD, self).__init__(controller, config)
        self.nsf_db = nfp_db.NFPDbBaseNSD()
        self.orchestration_driver = (
                orchestration_driver.OrchestrationDriverNSD(self.config))


    def _create_advance_sharing_interfaces(self, device, interfaces_infos):
        nfd_interfaces = []
        port_infos = []
        for position, interface in enumerate(interfaces_infos):
            interface['network_function_device_id'] = device['id']
            interface['interface_position'] = position
            interface['tenant_id'] = device['tenant_id']
            interface['plugged_in_port_id'] = {}
            interface['plugged_in_port_id']['id'] = interface['id']
            interface['plugged_in_port_id']['port_model'] = (
                interface.get('port_model'))
            interface['plugged_in_port_id']['port_classification'] = (
                interface.get('port_classification'))
            interface['plugged_in_port_id']['port_role'] = (
                interface.get('port_role'))

            nfd_interfaces.append(
                self.nsf_db.create_network_function_device_interface(
                    self.db_session, interface)
            )
            LOG.debug("Created following entries in port_infos table : %s, "
                      " network function device interfaces table: %s." %
                      (port_infos, nfd_interfaces))

    def _get_advance_sharing_interfaces(self, device_id):
        filters = {'network_function_device_id': [device_id]}
        network_function_device_interfaces = (
            self.nsf_db.get_network_function_device_interfaces(
                self.db_session,
                filters=filters)
        )
        return network_function_device_interfaces

    def _update_advance_sharing_interfaces(self, device, nfd_ifaces):
        for nfd_iface in nfd_ifaces:
            for port in device['ports']:
                if port['id'] == nfd_iface['mapped_real_port_id']:
                    nfd_iface['mapped_real_port_id'] = port['id']
                    nfd_iface['plugged_in_port_id'] = (
                        self.nsf_db.get_port_info(
                            self.db_session,
                            nfd_iface['plugged_in_port_id']))
                    self.nsf_db.update_network_function_device_interface(
                        self.db_session,
                        nfd_iface['id'],
                        nfd_iface)
                    break

    def _delete_advance_sharing_interfaces(self, nfd_ifaces):
        for nfd_iface in nfd_ifaces:
            port_id = nfd_iface['id']
            self.nsf_db.delete_network_function_device_interface(
                self.db_session,
                port_id)

    def _create_network_function_device_db(self, device_info, state):
        advance_sharing_interfaces = []

        self._update_device_status(device_info, state)
        # (ashu) driver should return device_id as vm_id
        device_id = device_info.pop('id')
        device_info['id'] = device_id
        device_info['reference_count'] = 0
        if device_info.get('advance_sharing_interfaces'):
            advance_sharing_interfaces = (
                device_info.pop('advance_sharing_interfaces'))
        device_info['interfaces_in_use'] = 0
        device = self.nsf_db.create_network_function_device(self.db_session,
                                                            device_info)
        if advance_sharing_interfaces:
            self._create_advance_sharing_interfaces(device,
                                                    advance_sharing_interfaces)
        return device

    def _delete_network_function_device_db(self, device_id, device):
        advance_sharing_interfaces = device.get(
            'advance_sharing_interfaces', [])
        if advance_sharing_interfaces:
            self._delete_advance_sharing_interfaces(
                advance_sharing_interfaces)
        self.nsf_db.delete_network_function_device(self.db_session, device_id)


    def _prepare_device_data(self, device_info):
        network_function_id = device_info['network_function_id']
        network_function_device_id = device_info['network_function_device_id']
        network_function_instance_id = (
            device_info['network_function_instance_id'])

        network_function = self._get_nsf_db_resource(
            'network_function',
            network_function_id)
        network_function_device = self._get_nsf_db_resource(
            'network_function_device',
            network_function_device_id)
        network_function_instance = self._get_nsf_db_resource(
            'network_function_instance',
            network_function_instance_id)

        admin_token = self.keystoneclient.get_admin_token()
        service_profile = self.gbpclient.get_service_profile(
            admin_token, network_function['service_profile_id'])
        service_details = transport.parse_service_flavor_string(
            service_profile['service_flavor'])

        device_info.update({
            'network_function_instance': network_function_instance})
        device_info.update({'id': network_function_device_id})
        service_details.update({'service_type': self._get_service_type(
            network_function['service_profile_id'])})
        device_info.update({'service_details': service_details})

        device = self._get_device_data(device_info)
        device = self._update_device_data(device, network_function_device)

        mgmt_port_id = network_function_device.pop('mgmt_port_id')
        mgmt_port_id = self._get_port(mgmt_port_id)
        device['mgmt_port_id'] = mgmt_port_id
        device['network_function_id'] = network_function_id

        device['advance_sharing_interfaces'] = (
            self._get_advance_sharing_interfaces(device['id']))
        return device

    def _get_orchestration_driver(self, service_vendor):
        return self.orchestration_driver

    def plug_interfaces(self, event, is_event_call=True):
        if is_event_call:
            device_info = event.data
        else:
            device_info = event
        # Get event data, as configurator sends back only request_info, which
        # contains nf_id, nfi_id, nfd_id.
        device = self._prepare_device_data(device_info)
        self._update_network_function_device_db(device,
                                                'HEALTH_CHECK_COMPLETED')
        orchestration_driver = self._get_orchestration_driver(
            device['service_details']['service_vendor'])

        _ifaces_plugged_in, advance_sharing_ifaces = (
            orchestration_driver.plug_network_function_device_interfaces(
                device))
        if _ifaces_plugged_in:
            if advance_sharing_ifaces:
                self._update_advance_sharing_interfaces(
                    device,
                    advance_sharing_ifaces)
            self._increment_device_interface_count(device)
            self._create_event(event_id='CONFIGURE_DEVICE',
                               event_data=device,
                               is_internal_event=True)
        else:
            self._create_event(event_id='DEVICE_CONFIGURATION_FAILED',
                               event_data=device,
                               is_internal_event=True)


    def plug_interfaces_fast(self, event):

        # In this case, the event will be
        # happening in paralell with HEALTHMONITORIN,
        # so, we should not generate CONFIGURE_DEVICE & should not update
        # DB with HEALTH_CHECK_COMPLETED.

        nfp_context = event.data

        service_details = nfp_context['service_details']
        network_function_device = nfp_context['network_function_device']
        token = nfp_context['resource_owner_context']['admin_token']
        tenant_id = nfp_context['resource_owner_context']['admin_tenant_id']

        consumer = nfp_context['consumer']
        provider = nfp_context['provider']

        orchestration_driver = self._get_orchestration_driver(
            service_details['service_vendor'])

        ports = self._make_ports_dict(consumer, provider, 'port')

        device = {
            'id': network_function_device['id'],
            'ports': ports,
            'service_details': service_details,
            'token': token,
            'tenant_id': tenant_id,
            'interfaces_in_use': network_function_device['interfaces_in_use'],
            'status': network_function_device['status'],
            'vendor_data': nfp_context['vendor_data']}

        _ifaces_plugged_in, advance_sharing_ifaces = (
            orchestration_driver.plug_network_function_device_interfaces(
                device))
        if _ifaces_plugged_in:
            if advance_sharing_ifaces:
                self._update_advance_sharing_interfaces(
                    device,
                    advance_sharing_ifaces)
            self._increment_device_interface_count(device)
            # REVISIT(mak) - Check how incremented ref count can be updated in
            # DB
            self._controller.event_complete(event, result="SUCCESS")
        else:
            self._create_event(event_id="PLUG_INTERFACE_FAILED",
                               event_data=nfp_context,
                               is_internal_event=True)
            self._controller.event_complete(event, result="FAILED")


    def unplug_interfaces(self, event):
        device_info = event.data
        device = self._prepare_device_data(device_info)
        orchestration_driver = self._get_orchestration_driver(
            device['service_details']['service_vendor'])

        is_interface_unplugged, advance_sharing_ifaces = (
            orchestration_driver.unplug_network_function_device_interfaces(
                device))
        if is_interface_unplugged:
            if advance_sharing_ifaces:
                self._update_advance_sharing_interfaces(
                    device,
                    advance_sharing_ifaces)
            mgmt_port_id = device['mgmt_port_id']
            self._decrement_device_interface_count(device)
            device['mgmt_port_id'] = mgmt_port_id
        else:
            # Ignore unplug error
            pass
        self._create_event(event_id='DELETE_DEVICE',
                           event_data=device,
                           is_internal_event=True)

    def delete_device(self, event):
        # Update status in DB, send DEVICE_DELETED event to NSO.
        device = event.data
        orchestration_driver = self._get_orchestration_driver(
            device['service_details']['service_vendor'])

        self._decrement_device_ref_count(device)
        device_ref_count = device['reference_count']
        if device_ref_count <= 0:
            orchestration_driver.delete_network_function_device(device)
            self._create_event(event_id='DEVICE_BEING_DELETED',
                               event_data=device,
                               is_poll_event=True,
                               original_event=event)
        else:
            desc = 'Network Service Device can be reuse'
            self._update_network_function_device_db(device,
                                                    device['status'],
                                                    desc)
            # DEVICE_DELETED event for NSO
            self._create_event(event_id='DEVICE_DELETED',
                               event_data=device)

