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
import uuid
import six
import oslo_messaging as messaging
from gbpservice.nfp.common import constants
from gbpservice.nfp.core.poll import poll_event_desc, PollEventDesc
from gbpservice.nfp.config_orchestrator.agent import topics
from gbpservice.nfp.config_orchestrator.agent.common import \
    prepare_request_data
from gbpservice.nfp.lib.transport import send_request_to_configurator, \
    RPCClient
from neutron._i18n import _LI, _LW, _LE
from neutron_lib import exceptions as n_exce
from oslo_log import log as logging
from oslo_log import helpers as log_helpers
from gbpservice.nfp.config_orchestrator.callbacks import firewall_agent_api \
    as api

LOG = logging.getLogger(__name__)

REMOVE_ROUTER_INTERFACE = 'remove_router_interface'
ADD_ROUTER_INTERFACE = 'add_router_interface'


class ServiceProfileNotFound(n_exce.NeutronException):
    message = _('Service Profile not found for Firewall ID - (firewall)%s.'
                'Specify profile id to render firewall.')


class FwAgent(PollEventDesc):

    RPC_API_VERSION = '1.0'
    target = messaging.Target(version=RPC_API_VERSION)

    def __init__(self, conf, sc):
        self._conf = conf
        self._sc = sc
        self.oc_fw_plugin_rpc = api.FWaaSPluginApiMixin(
            topics.FW_NFP_PLUGIN_TOPIC, self._conf.host)

    @property
    def so_rpc_client(self):
        return RPCClient(topics.NFP_NSO_TOPIC)

    @property
    def fw_plugin_client(self):
        return RPCClient(topics.FW_NFP_PLUGIN_TOPIC)

    def event_method_mapping(self, event_id):
        event_handler_mapping = {
            'FW_INSTANCE_SPAWNING': self.wait_for_device_ready,
            'FW_SERVICE_DELETE_IN_PROGRESS': self.service_deletion_done,
            'ROUTERS_UPDATED': self.process_l3_events
        }

        if event_id not in event_handler_mapping:
            raise Exception("Invalid Event ID")
        else:
            return event_handler_mapping[event_id]

    def _create_event(self, event_id, event_data=None, is_poll_event=False,
                      serialize=False, binding_key=None, key=None,
                      max_times=10):
        if is_poll_event:
            ev = self._sc.new_event(
                    id=event_id, data=event_data, serialize=serialize,
                    binding_key=binding_key, key=key)
            LOG.debug("poll event started for %s" % ev.id)
            self._sc.poll_event(ev, max_times=max_times)
        else:
            ev = self._sc.new_event(id=event_id, data=event_data)
            self._sc.post_event(ev)
        self._log_event_created(event_id, event_data)

    def handle_event(self, event):
        LOG.info(_LI("FWAgent received event %(id)s"),
                 {'id': event.id})
        try:
            event_handler = self.event_method_mapping(event.id)
            event_handler(event)
        except Exception:
            LOG.exception(_LE("Error in processing event: %(event_id)s"),
                          {'event_id': event.id})

    def handle_poll_event(self, event):
        LOG.info(_LI("Firewall Agent received poll event %(id)s"),
                 {'id': event.id})
        try:
            event_handler = self.event_method_mapping(event.id)
            return event_handler(event)
        except Exception:
            LOG.exception(_LE("Error in processing poll event: "
                              "%(event_id)s"), {'event_id': event.id})

    def poll_event_cancel(self, event):
        LOG.info(_LI("Poll event %(event_id)s cancelled."),
                 {'event_id': event.id})
        nw_fun_data = event.data
        if event.id == 'FW_INSTANCE_SPAWNING':
            erred_services = nw_fun_data['erred_services']
            erred_services.append(nw_fun_data['nw_function'])
            service_info_list = nw_fun_data['service_info_list']
            if service_info_list:
                network_function_data = nw_fun_data['network_function_data']
                network_function_data.update(service_info=service_info_list[0])
                service_info_list.pop(0)
                self.create_fw_instance(
                        nw_fun_data['context'], network_function_data,
                        service_info_list, nw_fun_data['processed_services'],
                        erred_services)
            else:
                nw_fun_data.update(erred_services=erred_services,
                                   nw_function={})
                self.post_process_create_firewall_service(nw_fun_data)
        elif event.id == 'FW_SERVICE_DELETE_IN_PROGRESS':
            nw_fun_data['erred_services'].append(nw_fun_data['nw_function'])
            try:
                nw_fun_data['network_function_list'].pop(0)
            except IndexError:
                LOG.warning(_LW("No more services to process"))
            if nw_fun_data['network_functions_list']:
                self.continue_deleting_fw_instance(nw_fun_data)
            else:
                nw_fun_data.update(nw_function={})
                self.process_post_delete(nw_fun_data)
        else:
            LOG.warning(_LW("Unhandled cancelled event %(event)s received"),
                        {'event': event.id})

    def create_firewall(self, context, firewall, host):
        # REVISIT(VK) This need to get fixed. We can't validate here. Think
        # about delete.
        try:
            is_neutron_mode = self._is_network_function_mode_neutron(firewall)
        except ServiceProfileNotFound:
            return self.oc_fw_plugin_rpc.set_firewall_status(context, firewall[
                'id'], constants.ERROR)
        LOG.info(_LI("Firewall - %(id)s create started") % {'id': firewall[
            'id']})
        if is_neutron_mode:
            self.process_create_firewall_service(context, firewall, host)
        else:
            self.call_configurator_for_config(context, firewall, host)

    def update_firewall(self, context, firewall, host):
        pass

    @log_helpers.log_method_call
    def delete_firewall(self, context, firewall, host):
        resource = 'firewall'
        firewall = self.get_extra_details_for_firewall_delete(context,
                                                              firewall)
        if 'services_to_delete' in firewall and not firewall[
           'services_to_delete']:
            self.oc_fw_plugin_rpc.firewall_deleted(context, firewall['id'])
        kwargs = {resource: firewall, 'host': host, 'context':
                  context.to_dict()}
        body = prepare_request_data(resource, kwargs, "firewall")
        LOG.info(_LI("Firewall - %(id)s delete started") % {'id': firewall[
            'id']})
        send_request_to_configurator(self._conf, context, body, "DELETE")

    def firewall_configuration_create_complete(self, context,  **kwargs):
        # Currently proxy agent is sending like - kwargs = {'kwargs': {}}. Bad
        kwargs = kwargs['kwargs']
        firewall = kwargs['firewall']
        if 'neutron_mode' not in firewall:
            return self.update_status(context, firewall)
        _erred_services = [service['id'] for service in firewall[
                                   'erred_services']]
        erred_services = [service for service in firewall[
            'config_erred_services'] if service['id'] not in
                                  _erred_services] + firewall['erred_services']
        if erred_services:
            service_ids = [service['service_id'] for service in erred_services]
            self.so_rpc_client.cctxt.cast(
                    context, 'admin_down_interfaces', port_ids=service_ids)
        if firewall.get('l3_notification'):
            return
        if firewall['configured_services']:
            self.oc_fw_plugin_rpc.set_firewall_status(context, firewall['id'],
                                                      constants.ACTIVE)
        else:
            self.oc_fw_plugin_rpc.set_firewall_status(context, firewall['id'],
                                                      constants.ERROR)
        LOG.info(_LI("Firewall - %(id)s creation completed.") %
                 {'id': firewall['id']})

    def firewall_configuration_delete_complete(self, context, **kwargs):
        kwargs = kwargs['kwargs']
        firewall = kwargs['firewall']
        if 'neutron_mode' in firewall:
            try:
                # Have no idea whether this will work or not.
                self.delete_firewall_instances(context, firewall)
            except Exception, err:
                LOG.error(_LE("Exception - %(err)s occurred while deleting "
                              "firewall instances. ") % {'err': err})
                self.oc_fw_plugin_rpc.set_firewall_status(context, firewall[
                    'id'], constants.ERROR)
        else:
            status = firewall['status']
            if status == constants.SUCCESS:
                self.oc_fw_plugin_rpc.firewall_deleted(context, firewall['id'])
            else:
                self.oc_fw_plugin_rpc.set_firewall_status(context, firewall[
                    'id'], constants.ERROR)

    def call_configurator_for_config(self, context, firewall, host):
        resource = 'firewall'
        kwargs = {resource: firewall,
                  'host': host,
                  'context': context.to_dict()}
        body = prepare_request_data(resource, kwargs, "firewall")
        send_request_to_configurator(self._conf, context, body, "CREATE")

    def get_extra_details_for_firewall_delete(self, context, firewall):
        if not self._is_network_function_mode_neutron(firewall) or\
                firewall.get('services_to_delete'):
            return firewall
        nw_functions = self.so_rpc_client.cctxt.call(
                context, 'get_network_functions',
                filters={'service_config': [firewall['id']]})
        firewall.update(services_to_delete=nw_functions, neutron_mode=True)
        return firewall

    def delete_firewall_instances(self, context, firewall):
        """
        This should only get executed only in firewall event.
        """
        # REVISIT (VK) : Think filter on firewall id would be fine.
        nw_functions = firewall.get('config_deleted_services')

        processed_services, erred_services = list(), list()
        event_data = {'context': context, 'nw_function': None,
                      'network_function_mode': 'neutron',
                      'tenant_id': firewall['tenant_id'],
                      'service_type': 'firewall',
                      'network_function_list': nw_functions,
                      'processed_services': processed_services,
                      'erred_services': erred_services,
                      'resource_data': firewall}
        if not nw_functions:
            self.process_post_delete(event_data)
        else:
            # Is this at all right ??? Blind processing.
            nw_functions[0].update(service_type='firewall')
            nw_function = self.so_rpc_client.cctxt.call(
                    context, 'neutron_delete_nw_function_config',
                    network_function=nw_functions[0])
            # nw_function = self.so_rpc_client.cctxt.call(
            #         context, 'delete_network_function',
            #         network_function_id=nw_functions[0]['id'])
            event_data.update(nw_function=nw_function)
            self._create_event(event_id='FW_SERVICE_DELETE_IN_PROGRESS',
                               event_data=event_data, is_poll_event=True,
                               serialize=True, binding_key=firewall['id'])

    @poll_event_desc(event='FW_SERVICE_DELETE_IN_PROGRESS', spacing=30)
    def service_deletion_done(self, event):
        """
        """
        data = event.data
        try:
            nw_function = self.so_rpc_client.cctxt.call(
                    data['context'], 'get_network_function',
                    network_function_id=data['nw_function']['id'])
        except messaging.RemoteError, messaging.MessagingTimeout:
            # REVISIT(VK) Do we need to handle this differently ?
            nw_function = None

        if not nw_function:
            self._sc.poll_event_done(event)
            data['processed_services'].append(data['nw_function'])
            try:
                data['network_function_list'].pop(0)
            except IndexError:
                LOG.warning(_LW("No more services to process"))
            if data['network_function_list']:
                self.continue_deleting_fw_instance(data)
            else:
                data.update(nw_function={})
                self.process_post_delete(data)

        elif nw_function['status'] == constants.ERROR:
            self._sc.poll_event_done(event)
            data['erred_services'].append(data['nw_function'])
            try:
                data['network_function_list'].pop(0)
            except IndexError:
                LOG.warning(_LW("No more services to process"))
            if data['network_functions_list']:
                self.continue_deleting_fw_instance(data)
            else:
                data.update(nw_function={})
                self.process_post_delete(data)

    def continue_deleting_fw_instance(self, data):
        data['network_function_list'][0].update(service_type='firewall')
        nw_function = self.so_rpc_client.cctxt.call(
                data['context'], 'neutron_delete_nw_function_config',
                network_function=data['network_function_list'][0])
        # nw_function = self.so_rpc_client.cctxt.call(
        #         data['context'], 'delete_network_function',
        #         network_function_id=data['network_function_list'][0][
        #             'id'])
        data.update(nw_function=nw_function,
                    processed_services=data['processed_services'],
                    network_function_list=data['network_function_list']
                    )
        self._create_event(event_id='FW_SERVICE_DELETE_IN_PROGRESS',
                           event_data=data, serialize=True, is_poll_event=True,
                           binding_key=data['resource_data']['id'])

    def process_post_delete(self, nw_function_data):
        """
        """
        firewall = nw_function_data['resource_data']
        # deleted_services = list(set(nw_function_data['processed_services']) &
        #                         set(firewall['config_deleted_services']))
        # erred_services = list(set(nw_function_data['erred_services']) |
        #  set(firewall['delete_erred_services']))
        _erred_services = [service['id'] for service in nw_function_data[
            'erred_services']]
        erred_services = [service for service in firewall[
            'delete_erred_services'] if service['id'] not in
                          _erred_services] + nw_function_data['erred_services']
        # service_ids = [service['service_id'] for service in erred_services]
        # if service_ids:
        #     pass
            # self.so_rpc_client.cctxt.cast(nw_function_data['context'],
            #                               'admin_down_interfaces',
            #                               port_ids=service_ids)

        # for service in erred_services:
        #     self.so_rpc_client.cctxt.cast(nw_function_data['context'],
        #                                   'delete_network_function',
        #                                   network_function_id=service['id'])

        if firewall.get('l3_notification'):
            return
        elif not erred_services:
            self.oc_fw_plugin_rpc.firewall_deleted(
                    nw_function_data['context'], firewall['id'])
        else:
            self.oc_fw_plugin_rpc.set_firewall_status(
                    nw_function_data['context'], firewall['id'],
                    constants.ERROR)
        LOG.info(_LI("Firewall - %(id)s deletion completed.") % {
            'id': firewall['id']})

    def process_create_firewall_service(self, context, firewall, host):
        kwargs = {'router_ids': firewall['add-router-ids']}
        router_interfaces = self.fw_plugin_client.cctxt.call(
                context, 'get_router_interfaces_details', **kwargs)
        service_info_list = self.prepare_service_info(firewall,
                                                      router_interfaces)
        network_function_data = self.prepare_create_resource_body(firewall)
        processed_services, erred_services = list(), list()

        network_function_data.update(service_info=service_info_list[0])
        service_info_list.pop(0)
        self.create_fw_instance(context, network_function_data,
                                service_info_list, processed_services,
                                erred_services)

    def create_fw_instance(self, context, network_function_data,
                           service_info_list,
                           processed_services, erred_services):
        nw_function = self.so_rpc_client.cctxt.call(
                context, 'neutron_update_nw_function_config',
                network_function=network_function_data)

        event_data = dict(nw_function=nw_function,
                          service_info_list=service_info_list,
                          processed_services=processed_services,
                          erred_services=erred_services,
                          network_function_data=network_function_data,
                          context=context)
        self._create_event(event_id='FW_INSTANCE_SPAWNING',
                           event_data=event_data, is_poll_event=True,
                           serialize=True, binding_key=network_function_data[
                               'resource_data']['id'])

    @poll_event_desc(event='FW_INSTANCE_SPAWNING', spacing=30)
    def wait_for_device_ready(self, event):
        nw_fun_data = event.data
        nw_fun_id = nw_fun_data['nw_function']['id']
        fw_service = self.so_rpc_client.cctxt.call(
                nw_fun_data['context'], 'get_network_function',
                network_function_id=nw_fun_id)

        if not fw_service or fw_service['status'] == constants.ERROR:
            self._sc.poll_event_done(event)
            # REVISIT(VK) Wacky Wacky !!!
            nw_fun_data['nw_function'] = fw_service
            erred_services = nw_fun_data['erred_services']
            erred_services.append(nw_fun_data['nw_function'])
            service_info_list = nw_fun_data['service_info_list']
            if service_info_list:
                network_function_data = nw_fun_data['network_function_data']
                network_function_data.update(service_info=service_info_list[0])
                service_info_list.pop(0)
                self.create_fw_instance(
                        nw_fun_data['context'], network_function_data,
                        service_info_list, nw_fun_data['processed_services'],
                        erred_services)
            else:
                nw_fun_data.update(erred_services=erred_services,
                                   nw_function={})
                self.post_process_create_firewall_service(nw_fun_data)
        elif fw_service['status'] == constants.ACTIVE:
            self._sc.poll_event_done(event)
            nw_fun_data['nw_function'] = fw_service
            processed_services = nw_fun_data['processed_services']
            processed_services.append(nw_fun_data['nw_function'])
            service_info_list = nw_fun_data['service_info_list']
            if service_info_list:
                network_function_data = nw_fun_data['network_function_data']
                network_function_data.update(service_info=service_info_list[0])
                service_info_list.pop(0)
                self.create_fw_instance(
                        nw_fun_data['context'], network_function_data,
                        service_info_list, processed_services, nw_fun_data[
                            'erred_services'])
            else:
                nw_fun_data.update(processed_services=processed_services,
                                   nw_function={})
                self.post_process_create_firewall_service(nw_fun_data)

    def post_process_create_firewall_service(self, nw_fun_data):
        firewall = nw_fun_data['network_function_data']['resource_data']
        if nw_fun_data['processed_services']:
            firewall['services_to_configure'] = nw_fun_data[
                'processed_services']
            firewall['erred_services'] = nw_fun_data['erred_services']
            firewall['neutron_mode'] = True
            if nw_fun_data.get('l3_notification'):
                firewall['l3_notification'] = True
            LOG.info(_LI("Sending configuration request to configurator for "
                         "firewall - %s"), firewall['id'])
            # Batch processing, have no other choice.
            self.call_configurator_for_config(
                    nw_fun_data['context'], firewall=nw_fun_data[
                        'network_function_data']['resource_data'],
                    host=self._conf.host)
        elif nw_fun_data.get('l3_notification'):
            kwargs = {'port': nw_fun_data['service_info'][0]['port']['id']}
            # self.so_rpc_client.cctxt.call(
            #         nw_fun_data['context'], 'delete_network_function',
            #         network_function_id=nw_fun_data['erred_services'][0]['id'])
            nw_function = nw_fun_data['network_function_list'][0]
            nw_function.update(service_type='firewall')
            # self.so_rpc_client.cctxt.call(nw_fun_data['context'],
            #                               'neutron_delete_nw_function_config',
            #                               network_function=nw_fun_data[
            #                                   'network_function_list'][0])

            # Plug the router port back in ADMIN STATE DOWN mode.
            self.fw_plugin_client.cctxt.cast(nw_fun_data['context'],
                                             'delete_router_port', **kwargs)
        elif nw_fun_data['erred_services']:
            self.oc_fw_plugin_rpc.set_firewall_status(
                    nw_fun_data['context'], firewall['id'], constants.ERROR)
            # Shall we do cleanup or leave ?
            # self.do_cleanup(nw_fun_data['context'], nw_fun_data[
            #     'erred_services'])

    def process_l3_events(self, l3_data):
        l3_data = l3_data.data
        context = l3_data['context']
        if l3_data['operation'] == REMOVE_ROUTER_INTERFACE:
            filters = {'service_id': l3_data['interfaces'][0]['id']}
            network_function = self.so_rpc_client.cctxt.call(
                    context, 'get_network_functions', filters=filters)
            if not network_function:
                LOG.warning(_LW("Corresponding Network function for Firewall "
                                "interface - %(interface_id)s not "
                                "found"), {'interface_id': l3_data[
                                    'interfaces'][0]['id']})
                return
            firewall = l3_data['firewalls'][0]
            firewall.update(services_to_delete=[network_function],
                            l3_notification=True)
            # Track this in RPCCallback and trigger network function delete
            # to service orchestrator.
            self.delete_firewall(context, firewall, host=None)
        elif l3_data['operation'] == ADD_ROUTER_INTERFACE:
            try:
                network_function_data = self.prepare_create_resource_body(
                        l3_data['firewalls'][0])
            except ServiceProfileNotFound:
                return self.oc_fw_plugin_rpc.set_firewall_status(
                        context, l3_data['firewalls'][0]['id'],
                        constants.ERROR)
            # 1:1 assumption
            service_info = dict(router_id=l3_data['routers'][0]['id'],
                                port=l3_data['interfaces'][0],
                                subnet=l3_data['interfaces'][0][
                                    'fixed_ips'][0]['subnet_id'])
            network_function_data.update(service_info=[service_info],
                                         l3_notification=True)
            self.create_fw_instance(context, network_function_data, [], [], [])

    def do_cleanup(self, context, erred_services):
        for service in erred_services:
            # Fire & Forget ???? Is this correct ?
            service.update(service_type='firewall')
            try:
                self.so_rpc_client.cctxt.call(
                        context, 'neutron_delete_nw_function_config',
                        network_function=service)
                # self.so_rpc_client.cctxt.call(
                #         context, 'delete_network_function',
                #         network_function_id=service['id'])
            except messaging.MessagingTimeout:
                LOG.error(_LE("Network function - %(network_function_id)s "
                              "deletion timed out.") %
                          {'network_function_id': service['id']})
            except messaging.RemoteError as ex:
                LOG.error(_LE("ERROR occurred  during network function - "
                              "%(nw_fun_id)s deletion. Reason - %(reason)s") %
                          {'nw_function_id': service['id'], 'reason':
                              six.text_type(ex)})

    @staticmethod
    def _log_event_created(event_id, event_data):
        LOG.info(_LI("Firewall Agent created event %(event_name)s with "
                     "event data %(event_data)s"), {
                     'event_name': event_id, 'event_data': event_data})

    @staticmethod
    def prepare_create_resource_body(firewall):
        """
        """
        network_function_info = dict()
        desc = firewall['description']
        fields = desc.split(';')
        for field in fields:
            if 'service_profile_id' in field:
                network_function_info['service_profile_id'] = field.split(
                        '=')[1]
        if not ('service_profile_id' in network_function_info):
            raise ServiceProfileNotFound(firewall=firewall['id'])
        network_function_info.update(network_function_mode='neutron',
                                     tenant_id=firewall['tenant_id'],
                                     service_type='firewall',
                                     resource_data=firewall)
        return network_function_info

    @staticmethod
    def prepare_service_info(firewall, router_interfaces, method=None):
        router_ids = firewall['router_ids'] if method == 'delete' else \
            firewall['add-router-ids']
        if method == 'delete':
            service_info_list = [{'router_id': interface['device_id'],
                                  'port': interface,
                                  'subnet': interface['fixed_ips'][0][
                                      'subnet_id']}
                                 for interface in router_interfaces
                                 if interface['name'] != 'oc_owned_stitching']
            return service_info_list
        router_interface_mapping = dict()
        for rtr_id in router_ids:
            router_interface_mapping[rtr_id] = \
                FwAgent.get_interfaces_for_router(rtr_id, router_interfaces)
        service_info_list = list()
        for rtr, _interfaces in router_interface_mapping.iteritems():
            for _, _interface in _interfaces.iteritems():
                service_info = dict(router_id=rtr, port=_interface,
                                    subnet=_interface['fixed_ips'][0][
                                        'subnet_id'])
                service_info_list.append([service_info])
        return service_info_list   # list of lists

    @staticmethod
    def get_interfaces_for_router(rtr_id, router_interfaces):
        interfaces = {}
        for interface in router_interfaces:
            if rtr_id in (interface['device_id'], interface['description']):
                interfaces.update({interface['id']: interface})
        return interfaces

    @staticmethod
    def _is_network_function_mode_neutron(firewall):
        desc = firewall['description']
        # Only expecting service_profile_id
        if len(desc.split(';')) > 1:
            return False
        else:
            desc_list = desc.split('=')
            if not desc_list[0] == 'service_profile_id':
                raise ServiceProfileNotFound(firewall=firewall['id'])
            try:
                uuid.UUID(desc_list[1])
            except (ValueError, IndexError):
                raise ServiceProfileNotFound(firewall=firewall['id'])
            return True

    def update_status(self, context, firewall):
        self.oc_fw_plugin_rpc.set_firewall_status(context, firewall['id'],
                                                  firewall['status'])


class FwPluginApi(object):

    RPC_API_VERSION = '1.0'
    target = messaging.Target(version=RPC_API_VERSION)

    def __init__(self, conf, sc):
        print 'FwPluginApi'
        self._conf = conf
        self._sc = sc

    def firewall_configuration_create_complete(self, context, **kwargs):
        kwargs = kwargs['kwargs']
        rpcClient = transport.RPCClient(topics.FW_NFP_PLUGIN_TOPIC)
        firewall_id = kwargs['firewall_id']
        status = kwargs['status']
        rpcClient.cctxt.cast(context, 'set_firewall_status',
                             host=kwargs['host'],
                             firewall_id=firewall_id,
                             status=status)

    def firewall_configuration_delete_complete(self, context, **kwargs):
        kwargs = kwargs['kwargs']
        rpcClient = transport.RPCClient(topics.FW_NFP_PLUGIN_TOPIC)
        firewall_id = kwargs['firewall_id']
        rpcClient.cctxt.cast(context, 'firewall_deleted',
                             host=kwargs['host'],
                             firewall_id=firewall_id)
