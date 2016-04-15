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
import eventlet
from gbpservice.nfp.config_orchestrator.agent import common
from gbpservice.nfp.config_orchestrator.agent import topics as a_topics
from gbpservice.nfp.lib import transport
from neutron_vpnaas.db.vpn import vpn_db
from oslo_log import helpers as log_helpers
import oslo_messaging as messaging
from oslo_log import log as logging
from neutron_lib import exceptions as n_exec

LOG = logging.getLogger(__name__)


class VPNServiceDeleteFailed(n_exec.NeutronException):
    message = "VPN Service Deletion failed"


class VPNServiceCreateFailed(n_exec.NeutronException):
    message = "VPN Service Creation Failed"


class VpnAgent(vpn_db.VPNPluginDb, vpn_db.VPNPluginRpcDbMixin):
    RPC_API_VERSION = '1.0'
    target = messaging.Target(version=RPC_API_VERSION)

    def __init__(self, conf, sc):
        self._conf = conf
        self._sc = sc
        super(VpnAgent, self).__init__()

    @log_helpers.log_method_call
    def vpnservice_updated(self, context, **kwargs):
        LOG.debug("vpnservice _updated kwargs  %r" % kwargs)
        if self._is_network_function_mode_neutron(kwargs):
            if kwargs['reason'] == 'create':
                nw_fun_info =  \
                    self.validate_and_process_vpn_create_service_request(
                        context, kwargs)
                if kwargs['rsrc_type'] == 'ipsec_site_connection':
                    if ('status' in nw_fun_info['nw_func'] and
                        nw_fun_info['nw_func']["status"] == "ACTIVE"):
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
                        kwargs['resource']['description'] = nw_func[0]['description']
                    self.call_configurator(context, kwargs)
                else:
                    self.validate_and_process_vpn_delete_service_request(
                        context, kwargs)
        else:
            if (kwargs['reason'] == 'delete' and 
                    kwargs['rsrc_type'] == 'vpn_service'):
                vpn_plugin = transport.RPCClient(
                    a_topics.VPN_NFP_PLUGIN_TOPIC)
                vpn_plugin.cctxt.cast(context, 'vpnservice_deleted',
                                      id=resource_data['resource']['id'])
            else:
                self.call_configurator(context, kwargs)

    def call_configurator(self, context, kwargs):
        resource_data = kwargs.get('resource')
        # Collecting db entry required by configurator.
        db = self._context(context, resource_data['tenant_id'])
        # Addind service_info to neutron context and sending
        # dictionary format to the configurator.
        context_dict = context.to_dict()
        context_dict.update({'service_info': db})
        kwargs.update({'context': context_dict})
        resource = kwargs.get('rsrc_type')
        reason = kwargs.get('reason')
        body = common. prepare_request_data(resource, kwargs, "vpn")
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

    # TODO(ashu): Need to fix once vpn code gets merged in mitaka branch
    @log_helpers.log_method_call
    def update_status(self, context, **kwargs):
        status = kwargs['kwargs']['status']
        rpcClient = transport.RPCClient(a_topics.VPN_NFP_PLUGIN_TOPIC)
        msg = ("NCO received VPN's update_status API,"
               "making an update_status RPC call to plugin for %s object"
               "with status %s" % (kwargs['obj_id'], kwargs['status']))
        LOG.info(msg)
        rpcClient.cctxt.cast(context, 'update_status',
                             status=status)

    # TODO(ashu): Need to fix once vpn code gets merged in mitaka branch
    @log_helpers.log_method_call
    def ipsec_site_conn_deleted(self, context, **kwargs):
        resource_id = kwargs['kwargs']['resource_id']
        rpcClient = transport.RPCClient(a_topics.VPN_NFP_PLUGIN_TOPIC)
        msg = ("NCO received VPN's ipsec_site_conn_deleted API,"
               "making an ipsec_site_conn_deleted RPC call to plugin for "
               "%s object" % (kwargs['obj_id']))
        LOG.info(msg)
        rpcClient.cctxt.cast(context, 'ipsec_site_conn_deleted',
                             resource_id=resource_id)


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
            nw_func = self.wait_for_device_ready(context, nw_function_info)
            vpnsvc_status = [{
                'id': resource_data['resource']['id'],
                'status': nw_func['status'],
                'updated_pending_status':True,
                'ipsec_site_connections':{}}]
            vpn_plugin.cctxt.cast(context, 'update_status', status=vpnsvc_status)
        else:
            nw_function_info = self.prepare_request_data_for_orch(
                context, resource_data['resource']['vpnservice_id'],
                resource_data)
            try:
                nw_func = rpcc.cctxt.call(
                            context, 'neutron_update_nw_function_config',
                            network_function=nw_function_info)
            except Exception, err:
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
        if not 'service_profile_id' in network_function_info:
            raise
        network_function_info.update(network_function_mode='neutron',
                                     tenant_id=resource['tenant_id'],
                                     service_type=vpn_data.get('rsrc_type'),
                                     service_info=service_info,
                                     resource_data=resource)
        return network_function_info

    @staticmethod
    def wait_for_device_ready(context, nw_function_info_data):
        rpcc = transport.RPCClient(a_topics.NFP_NSO_TOPIC)
        nw_func = rpcc.cctxt.call(context, 'neutron_update_nw_function_config',
                                  network_function=nw_function_info_data)
        try:
            nw_func
        except NameError:
            raise NameError()
        time_waited = 5
        while time_waited < 300:
            nw_func = rpcc.cctxt.call(context, 'get_network_function',
                                      network_function_id=nw_func['id'])
            if nw_func['status'] == "ACTIVE":
                return nw_func
            elif nw_func['status'] == "ERROR":
                return nw_func
            eventlet.sleep(time_waited)
            time_waited += 5
        nw_function_info_data["status"] = "ERROR"
        return nw_function_info_data

    def validate_and_process_vpn_delete_service_request(self, context,
                                                        resource_data):
        rpcc = transport.RPCClient(a_topics.NFP_NSO_TOPIC)
        vpn_plugin = transport.RPCClient(a_topics.VPN_NFP_PLUGIN_TOPIC)
        nw_func = rpcc.cctxt.call(context, 'get_network_functions',
                                  filters={'service_id': [resource_data[
                                           'resource']['id']]})
        if not nw_func:
            vpn_plugin.cctxt.cast(context, 'vpnservice_deleted',
                                  id=resource_data['resource']['id'])
            return
        else:
            rpcc.cctxt.call(context, 'delete_network_function',
                            network_function_id=nw_func[0]['id'])
            try:
                self.wait_for_device_delete(context, nw_func[0]['id'],
                                            rpcc)
            except VPNServiceDeleteFailed, err:
                LOG.error("Exception %s" % err)
                status = 'ERROR'
            else:
                vpn_plugin.cctxt.cast(context, 'vpnservice_deleted',
                                      id=resource_data['resource']['id'])
                return
        LOG.error("Delete of vpnservice %s failed" % resource_data)
        vpnsvc_status = [{
                'id': resource_data['resource']['id'],
                'status': status,
                'updated_pending_status':True,
                'ipsec_site_connections':{}}]
        vpn_plugin.cctxt.cast(context, 'update_status', status=vpnsvc_status)

    @staticmethod
    def wait_for_device_delete(context, nw_fun_id, rpcc):
        time_waited = 5
        while time_waited < 300:
            nw_func = rpcc.cctxt.call(context, 'get_network_function',
                                      network_function_id=nw_fun_id)
            if not nw_func:
                return
        raise VPNServiceDeleteFailed()

    @staticmethod
    def _is_network_function_mode_neutron(kwargs):
        desc = kwargs['resource']['description']
        # Only expecting service_profile_id
        if len(desc.split(';')) > 1:
            return False
        else:
            return True



