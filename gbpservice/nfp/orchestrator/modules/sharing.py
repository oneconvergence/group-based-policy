from gbpservice.nfp.orchestrator.modules import device_orchestrator as ndo
from gbpservice.nfp.core.event import Event
from gbpservice.nfp.core import module as nfp_api
from gbpservice.nfp.orchestrator.db import nfp_db

from gbpservice.nfp.core import log as nfp_logging
LOG = nfp_logging.getLogger(__name__)

def events_init(controller, config, sharing_feature):
    events = ['CREATE_NETWORK_FUNCTION_DEVICE']
    events_to_register = []
    for event in events:
        events_to_register.append(
            Event(id=event, handler=sharing_feature, override=True))
    controller.register_events(events_to_register)


def nfp_module_init(controller, config):
    events_init(controller, config, SharingFeature(controller, config))
    LOG.debug("Sharing Feature: module_init")


class SharingFeature(ndo.DeviceOrchestrator, nfp_api.NfpEventHandler):

    def __init__(self, controller, config):
        super(SharingFeature, self).__init__(controller, config)
        self._controller = controller
        self.config = config
        self.db_handler = nfp_db.NFPDbBase()

    def event_method_mapping(self, event_id):
        event_handler_mapping = {
			"CREATE_NETWORK_FUNCTION_DEVICE": self.create_network_function_device
		}
    	if event_id not in event_handler_mapping:
			raise Exception("Invalid event ID")
        else:
            return event_handler_mapping[event_id]

	def handle_event(self, event):
		try:
			event_handler = self.event_method_mapping(event.id)
			event_handler(event)
		except Exception as e:
			_, _, tb = sys.exc_info()
			traceback.print_tb(tb)

	def _check_nfi_advanced_sharing(self, provider_pt_id, nfp_context):
		already_shared = False
		network_function_instances = (
			self.db_handler.get_network_function_instances(self.db_session,
														   filters={}))
		for network_function_instance in network_function_instances:
			if (provider_pt_id in network_function_instance['port_info'] and
					network_function_instance['network_function_device_id']
						is not None):
				already_shared = True
				nfp_context['network_function_device_id'] = (
					network_function_instance['network_function_device_id'])
				break
		return already_shared

    def _get_network_function_devices(self, filters=None):
        network_function_devices = self.db_handler.get_network_function_devices(
            self.db_session, filters)
        for device in network_function_devices:
            mgmt_port_id = device.pop('mgmt_port_id')
            mgmt_port_id = self._get_port(mgmt_port_id)
            device['mgmt_port_id'] = mgmt_port_id

            network_functions = (
                self._get_network_function_info(device['id']))
            device['network_functions'] = network_functions
        return network_function_devices

    def _get_device_to_reuse(self, device_data, dev_sharing_info):
        device_filters = dev_sharing_info['filters']
        orchestration_driver = super(SharingFeature, self)._get_orchestration_driver(
            device_data['service_details']['service_vendor'])
        devices = self._get_network_function_devices(device_filters)
        device = orchestration_driver.select_network_function_device(
            devices,
            device_data)
        return device

	def _prepare_advanced_sharing_graph(self, nfp_context):
		orchestration_driver = super(SharingFeature, self)._get_orchestration_driver(
			service_details['service_vendor'])
		device_data = super(SharingFeature, self)._prepare_device_data_from_nfp_context(
			nfp_context)
		dev_sharing_info = (
			orchestration_driver.get_network_function_device_sharing_info(
				device_data))
		device = self._get_device_to_reuse(device_data, dev_sharing_info)
		if device:
			device = self._update_device_data(device, device_data)
		LOG.info(_LI("Sharing existing device: %s(device)s for reuse"),
				{'device': device})

		nfp_context['network_function_device'] = (
			network_function_device)
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

        graph_event = self._controller.new_event(id="SHARING_GRAPH",
                                                 graph=graph)
        graph_nodes = [du_event, plug_int_event]
        self._controller.post_event_graph(graph_event, graph_nodes)

	def create_network_function_device(self, event):
		nfp_context = event.data
        provider = nfp_context['provider']
        provider_pt_id = provider['pt']['id']
        if (provider_pt_id and
                self._check_nfi_advanced_sharing(provider_pt_id, nfp_context)):
			self._prepare_advanced_sharing_graph(self, nfp_context)
			return

        super(SharingFeature, self).create_network_function_device(event)
