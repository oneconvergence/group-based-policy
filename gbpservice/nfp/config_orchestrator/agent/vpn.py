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

    def _get_vpn_context(self, context, vpnservice_id,
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

    def _get_core_context(self, context, tenant_id):
        filters = {'tenant_id': [tenant_id]}
        core_context_dict = common.get_core_context(context,
                                                    filters,
                                                    self._conf.host)
        del core_context_dict['ports']
        return core_context_dict

    def _context(self, context, tenant_id, resource, resource_data):
        if context.is_admin:
            tenant_id = context.tenant_id
        if resource.lower() == 'ipsec_site_connection':
            vpn_db = self._get_vpn_context(context, resource_data[
                'vpnservice_id'], resource_data['ikepolicy_id'],
                resource_data['ipsecpolicy_id'], resource_data[
                'id'], resource_data['description'])
            core_db = self._get_core_context(context, tenant_id)
            filtered_core_db = self._filter_core_data(core_db,
                                                      vpn_data['vpnservices'])
            return vpn_db.update(filtered_core_db)
        elif resource.lower() == 'vpnservice':
            core_db = self._get_core_context(context, tenant_id)
            return self._filter_core_data(core_db, [resource_data])
        else:
            return None

    def _prepare_resource_context_dicts(self, context, tenant_id,
                                        resource, resource_data):
        # Prepare context_dict
        context = kwargs.get('context')
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
        description = self._get_dict_desc_from_string(
            nf['description'].split('\n')[1])
        resource = kwargs['rsrc_type']
        resource_data = kwargs['resource']
        resource_data['description'] = str(description)
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

    @log_helpers.log_method_call
    def vpnservice_updated(self, context, **kwargs):
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

    def _filter_core_data(self, db_data, vpnservices):
        filtered_core_data = {'subnets': [],
                              'routers': []}
        for vpnservice in vpnservices:
            subnet_id = vpnservices['subnet_id']
            for subnet in db_data['subnets']:
                if subnet['id'] == subnet_id:
                    filtered_data['subnets'].append(subnet)
            router_id = vpnservices['router_id']
            for router in db_data['routers']:
                if router['id'] == router_id:
                    filtered_data['routers'].append(router)
        return filtered_core_data

    def _get_vpnservices(self, context, tenant_id, vpnservice_id, desc):
        filters = {'tenant_id': [tenant_id],
                   'id': [vpnservice_id]}
        args = {'context': context, 'filters': filters}
        vpnservices = self._db_inst.get_vpnservices(**args)
        for vpnservice in vpnservices:
            vpnservice['description'] = desc
        return vpnservices

    def _get_ikepolicies(self, context, ikepolicy_id):
        filters = {'tenant_id': [tenant_id],
                   'id': [ikepolicy_id]}
        args = {'context': context, 'filters': filters}
        return self._db_inst.get_ikepolicies(**args)

    def _get_ipsecpolicies(self, context, ipsecpolicy_id):
        filters = {'tenant_id': [tenant_id],
                   'id': [ipsecpolicy_id]}
        args = {'context': context, 'filters': filters}
        return self._db_inst.get_ipsecpolicies(**args)

    def _get_ipsec_site_conns(self, context, ipsec_site_conn_id, desc):
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

    def _prepare_request_data(self, context,
                              nf_id, resource_id,
                              ipsec_id, service_type):
        request_data = None
        try:
            request_data = common.get_network_function_map(
                context, nf_id)
            # Adding Service Type #
            request_data.update({"service_type": service_type,
                                 "ipsec_site_connection_id": ipsec_id,
                                 "neutron_resource_id": resource_id})
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

    # TODO(ashu): Need to fix once vpn code gets merged in mitaka branch
    def ipsec_site_conn_deleted(self, context, notification_data):
        resource_data = notification_data['notification'][0]['data']
        notification_info = notification_data['info']
        ipsec_site_conn_id = resource_data['resource_id']
        msg = ("NCO received VPN's ipsec_site_conn_deleted API,"
               "making an ipsec_site_conn_deleted RPC call to plugin for "
               " ipsec ")
        LOG(LOGGER, 'INFO', " %s " % (msg))
        rpcClient = transport.RPCClient(a_topics.VPN_NFP_PLUGIN_TOPIC)
        rpcClient.cctxt.cast(context, 'ipsec_site_conn_deleted',
                             ipsec_site_conn_id=ipsec_site_conn_id)

        # Sending An Event for visiblity
        nf_id = notification_info['context']['network_function_id']
        ipsec_id = notification_info['context']['ipsec_site_connection_id']
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
