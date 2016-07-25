from gbpservice.nfp.core import event as nfp_event
from gbpservice.nfp.core.event import Event
from gbpservice.nfp.core import module as nfp_api

from gbpservice.nfp.orchestrator.modules import device_orchestrator
from gbpservice.nfp.orchestrator.drivers import sharing_driver

import sys
import time
import traceback

from gbpservice.nfp.core import log as nfp_logging
LOG = nfp_logging.getLogger(__name__)


def events_init(controller, config, orchestrator):
    events = ['CREATE_NETWORK_FUNCTION_DEVICE']
    events_to_register = []
    for event in events:
        events_to_register.append(
            Event(id=event, handler=orchestrator))
    controller.register_events(events_to_register, module='sharing', priority=1)


def nfp_module_init(controller, config):
    events_init(controller, config, Sharing(controller, config))
    LOG.debug("Service Sharing: module_init")


class Sharing(nfp_api.NfpEventHandler):
    def __init__(self, controller, config):
        self._controller = controller
        self.config = config
        self.device_orchestrator = device_orchestrator.DeviceOrchestrator(controller, config)
        self.sharing_driver = sharing_driver.SharingDriver(config)

    def handle_event(self, event):
        if event.id == "CREATE_NETWORK_FUNCTION_DEVICE":
            self.create_network_function_device(event)
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
        devices = self.device_orchestrator._get_network_function_devices(device_filters)
        device = self.sharing_driver.select_network_function_device(devices, device_data)
        return device
                      
    def create_network_function_device(self, event):
        nfp_context = event.data
        LOG.info(_LI("Orchestrator's sharing module received "
                     " create network function "
                     "device request with data %(data)s"),
                 {'data': nfd_request})
        device_data = self.device_orchestrator._prepare_device_data_from_nfp_context(nfp_context)
       
        device = self._get_device_to_reuse(device_data)
        if device:
            device.update(device_data)
            # Existing device to be shared
            # Trigger an event for Service Orchestrator
            device['network_function_device_id'] = device['id']
            # Create an event to NSO, to give device_id
            device_created_data = {
                'network_function_instance_id': (
                    nfp_context['network_function_instance']['id']),
                'network_function_device_id': device['id']
            }
            self.device_orchestrator._create_event(event_id='DEVICE_CREATED',
                           event_data=device_created_data)
            

            # Since the device is already UP, create a GRAPH so that
            # further processing continues in device orchestrator
            nf_id = nfp_context['network_function']['id']
            du_event = self._controller.new_event(id="DEVICE_UP",
                                                  key=nf_id,
                                                  data=nfp_context,
                                                  graph=True)

            plug_int_event = self._controller.new_event(id="PLUG_INTERFACES",
                                                        key=nf_id,
                                                        data=nfp_context,
                                                        graph=True)

            graph = nfp_event.EventGraph(du_event)
            graph.add_node(plug_int_event, du_event)

            graph_event = self._controller.new_event(id="DEVICE_SHARE_GRAPH",
                                                     graph=graph)
            graph_nodes = [du_event, plug_int_event]
            self._controller.post_event_graph(graph_event, graph_nodes)
        else:
            # Device does not exist.
            # Post this event back to device orchestrator
            # It will handle as it was handling in non sharing case
            self._controller.post_event(event, target='device_orchestrator')
