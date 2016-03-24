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
from neutron_vpnaas.db.vpn import vpn_db
from gbpservice.nfp.config_orchestrator.agent.common import *
from gbpservice.nfp.config_orchestrator.agent import topics as a_topics
from gbpservice.nfp.lib.transport import *
from neutron import context as n_context
from neutron.common import exceptions as n_exec

LOG = logging.getLogger(__name__)


class VPNServiceDeleteFailed(n_exec.NeutronException):
    message = "VPN Service Deletion failed"


class VPNServiceCreateFailed(n_exec.NeutronException):
    message = "VPN Service Creation Failed"


def update_status(**kwargs):
    rpcClient = RPCClient(a_topics.VPN_NFP_PLUGIN_TOPIC)
    context = kwargs.get('context')
    rpc_ctx = n_context.Context.from_dict(context)
    del kwargs['context']
    rpcClient.cctxt.cast(rpc_ctx, 'update_status',
                         status=kwargs['status'])


class VpnAgent(vpn_db.VPNPluginDb, vpn_db.VPNPluginRpcDbMixin):
    RPC_API_VERSION = '1.0'
    _target = target.Target(version=RPC_API_VERSION)

    def __init__(self, conf, sc):
        self._conf = conf
        self._sc = sc
        super(VpnAgent, self).__init__()

    def vpnservice_updated(self, context, **kwargs):
        LOG.error("kwargs  %r" % kwargs)
        if self._is_network_function_mode_neutron(kwargs):
            if kwargs['reason'] == 'create':
                nw_fun_info =  \
                    self.validate_and_process_vpn_create_service_request(
                        context, kwargs)
                LOG.error("nw_func_info  %r" % nw_fun_info)
                if kwargs['rsrc_type'] == 'ipsec_site_connection':
                    if 'status' in nw_fun_info and nw_fun_info["status"] == \
                            "ACTIVE":
                        kwargs['resource']['description'] = nw_fun_info[
                            'description']
                        self.call_configurator(context, kwargs)
            if kwargs['reason'] == 'delete':
                if kwargs['rsrc_type'] == 'ipsec_site_connection':
                    rpcc = RPCClient(a_topics.NFP_NSO_TOPIC)
                    nw_func = rpcc.cctxt.call(
                        context, 'get_network_functions',
                        filters={'service_id': [kwargs['resource'][
                                                    'vpnservice_id']]})
                    kwargs['resource']['description'] = nw_func['description']
                    self.call_configurator(context, kwargs)
                else:
                    self.validate_and_process_vpn_delete_service_request(
                        context, kwargs)
        else:
            self.call_configurator(context, kwargs)

    def call_configurator(self, context, kwargs):
        resource_data = kwargs.get('resource')
        db = self._context(context, resource_data['tenant_id'])
        context_dict = context.to_dict()
        context_dict.update({'service_info': db})
        kwargs.update({'context': context_dict})
        resource = resource_data['rsrc_type']
        reason = resource_data['reason']
        body = prepare_request_data(resource, kwargs, "vpn")
        send_request_to_configurator(self._conf, context, body, reason)

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
        core_context_dict = get_core_context(context, filters, self._conf.host)
        del core_context_dict['ports']
        return core_context_dict

    def validate_and_process_vpn_create_service_request(self, context,
                                                        resource_data):
        """
        :param context:
        :param resource_data:
        :return:
        """
        rpcc = RPCClient(a_topics.VPN_NFP_PLUGIN_TOPIC)
        nw_function_info = self.prepare_request_data_for_orch(resource_data)
        if resource_data['rsrc_type'].lower() == 'vpn_service':
            nw_func = self.wait_for_device_ready(context, nw_function_info)
            rpcc.cctxt.cast(context, 'update_status', status=nw_func['status'])
        else:
            try:
                nw_func = rpcc.cctxt.call(
                            context, 'neutron_update_nw_function_config',
                            nw_function_info)
            except Exception, err:
                rpcc.cctxt.cast(context, 'update_status', status="ERROR")
                nw_function_info["status"] = "ERROR"
                return nw_function_info
            if "ipsec_service_status" in nw_func and nw_function_info[
                    "ipsec_service_status"] == "ACTIVE":
                nw_function_info.update(nw_func)
            else:
                rpcc.cctxt.cast(context, 'update_status', status="ERROR")
                nw_function_info["status"] = "ERROR"
        return nw_function_info

    @staticmethod
    def prepare_request_data_for_orch(vpn_data):
        resource = vpn_data.get('resource')
        router_id = resource.get('router_id')
        subnet = resource.get('subnet_id')
        port = resource.get('port')
        service_info = [{'router_id': router_id, 'port': port,
                         'subnet': subnet}]
        network_function_info = dict()
        desc = resource['description']
        fields = desc.split(';')
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
        rpcc = RPCClient(a_topics.NFP_NSO_TOPIC)
        nw_func = rpcc.cctxt.call(context, 'neutron_update_nw_function_config',
                                  nw_function_info_data)
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
        rpcc = RPCClient(a_topics.NFP_NSO_TOPIC)
        nw_func = rpcc.cctxt.call(context, 'get_network_functions',
                                  filters={'service_id': [resource_data[
                                           'resource']['id']]})
        if not nw_func:
            rpcc.cctxt.cast(context, 'update_status', status="ERROR")
        else:
            rpcc.cctxt.call(context, 'delete_network_function',
                            network_function_id=nw_func['id'])
            try:
                self.wait_for_device_delete(context, nw_func['id'])
            except VPNServiceDeleteFailed, err:
                rpcc.cctxt.cast(context, 'update_status', status="ERROR")
            rpcc.cctxt.cast(context, 'update_status', status="DELETED")

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



