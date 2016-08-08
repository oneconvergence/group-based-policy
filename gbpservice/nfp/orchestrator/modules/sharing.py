from neutron._i18n import _LE
from neutron._i18n import _LI
from gbpservice.nfp.core import event as nfp_event
from gbpservice.nfp.core.event import Event
from gbpservice.nfp.core import module as nfp_api

from gbpservice.nfp.orchestrator.modules import device_orchestrator
from gbpservice.nfp.common import constants as nfp_constants
from gbpservice.nfp.orchestrator.drivers import sharing_driver
from gbpservice.nfp.orchestrator.modules import service_orchestrator

from gbpservice.nfp.core import log as nfp_logging
LOG = nfp_logging.getLogger(__name__)


def events_init(controller, config, orchestrator):
    events = ['CREATE_NETWORK_FUNCTION_INSTANCE',
              'CREATE_NETWORK_FUNCTION_DEVICE',
              'UNPLUG_INTERFACES']
    events_to_register = []
    for event in events:
        events_to_register.append(
            Event(id=event, handler=orchestrator))

    controller.register_events(
        events_to_register, priority=1)


def nfp_module_init(controller, config):
    events_init(controller, config, Sharing(controller, config))
    LOG.debug("Service Sharing: module_init")


class Sharing(nfp_api.NfpEventHandler):

    def __init__(self, controller, config):
        self._controller = controller
        self.config = config
        self.device_orchestrator = device_orchestrator.DeviceOrchestrator(
            controller, config)
        self.service_orchestrator = service_orchestrator.ServiceOrchestrator(
            controller, config)
        self.sharing_driver = sharing_driver.SharingDriver(config)

    def handle_event(self, event):
        if event.id == "CREATE_NETWORK_FUNCTION_INSTANCE":
            self.create_network_function_instance(event)
        elif event.id == "CREATE_NETWORK_FUNCTION_DEVICE":
            self.create_network_function_device(event)
        elif event.id == "UNPLUG_INTERFACES":
            self.unplug_interfaces(event)
        else:
            LOG.error(_LE("Invalid event: %(event_id)s for "
                          "event data %(event_data)s"),
                      {'event_id': event.id, 'event_data': event.data})

    def _get_device_to_reuse(self, device_data):
        device_filters = {
            'tenant_id': [device_data['tenant_id']],
            'service_vendor': [device_data['service_details'][
                'service_vendor']],
            'status': [nfp_constants.ACTIVE]
        }
        devices = self.device_orchestrator._get_network_function_devices(
            device_filters)
        device = self.sharing_driver.select_network_function_device(
            devices, device_data)
        return device

    def _check_fw_vpn_sharing(self, nfp_context):
        service_details = nfp_context['service_details']
        if service_details['service_type'].lower() in [
                nfp_constants.FIREWALL, nfp_constants.VPN]:
            service_chain_specs = nfp_context['service_chain_specs']
            for spec in service_chain_specs:
                nodes = spec['sc_nodes']
                for node in nodes:
                    service_type = node['sc_service_profile']['service_type']
                    if service_type != service_details['service_type'] and (
                            service_type.lower() in [
                                nfp_constants.FIREWALL, nfp_constants.VPN]):
                        return True
        return False

    def create_network_function_instance(self, event):
        if self._check_fw_vpn_sharing(event.data):
            event.data['is_fw_vpn_sharing'] = True
            event.data['binding_key'] = (
                event.data['service_chain_instance']['id'])
        self._controller.post_event(event, target='service_orchestrator')

    def _prepare_device_data_from_nfp_context(self, nfp_context):
        device_data = (
            self.device_orchestrator._prepare_device_data_from_nfp_context(
                nfp_context))
        # Donot update the name of the device
        del device_data['name']
        return device_data

    def create_network_function_device(self, event):
        nfp_context = event.data
        LOG.info(_LI("Orchestrator's sharing module received "
                     " create network function "
                     "device request with data %(data)s"),
                 {'data': nfp_context})

        device_data = self._prepare_device_data_from_nfp_context(nfp_context)
        device = self._get_device_to_reuse(device_data)

        if device:
            device.update(device_data)
            # Existing device to be shared
            # Trigger an event for Service Orchestrator
            # from gbpservice.nfp.utils import forked_pdb
            # forked_pdb.ForkedPdb().set_trace()
            device['network_function_device_id'] = device['id']
            plug_interface = True
            if ('is_fw_vpn_sharing' in nfp_context
                    and nfp_context['is_fw_vpn_sharing']):
                nf_filters = {'service_chain_id': [
                    nfp_context['network_function']['service_chain_id']]}
                sibling_network_functions = (
                    self.service_orchestrator.db_handler.get_network_functions(
                        self.service_orchestrator.db_session, filters=nf_filters))
                for sibling_network_function in sibling_network_functions:
                    nfi_filters= {'network_function_id': [sibling_network_function['id']],
                                  'network_function_device_id': [device['network_function_device_id']]}
                    network_function_instances = (
                        self.service_orchestrator.db_handler.get_network_function_instances(
                            self.service_orchestrator.db_session, filters=nfi_filters))
                    if network_function_instances:
                        plug_interface = False
                        break
            # Create an event to NSO, to give device_id
            if not plug_interface:
                device['interfaces_in_use'] -= 2

            device_created_data = {
                'network_function_instance_id': (
                    nfp_context['network_function_instance']['id']),
                'network_function_device_id': device['id']
            }
            self.service_orchestrator._create_event(
                event_id='DEVICE_CREATED',
                event_data=device_created_data,
                is_internal_event=True)

            nfp_context['network_function_device'] = device
            nfp_context['vendor_data'] = device['vendor_data']
            management_info = self.sharing_driver.get_managment_info(device)
            management = nfp_context['management']
            management['port'] = management_info['neutron_port']
            management['port']['ip_address'] = management_info['ip_address']
            management['subnet'] = management_info['neutron_subnet']

            # Since the device is already UP, create a GRAPH so that
            # further processing continues in device orchestrator
            nf_id = nfp_context['network_function']['id']
            nfp_context['event_desc'] = event.desc.to_dict()
            du_event = self._controller.new_event(id="DEVICE_UP",
                                                  key=nf_id,
                                                  data=nfp_context,
                                                  graph=True)
            graph = nfp_event.EventGraph(du_event)
            graph_nodes = [du_event]
            if plug_interface:
                plug_int_event = self._controller.new_event(id="PLUG_INTERFACES",
                                                            key=nf_id,
                                                            data=nfp_context,
                                                            graph=True)

                graph.add_node(plug_int_event, du_event)
                graph_nodes.append(plug_int_event)

            graph_event = self._controller.new_event(id="DEVICE_SHARE_GRAPH",
                                                     graph=graph)
            self._controller.post_event_graph(graph_event, graph_nodes)
        else:
            # Device does not exist.
            # Post this event back to device orchestrator
            # It will handle as it was handling in non sharing case
            self._controller.post_event(event, target='device_orchestrator')

    def unplug_interfaces(self, event):
        device_data = event.data
        filters = {
            'network_function_device_id': [
                device_data['id']],
            'status': ['ACTIVE']
        }
        network_function_instances = (
            self.device_orchestrator.nsf_db.get_network_function_instances(
                self.device_orchestrator.db_session, filters=filters))

        if network_function_instances:
            service_details = device_data['service_details']
            unplug_interface = True
            if (service_details['service_type'].lower() in [
                    nfp_constants.FIREWALL, nfp_constants.VPN]):
                network_function = (
                    self.service_orchestrator.db_handler.get_network_function(
                        self.service_orchestrator.db_session,
                        device_data['network_function_id']))
                service_chain_id = network_function['service_chain_id']
                filters = {'service_chain_id': [service_chain_id],
                           'status': ['ACTIVE']}
                network_functions = (
                    self.service_orchestrator.db_handler.get_network_functions(
                        self.service_orchestrator.db_session, filters=filters))
                admin_token = self.device_orchestrator.keystoneclient.get_admin_token()
                for network_function in network_functions:
                    service_profile = (
                        self.device_orchestrator.gbpclient.get_service_profile(
                            admin_token, network_function['service_profile_id']))
                    if (service_profile['service_type'].lower() in [
                            nfp_constants.FIREWALL, nfp_constants.VPN] and
                                (not (service_profile['service_type'].lower() == (
                                    service_details['service_type'].lower())))):
                        unplug_interface = False
                        break
            if unplug_interface:
                orchestration_driver = (
                    self.device_orchestrator._get_orchestration_driver(
                        device_data['service_details']['service_vendor']))

                is_interface_unplugged, advance_sharing_ifaces = (
                    orchestration_driver.unplug_network_function_device_interfaces(
                        device_data))
                if is_interface_unplugged:
                    if advance_sharing_ifaces:
                        self.device_orchestrator._update_advance_sharing_interfaces(
                            device_data,
                            advance_sharing_ifaces)
                    self.device_orchestrator._decrement_device_interface_count(device_data)

            updated_nfi = {
                'port_info': []
            }
            self.device_orchestrator.nsf_db.update_network_function_instance(
                self.device_orchestrator.db_session,
                device_data['network_function_instance_id'],
                updated_nfi)
            self.device_orchestrator.nsf_db.delete_network_function_instance(
                self.device_orchestrator.db_session,
                device_data['network_function_instance_id'])
            LOG.info(_LI(
                "NSO: Deleted network function instance: %(nfi_id)s"),
                     {'nfi_id': device_data['network_function_instance_id']})

            self.device_orchestrator.nsf_db.delete_network_function(
                self.device_orchestrator.db_session,
                device_data['network_function_id'])
            LOG.info(_LI("NSO: Deleted network function: %(nf_id)s"),
                     {'nf_id': device_data['network_function_id']})
            self._controller.event_complete(event)
        else:
            self._controller.post_event(event, target='device_orchestrator')
