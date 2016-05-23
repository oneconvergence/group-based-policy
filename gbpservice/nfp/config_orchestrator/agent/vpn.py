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

import ast
import copy
import eventlet
from gbpservice.nfp.config_orchestrator.agent import common
from gbpservice.nfp.config_orchestrator.agent import topics as a_topics
from gbpservice.nfp.core import common as nfp_common
from gbpservice.nfp.core.poll import poll_event_desc, PollEventDesc
from gbpservice.nfp.lib import transport

from neutron_vpnaas.db.vpn import vpn_db

from oslo_log import helpers as log_helpers
from oslo_log import log as oslo_logging
import oslo_messaging as messaging
from neutron_lib import exceptions as n_exec

from neutron import context as n_context
LOGGER = oslo_logging.getLogger(__name__)
LOG = nfp_common.log


class VPNServiceDeleteFailed(n_exec.NeutronException):
    message = "VPN Service Deletion failed"


class VPNServiceCreateFailed(n_exec.NeutronException):
    message = "VPN Service Creation Failed"


"""
RPC handler for VPN service
"""


class VpnAgent(vpn_db.VPNPluginDb, vpn_db.VPNPluginRpcDbMixin):
    RPC_API_VERSION = '1.0'
    target = messaging.Target(version=RPC_API_VERSION)

    def __init__(self, conf, sc):
        super(VpnAgent, self).__init__()
        self._conf = conf
        self._sc = sc
        self._db_inst = super(VpnAgent, self)

    def _get_dict_desc_from_string(self, vpn_svc):
        svc_desc = vpn_svc.split(";")
        desc = {}
        for ele in svc_desc:
            s_ele = ele.split("=")
            desc.update({s_ele[0]: s_ele[1]})
        return desc

    def _get_vpn_context(self, context, tenant_id, vpnservice_id,
                         ikepolicy_id, ipsecpolicy_id,
                         ipsec_site_conn_id, desc):
        vpnservices = self._get_vpnservices(context, tenant_id,
                                            vpnservice_id, desc)
        ikepolicies = self._get_ikepolicies(context, tenant_id,
                                            ikepolicy_id)
        ipsecpolicies = self._get_ipsecpolicies(context, tenant_id,
                                                ipsecpolicy_id)
        ipsec_site_conns = self._get_ipsec_site_conns(context, tenant_id,
                                                      ipsec_site_conn_id, desc)

        return {'vpnservices': vpnservices,
                'ikepolicies': ikepolicies,
                'ipsecpolicies': ipsecpolicies,
                'ipsec_site_conns': ipsec_site_conns}

    def _get_core_context(self, context):
        return {'networks': common.get_networks(context, self._conf.host),
                'routers': common.get_routers(context, self._conf.host)}

    def _context(self, context, tenant_id, resource, resource_data):
        if context.is_admin:
            tenant_id = context.tenant_id
        if resource.lower() == 'ipsec_site_connection':
            vpn_ctx_db = self._get_vpn_context(context,
                                               tenant_id,
                                               resource_data[
                                                   'vpnservice_id'],
                                               resource_data[
                                                   'ikepolicy_id'],
                                               resource_data[
                                                   'ipsecpolicy_id'],
                                               resource_data['id'],
                                               resource_data[
                                                   'description'])
            core_db = self._get_core_context(context)
            filtered_core_db = self.\
                _filter_core_data(core_db,
                                  vpn_ctx_db[
                                      'vpnservices'])
            vpn_ctx_db.update(filtered_core_db)
            return vpn_ctx_db
        elif resource.lower() == 'vpn_service':
            return {'vpnservices': [resource_data]}
        else:
            return None

    def _prepare_resource_context_dicts(self, context, tenant_id,
                                        resource, resource_data):
        # Prepare context_dict
        ctx_dict = context.to_dict()
        # Collecting db entry required by configurator.
        # Addind service_info to neutron context and sending
        # dictionary format to the configurator.
        db = self._context(context, tenant_id, resource,
                           resource_data)
        rsrc_ctx_dict = copy.deepcopy(ctx_dict)
        rsrc_ctx_dict.update({'service_info': db})
        return ctx_dict, rsrc_ctx_dict

    def _data_wrapper(self, context, tenant_id, nf, **kwargs):
        nfp_context = {}
        str_description = nf['description'].split('\n')[1]
        description = self._get_dict_desc_from_string(
            str_description)
        resource = kwargs['rsrc_type']
        resource_data = kwargs['resource']
        resource_data['description'] = str_description
        if resource.lower() == 'ipsec_site_connection':
            nfp_context = {'network_function_id': nf['id'],
                           'ipsec_site_connection_id': kwargs[
                               'rsrc_id']}

        ctx_dict, rsrc_ctx_dict = self.\
            _prepare_resource_context_dicts(context, tenant_id,
                                            resource, resource_data)
        nfp_context.update({'neutron_context': ctx_dict,
                            'requester': 'nas_service'})
        resource_type = 'vpn'
        kwargs.update({'neutron_context': rsrc_ctx_dict})
        body = common.prepare_request_data(nfp_context, resource,
                                           resource_type, kwargs,
                                           description['service_vendor'])
        return body

    def _fetch_nf_from_resource_desc(self, desc):
        desc_dict = ast.literal_eval(desc)
        nf_id = desc_dict['network_function_id']
        return nf_id

    @staticmethod
    def _is_network_function_mode_neutron(kwargs):
        desc = kwargs['resource']['description']
        # Only expecting service_profile_id
        if len(desc.split(';')) == 1 and 'service_profile_id' in desc:
            return True
        else:
            return False

    def handle_neutron_service_updated(self, context, **kwargs):
        neutronaas = NeutronVpnaasAgent(self._conf, self._sc)
        if kwargs['reason'] == 'create':
            nw_fun_info = (
                neutronaas.validate_and_process_vpn_create_service_request(
                    context, kwargs))
            if kwargs['rsrc_type'] == 'ipsec_site_connection':
                if ('nw_func' in nw_fun_info and
                        nw_fun_info["nw_func"]["status"] == "ACTIVE"):
                    kwargs['resource']['description'] = nw_fun_info[
                        'nw_func']['description']
                    self.call_configurator(context, kwargs)
        if kwargs['reason'] == 'delete':
            if kwargs['rsrc_type'] == 'ipsec_site_connection':
                rpcc = transport.RPCClient(a_topics.NFP_NSO_TOPIC)
                nw_func = rpcc.cctxt.call(
                    context, 'get_network_functions',
                    filters={'service_id': [kwargs['resource'][
                                                'vpnservice_id']]})
                if nw_func:
                    kwargs['resource']['description'] = nw_func[0][
                        'description']
                self.call_configurator(context, kwargs)
            else:
                kwargs.update({'context': context.to_dict()})
                filters = {'service_id': [kwargs['rsrc_id']]}
                rpcc = transport.RPCClient(a_topics.NFP_NSO_TOPIC)
                nw_function = rpcc.cctxt.call(
                        context, 'get_network_functions', filters=filters)
                if not nw_function:
                    vpn_plugin = transport.RPCClient(
                            a_topics.VPN_NFP_PLUGIN_TOPIC)
                    vpn_plugin.cctxt.cast(context, 'vpnservice_deleted',
                                          id=kwargs['rsrc_id'])
                    return
                rpcc.cctxt.cast(context,
                                'delete_network_function',
                                network_function_id=nw_function[0]['id'])
                neutronaas._create_event(
                    event_id='VPN_SERVICE_DELETE_IN_PROGRESS',
                    event_data=kwargs,
                    is_poll_event=True,
                    serialize=True,
                    binding_key=kwargs['resource']['id'])

    @log_helpers.log_method_call
    def vpnservice_updated(self, context, **kwargs):
        LOG(LOGGER, 'DEBUG', "vpnservice_updated, kwargs %r" % kwargs)
        if self._is_network_function_mode_neutron(kwargs):
            self.handle_neutron_service_updated(context, kwargs)
        else:
            if (kwargs['reason'] == 'delete' and
                    kwargs['rsrc_type'] == 'vpn_service'):
                return
            else:
                # self.call_configurator(context, kwargs)
                # Fetch nf_id from description of the resource
                nf_id = self._fetch_nf_from_resource_desc(kwargs[
                    'resource']['description'])
                nf = common.get_network_function_details(context, nf_id)
                reason = kwargs['reason']
                body = self._data_wrapper(context, kwargs[
                    'resource']['tenant_id'], nf, **kwargs)
                transport.send_request_to_configurator(self._conf,
                                                       context, body,
                                                       reason)

    def call_configurator(self, context, kwargs):
        tenant_id = kwargs['resource']['tenant_id']
        ctx_dict, rsrc_ctx_dict = self.\
            _prepare_resource_context_dicts(context, tenant_id)
        nfp_context = {'neutron_context': ctx_dict,
                       'requester': 'nas_service'}
        resource_type = 'vpn'
        resource = kwargs['rsrc_type']
        if resource.lower() == 'ipsec_site_connection':
            ipsec_desc = self._get_dict_desc_from_string(kwargs[
                'resource']['description'])
            nf_id = ipsec_desc['network_function_id']
            ipsec_site_connection_id = kwargs['rsrc_id']
            nfp_context.update(
                {'network_function_id': nf_id,
                 'ipsec_site_connection_id': ipsec_site_connection_id})
        kwargs.update({'neutron_context': rsrc_ctx_dict})
        resource_data = kwargs
        reason = kwargs.get('reason')
        body = common.prepare_request_data(nfp_context, resource,
                                           resource_type, resource_data)
        transport.send_request_to_configurator(self._conf,
                                               context, body,
                                               reason)

    def _filter_core_data(self, db_data, vpnservices):
        filtered_core_data = {'subnets': [],
                              'routers': []}
        for vpnservice in vpnservices:
            subnet_id = vpnservice['subnet_id']
            for network in db_data['networks']:
                subnets = network['subnets']
                for subnet in subnets:
                    if subnet['id'] == subnet_id:
                        filtered_core_data['subnets'].append(
                            {'id': subnet['id'], 'cidr': subnet['cidr']})
            router_id = vpnservice['router_id']
            for router in db_data['routers']:
                if router['id'] == router_id:
                    filtered_core_data['routers'].append({'id': router_id})
        return filtered_core_data

    def _get_vpnservices(self, context, tenant_id, vpnservice_id, desc):
        filters = {'tenant_id': [tenant_id],
                   'id': [vpnservice_id]}
        args = {'context': context, 'filters': filters}
        vpnservices = self._db_inst.get_vpnservices(**args)
        for vpnservice in vpnservices:
            vpnservice['description'] = desc
        return vpnservices

    def _get_ikepolicies(self, context, tenant_id, ikepolicy_id):
        filters = {'tenant_id': [tenant_id],
                   'id': [ikepolicy_id]}
        args = {'context': context, 'filters': filters}
        return self._db_inst.get_ikepolicies(**args)

    def _get_ipsecpolicies(self, context, tenant_id, ipsecpolicy_id):
        filters = {'tenant_id': [tenant_id],
                   'id': [ipsecpolicy_id]}
        args = {'context': context, 'filters': filters}
        return self._db_inst.get_ipsecpolicies(**args)

    def _get_ipsec_site_conns(self, context, tenant_id, ipsec_site_conn_id,
                              desc):
        filters = {'tenant_id': [tenant_id],
                   'id': [ipsec_site_conn_id]}
        args = {'context': context, 'filters': filters}
        ipsec_site_conns = self._db_inst.get_ipsec_site_connections(**args)
        for ipsec_site_conn in ipsec_site_conns:
            ipsec_site_conn['description'] = desc
        return ipsec_site_conns


class VpnNotifier(object):

    def __init__(self, conf, sc):
        self._sc = sc
        self._conf = conf

    def _prepare_request_data(self, context, nf_id,
                              resource_id, ipsec_id, service_type):
        request_data = None
        try:
            request_data = common.get_network_function_map(
                context, nf_id)
            # Adding Service Type #
            request_data.update({"service_type": service_type,
                                 "ipsec_site_connection_id": ipsec_id,
                                 "neutron_resource_id": resource_id,
                                 "LogMetaID": nf_id})
        except Exception as e:
            LOG(LOGGER, 'ERROR', '%s' % (e))

            return request_data
        return request_data

    def _trigger_service_event(self, context, event_type, event_id,
                               request_data):
        event_data = {'resource': None,
                      'context': context.to_dict()}
        event_data['resource'] = {'eventtype': event_type,
                                  'eventid': event_id,
                                  'eventdata': request_data}
        ev = self._sc.new_event(id=event_id,
                                key=event_id, data=event_data)
        self._sc.post_event(ev)

    def update_status(self, context, notification_data):
        resource_data = notification_data['notification'][0]['data']
        notification_info = notification_data['info']
        status = resource_data['status']
        msg = ("NCO received VPN's update_status API,"
               "making an update_status RPC call to plugin for object"
               "with status %s" % (status))
        LOG(LOGGER, 'INFO', " %s " % (msg))
        rpcClient = transport.RPCClient(a_topics.VPN_NFP_PLUGIN_TOPIC)
        rpcClient.cctxt.cast(context, 'update_status',
                             status=status)

        # Sending An Event for visiblity
        if notification_data['notification'][0]['resource'].lower() ==\
                'ipsec_site_connection':
            nf_id = notification_info['context']['network_function_id']
            ipsec_id = notification_info['context']['ipsec_site_connection_id']
            service_type = notification_info['service_type']

            event_data = {'context': context.to_dict(),
                          'nf_id': nf_id,
                          'ipsec_id': ipsec_id,
                          'service_type': service_type,
                          'resource_id': ipsec_id
                          }
            ev = self._sc.new_event(id='SERVICE_CREATE_PENDING',
                                    key='SERVICE_CREATE_PENDING',
                                    data=event_data, max_times=24)
            self._sc.poll_event(ev)

    def ipsec_site_conn_deleted(self, context, notification_data):
        # Sending An Event for visiblity
        notification_info = notification_data['info']
        nf_id = notification_info['context']['network_function_id']
        ipsec_id = notification_info['context']['ipsec_site_connection_id']
        msg = ("NCO received VPN's ipsec_site_conn_deleted API,"
               "making an ipsec_site_conn_deleted RPC call to plugin for "
               " ipsec ")
        LOG(LOGGER, 'INFO', " %s " % (msg))
        rpcClient = transport.RPCClient(a_topics.VPN_NFP_PLUGIN_TOPIC)
        rpcClient.cctxt.cast(context, 'ipsec_site_conn_deleted',
                             ipsec_site_conn_id=ipsec_id)

        # Sending An Event for visiblity
        resource_id = notification_info['context']['ipsec_site_connection_id']
        service_type = notification_info['service_type']
        request_data = self._prepare_request_data(context,
                                                  nf_id,
                                                  resource_id,
                                                  ipsec_id,
                                                  service_type)
        LOG(LOGGER, 'INFO', "%s : %s " % (request_data, nf_id))

        self._trigger_service_event(context, 'SERVICE', 'SERVICE_DELETED',
                                    request_data)


class NeutronVpnaasAgent(PollEventDesc):
    def __init__(self, conf, sc):
        self._conf = conf
        self._sc = sc
        super(NeutronVpnaasAgent, self).__init__()

    def event_method_mapping(self, event_id):
        event_handler_mapping = {
            'VPN_SERVICE_SPAWNING': self.wait_for_device_ready,
            'VPN_SERVICE_DELETE_IN_PROGRESS':
                self.validate_and_process_vpn_delete_service_request
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
            LOG(LOGGER, 'DEBUG', "poll event started for %s" % (ev.id))
            self._sc.poll_event(ev, max_times=max_times)
        else:
            ev = self._sc.new_event(id=event_id, data=event_data)
            self._sc.post_event(ev)
        self._log_event_created(event_id, event_data)

    def poll_event_cancel(self, event):
        LOG(LOGGER, 'INFO', "poll event cancelled for %s" % (event.id))
        if event.id == "VPN_SERVICE_SPAWNING":
            pass
        elif event.id == "VPN_SERVICE_DELETE_IN_PROGRESS":
            data = event.data
            context = n_context.Context.from_dict(data['context'])
            vpnsvc_status = [{
                'id': data['resource']['id'],
                'status': "ERROR",
                'updated_pending_status': True,
                'ipsec_site_connections': {}}]
            vpn_plugin = transport.RPCClient(a_topics.VPN_NFP_PLUGIN_TOPIC)
            vpn_plugin.cctxt.cast(context, 'update_status',
                                  status=vpnsvc_status)

    @log_helpers.log_method_call
    def vpnservice_updated(self, context, **kwargs):
        LOG(LOGGER, 'DEBUG', "vpnservice _updated kwargs  %r" % kwargs)
        if self._is_network_function_mode_neutron(kwargs):
            if kwargs['reason'] == 'create':
                nw_fun_info =  \
                    self.validate_and_process_vpn_create_service_request(
                        context, kwargs)
                if kwargs['rsrc_type'] == 'ipsec_site_connection':
                    if ('nw_func' in nw_fun_info and
                            nw_fun_info["nw_func"]["status"] == "ACTIVE"):
                        kwargs['resource']['description'] = nw_fun_info[
                            'nw_func']['description']
                        self.call_configurator(context, kwargs)
            if kwargs['reason'] == 'delete':
                if kwargs['rsrc_type'] == 'ipsec_site_connection':
                    rpcc = transport.RPCClient(a_topics.NFP_NSO_TOPIC)
                    nw_func = rpcc.cctxt.call(
                        context, 'get_network_functions',
                        filters={'service_id': [kwargs['resource'][
                                                    'vpnservice_id']]})
                    if nw_func:
                        kwargs['resource']['description'] = nw_func[0][
                            'description']
                    self.call_configurator(context, kwargs)
                else:
                    kwargs.update({'context': context.to_dict()})
                    filters = {'service_id': [kwargs['rsrc_id']]}
                    rpcc = transport.RPCClient(a_topics.NFP_NSO_TOPIC)
                    nw_function = rpcc.cctxt.call(
                            context, 'get_network_functions', filters=filters)
                    if not nw_function:
                        vpn_plugin = transport.RPCClient(
                                a_topics.VPN_NFP_PLUGIN_TOPIC)
                        vpn_plugin.cctxt.cast(context, 'vpnservice_deleted',
                                              id=kwargs['rsrc_id'])
                        return
                    rpcc.cctxt.cast(context,
                                    'delete_network_function',
                                    network_function_id=nw_function[0]['id'])
                    self._create_event(
                        event_id='VPN_SERVICE_DELETE_IN_PROGRESS',
                        event_data=kwargs,
                        is_poll_event=True,
                        serialize=True,
                        binding_key=kwargs['resource']['id'])
        else:
            if (kwargs['reason'] == 'delete' and
                    kwargs['rsrc_type'] == 'vpn_service'):
                vpn_plugin = transport.RPCClient(
                    a_topics.VPN_NFP_PLUGIN_TOPIC)
                vpn_plugin.cctxt.cast(context, 'vpnservice_deleted',
                                      id=kwargs['resource']['id'])
            else:
                self.call_configurator(context, kwargs)

    def call_configurator(self, context, kwargs):
        '''resource_data = kwargs.get('resource')
        # Collecting db entry required by configurator.
        db = VPNPluginDbHelper(self._conf)
        db_data = db._context(context, resource_data['tenant_id'])
        # Addind service_info to neutron context and sending
        # dictionary format to the configurator.
        context_dict = context.to_dict()
        context_dict.update({'service_info': db_data})
        kwargs.update({'context': context_dict})
        resource = kwargs.get('rsrc_type')
        reason = kwargs.get('reason')
        body = common.prepare_request_data(resource, kwargs, "vpn")'''
        tenant_id = kwargs['resource']['tenant_id']
        ctx_dict, rsrc_ctx_dict = self.\
            _prepare_resource_context_dicts(context, tenant_id)
        nfp_context = {'neutron_context': ctx_dict,
                       'requester': 'nas_service'}
        resource_type = 'vpn'
        resource = kwargs['rsrc_type']
        if resource.lower() == 'ipsec_site_connection':
            ipsec_desc = self._get_dict_desc_from_string(kwargs[
                'resource']['description'])
            nf_id = ipsec_desc['network_function_id']
            ipsec_site_connection_id = kwargs['rsrc_id']
            nfp_context.update(
                {'network_function_id': nf_id,
                 'ipsec_site_connection_id': ipsec_site_connection_id})
        kwargs.update({'neutron_context': rsrc_ctx_dict})
        resource_data = kwargs
        body = common.prepare_request_data(nfp_context, resource,
                                           resource_type, resource_data)
        transport.send_request_to_configurator(self._conf,
                                               context, body,
                                               reason)

    def validate_and_process_vpn_create_service_request(self, context,
                                                        resource_data):
        """
        :param context:
        :param resource_data:
        :return:
        """
        rpcc = transport.RPCClient(a_topics.NFP_NSO_TOPIC)
        vpn_plugin = transport.RPCClient(a_topics.VPN_NFP_PLUGIN_TOPIC)
        if resource_data['rsrc_type'].lower() == 'vpn_service':
            nw_function_info = self.prepare_request_data_for_orch(
                context, resource_data['resource']['id'], resource_data)
            nw_func = rpcc.cctxt.call(context,
                                      'neutron_update_nw_function_config',
                                      network_function=nw_function_info)
            nw_function_info.update({'nw_func': nw_func, 'context':
                                     context.to_dict()})
            self._create_event(event_id='VPN_SERVICE_SPAWNING',
                               event_data=nw_function_info, is_poll_event=True,
                               serialize=True,
                               binding_key=resource_data['resource']['id'])
        else:
            nw_function_info = self.prepare_request_data_for_orch(
                context, resource_data['resource']['vpnservice_id'],
                resource_data)
            try:
                nw_func = rpcc.cctxt.call(
                            context, 'neutron_update_nw_function_config',
                            network_function=nw_function_info)
            except Exception:
                vpnconn_status = [{
                    'id': resource_data['resource']['vpnservice_id'],
                    'status':'ACTIVE',
                    'updated_pending_status':False,
                    'ipsec_site_connections':{
                        resource_data['resource']['id']: {
                            'status': "ERROR",
                            'updated_pending_status': True}}}]
                vpn_plugin.cctxt.cast(context, 'update_status',
                                      status=vpnconn_status)
                nw_function_info["status"] = "ERROR"
                return nw_function_info
            if "ipsec_service_status" in nw_func and nw_func[
                    "ipsec_service_status"] == "ACTIVE":
                nw_function_info.update(nw_func=nw_func)
            else:
                vpn_plugin.cctxt.cast(context, 'update_status',
                                      status="ERROR")
                nw_function_info["status"] = "ERROR"
        return nw_function_info

    @staticmethod
    def prepare_request_data_for_orch(context, vpnservice_id, vpn_data):
        resource = vpn_data.get('resource')
        router_id = resource.get('router_id')
        subnet = resource.get('subnet_id')
        port = resource.get('port')
        service_info = [{'router_id': router_id, 'port': port,
                         'subnet': subnet}]
        network_function_info = dict()
        desc = resource['description']
        rpcc = transport.RPCClient(a_topics.NFP_NSO_TOPIC)
        nw_func = rpcc.cctxt.call(
                        context, 'get_network_functions',
                        filters={'service_id': vpnservice_id})
        fields = desc.split(';')
        if nw_func:
            resource['description'] = nw_func[0]['description']

        for field in fields:
            if 'service_profile_id' in field:
                network_function_info['service_profile_id'] = field.split(
                    '=')[1]
        if 'service_profile_id' not in network_function_info:
            err = ("Service profile id must be specified in description")
            raise Exception(err)
        network_function_info.update(network_function_mode='neutron',
                                     tenant_id=resource['tenant_id'],
                                     service_type=vpn_data.get('rsrc_type'),
                                     service_info=service_info,
                                     resource_data=resource)
        return network_function_info

    @poll_event_desc(event="VPN_SERVICE_SPAWNING", spacing=30)
    def wait_for_device_ready(self, event):
        nw_function_info_data = event.data
        context = nw_function_info_data['context']
        nw_func = nw_function_info_data['nw_func']
        rpcc = transport.RPCClient(a_topics.NFP_NSO_TOPIC)
        nw_func = rpcc.cctxt.call(context, 'get_network_function',
                                  network_function_id=nw_func['id'])
        # (VK) - Kedar check for data sent back to plugin ???
        if nw_func['status'] == "ACTIVE":
            vpn_plugin = transport.RPCClient(a_topics.VPN_NFP_PLUGIN_TOPIC)
            self._sc.poll_event_done(event)
            vpnsvc_status = [{
                'id': nw_function_info_data['resource_data']['id'],
                'status': nw_func['status'],
                'updated_pending_status': True,
                'ipsec_site_connections': {}}]
            vpn_plugin.cctxt.cast(context, 'update_status',
                                  status=vpnsvc_status)
        elif nw_func['status'] == "ERROR":
            vpn_plugin = transport.RPCClient(a_topics.VPN_NFP_PLUGIN_TOPIC)
            self._sc.poll_event_done(event)
            vpnsvc_status = [{
                'id': nw_function_info_data['resource_data']['resource']['id'],
                'status': nw_func['status'],
                'updated_pending_status': True,
                'ipsec_site_connections': {}}]
            vpn_plugin.cctxt.cast(context, 'update_status',
                                  status=vpnsvc_status)

    @poll_event_desc(event="VPN_SERVICE_DELETE_IN_PROGRESS", spacing=30)
    def validate_and_process_vpn_delete_service_request(self, event):
        data = event.data
        context = n_context.Context.from_dict(data['context'])
        resource_data = data
        rpcc = transport.RPCClient(a_topics.NFP_NSO_TOPIC)
        nw_func = rpcc.cctxt.call(context, 'get_network_functions',
                                  filters={'service_id': [resource_data[
                                           'resource']['id']]})
        if not nw_func:
            self._sc.poll_event_done(event)
            vpn_plugin = transport.RPCClient(a_topics.VPN_NFP_PLUGIN_TOPIC)
            vpn_plugin.cctxt.cast(context, 'vpnservice_deleted',
                                  id=resource_data['resource']['id'])

    @staticmethod
    def _log_event_created(event_id, event_data):
        LOG(LOGGER, 'DEBUG', ("VPN Agent created event %s with "
            "event data %s") % (event_id, event_data))