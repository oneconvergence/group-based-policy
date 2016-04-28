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

import copy
from gbpservice.nfp.config_orchestrator.agent import common
from gbpservice.nfp.config_orchestrator.agent import topics as a_topics
from gbpservice.nfp.core import common as nfp_common
from gbpservice.nfp.lib import transport

from neutron_vpnaas.db.vpn import vpn_db

from oslo_log import helpers as log_helpers
from oslo_log import log as oslo_logging
import oslo_messaging as messaging

LOGGER = oslo_logging.getLogger(__name__)
LOG = nfp_common.log

"""
RPC handler for VPN service
"""


class VpnAgent(vpn_db.VPNPluginDb, vpn_db.VPNPluginRpcDbMixin):
    RPC_API_VERSION = '1.0'
    target = messaging.Target(version=RPC_API_VERSION)

    def __init__(self, conf, sc):
        self._conf = conf
        self._sc = sc
        super(VpnAgent, self).__init__()

    def _get_dict_desc_from_string(self, vpn_svc):
        svc_desc = vpn_svc.split(";")
        desc = {}
        for ele in svc_desc:
            s_ele = ele.split("=")
            desc.update({s_ele[0]: s_ele[1]})
        return desc

    def _prepare_resource_context_dicts(self, context, tenant_id):
        # Prepare context_dict
        ctx_dict = context.to_dict()
        # Collecting db entry required by configurator.
        # Addind service_info to neutron context and sending
        # dictionary format to the configurator.
        db = self._context(context, tenant_id)
        rsrc_ctx_dict = copy.deepcopy(ctx_dict)
        rsrc_ctx_dict.update({'service_info': db})
        return ctx_dict, rsrc_ctx_dict

    def _data_wrapper(self, context, tenant_id, **kwargs):

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
        return body

    @log_helpers.log_method_call
    def vpnservice_updated(self, context, **kwargs):
        reason = kwargs['reason']
        body = self._data_wrapper(context, kwargs[
            'resource']['tenant_id'], **kwargs)
        transport.send_request_to_configurator(self._conf,
                                               context, body,
                                               reason)

    def _context(self, context, tenant_id):
        if context.is_admin:
            tenant_id = context.tenant_id
        filters = {'tenant_id': [tenant_id]}
        db = self._get_vpn_context(context, filters)
        db.update(self._get_core_context(context, filters))
        return db

    def _get_vpn_context(self, context, filters):
        args = {'context': context, 'filters': filters}
        db_data = super(VpnAgent, self)
        return {'vpnservices': db_data.get_vpnservices(**args),
                'ikepolicies': db_data.get_ikepolicies(**args),
                'ipsecpolicies': db_data.get_ipsecpolicies(**args),
                'ipsec_site_conns': db_data.get_ipsec_site_connections(**args)}

    def _get_core_context(self, context, filters):
        core_context_dict = common.get_core_context(context,
                                                    filters,
                                                    self._conf.host)
        del core_context_dict['ports']
        return core_context_dict


class VpnNotifier(object):

    def __init__(self, conf, sc):
        self._sc = sc
        self._conf = conf

    def _prepare_request_data(self, context, nf_id,
                              ipsec_id, service_type):
        request_data = None
        try:
            request_data = common.get_network_function_map(
                context, nf_id)
            # Adding Service Type #
            request_data.update({"service_type": service_type,
                                 "ipsec_site_connection_id": ipsec_id})
        except Exception:
            return request_data
        return request_data

    def _trigger_service_event(self, context, event_type, event_id,
                               request_data):
        event_data = {'resource': None,
                      'context': context}
        event_data['resource'] = {'eventtype': event_type,
                                  'eventid': event_id,
                                  'eventdata': request_data}
        ev = self._sc.new_event(id=event_id,
                                key=event_id, data=event_data)
        self._sc.post_event(ev)

    # TODO(ashu): Need to fix once vpn code gets merged in mitaka branch
    # TODO(akash): Event for service create/delete not implemented here
    # Need to do that
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
        if resource_data['resource'].lower() is\
                'ipsec_site_connection':
            nf_id = notification_info['context']['network_function_id']
            ipsec_id = notification_info['context']['ipsec_site_connection_id']
            service_type = notification_info['service_type']
            request_data = self._prepare_request_data(context, nf_id,
                                                      ipsec_id, service_type)
            LOG(LOGGER, 'INFO', "%s : %s " % (request_data, nf_id))

            self._trigger_service_event(context, 'SERVICE', 'SERVICE_CREATED',
                                        request_data)

    # TODO(ashu): Need to fix once vpn code gets merged in mitaka branch
    def ipsec_site_conn_deleted(self, context, notification_data):
        resource_data = notification_data['notification'][0]['data']
        notification_info = notification_data['info']
        resource_id = resource_data['resource_id']
        msg = ("NCO received VPN's ipsec_site_conn_deleted API,"
               "making an ipsec_site_conn_deleted RPC call to plugin for "
               " ipsec ")
        LOG(LOGGER, 'INFO', " %s " % (msg))
        rpcClient = transport.RPCClient(a_topics.VPN_NFP_PLUGIN_TOPIC)
        rpcClient.cctxt.cast(context, 'ipsec_site_conn_deleted',
                             id=resource_id)

        # Sending An Event for visiblity
        nf_id = notification_info['context']['network_function_id']
        ipsec_id = notification_info['context']['ipsec_site_connection_id']
        service_type = notification_info['service_type']
        request_data = self._prepare_request_data(context, nf_id,
                                                  ipsec_id, service_type)
        LOG(LOGGER, 'INFO', "%s : %s " % (request_data, nf_id))

        self._trigger_service_event(context, 'SERVICE', 'SERVICE_DELETED',
                                    request_data)
