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

from gbpservice.nfp.config_orchestrator.agent import firewall
from gbpservice.nfp.config_orchestrator.agent import loadbalancer
from gbpservice.nfp.config_orchestrator.agent import notification_handler
from gbpservice.nfp.config_orchestrator.agent import vpn
import mock
from neutron import context as ctx
import unittest


class TestContext(object):

    def get_context(self):
        try:
            return ctx.Context('some_user', 'some_tenant')
        except Exception:
            return ctx.Context('some_user', 'some_tenant')


class Conf(object):

    class Test_RPC(object):

        def __init__(self):
            self.topic = 'xyz_topic'

    def __init__(self):
        self.host = 'dummy_host'
        self.backend = 'rpc'
        self.RPC = self.Test_RPC()


class RpcMethods(object):

    def cast(self, context, method, **kwargs):
        return

    def call(self, context, method, **kwargs):
        return {}


class GeneralConfigStructure(object):

    def _check_general_structure(self, request_data, rsrc_name, resource=None):
        flag = 0
        if all(key in request_data for key in ["info", "config"]):
            header_data = request_data['info']
            if all(key in header_data for key in ["context", "service_type",
                                                  "service_vendor"]):
                if not self.\
                        _check_resource_header_data(rsrc_name,
                                                    header_data["context"],
                                                    resource):
                    return False
                data = request_data['config']
                for ele in data:
                    if all(key in ele for key in ["resource",
                                                  "resource_data"]):
                        if self._check_resource_structure(rsrc_name,
                                                          ele['resource_data'],
                                                          resource):
                            flag = 1
                        else:
                            flag = 0
                    else:
                        flag = 0
        if flag == 1:
            return True
        return False

    def verify_firewall_structure(self, blob_data, resource=None):
        if all(k in blob_data for k in ["neutron_context", "host",
                                        "firewall"]):
            context = blob_data['neutron_context']
            try:
                if context['service_info']:
                    data = context['service_info']
                    if all(k in data for k in ["firewalls",
                                               "firewall_policies",
                                               "firewall_rules"]):
                        return True
            except AttributeError:
                return False
        return False

    def verify_firewall_header_data(self, data, resource=None):
        if all(k in data for k in ["neutron_context", "network_function_id",
                                   "fw_mac", "requester"]):
            if data['requester'] == 'nas_service':
                return True
            return False

    def verify_loadbalancer_header_data(self, data, resource=None):
        if all(k in data for k in ["neutron_context", "requester"]):
            if resource == "vip":
                if not all(k in data for k in ["network_function_id",
                                               "vip_id"]):
                    return False
            if data['requester'] == 'nas_service':
                return True
        return False

    def verify_vpn_header_data(self, data, resource=None):
        if all(k in data for k in ["neutron_context", "requester"]):
            if resource == "ipsec_site_connection":
                if not all(k in data for k in ["network_function_id",
                                               "ipsec_site_connection_id"]):
                    return False
            if data['requester'] == 'nas_service':
                return True
            return False

    def verify_loadbalancer_structure(self, blob_data, resource):
        if all(k in blob_data for k in ["neutron_context", resource]):
            context = blob_data["neutron_context"]
            try:
                if context['service_info']:
                    data = context['service_info']
                    if all(k in data for k in ["pools", "vips", "members",
                                               "health_monitors",
                                               "subnets", "ports"]):
                        return True
            except AttributeError:
                return False
        return False

    def verify_vpn_structure(self, blob_data, resource):
        if all(k in blob_data for k in ["neutron_context", "resource",
                                        "rsrc_id", "reason"]):
            context = blob_data["neutron_context"]
            try:
                if context['service_info']:
                    data = context['service_info']
                    if all(k in data for k in ["vpnservices",
                                               "ikepolicies",
                                               "ipsecpolicies",
                                               "ipsec_site_conns",
                                               "subnets",
                                               "routers"]):
                        return True
            except AttributeError:
                return False
        return False

    def _check_resource_structure(self, rsrc_name, data, resource=None):
        mod = self
        mod_method = getattr(mod, "verify_%s_structure" % rsrc_name)
        return mod_method(data, resource)

    def _check_resource_header_data(self, rsrc_name, data, resource):
        mod = self
        mod_method = getattr(mod, "verify_%s_header_data" % rsrc_name)
        return mod_method(data, resource)


class FirewallTestCase(unittest.TestCase):

    def setUp(self):
        self.conf = Conf()
        self.fw_handler = firewall.FwAgent(self.conf, 'sc')
        self.context = TestContext().get_context()
        self.fw = self._firewall_data()
        self.host = 'host'
        import_path = ("neutron_fwaas.db.firewall.firewall_db."
                       "Firewall_db_mixin")
        self.import_fw_api = import_path + '.get_firewalls'
        self.import_fwp_api = import_path + '.get_firewall_policies'
        self.import_fwr_api = import_path + '.get_firewall_rules'
        self.import_lib = 'gbpservice.nfp.lib.transport'

    def _firewall_data(self):
        return {'tenant_id': 123,
                'description': str({'network_function_id': 123,
                                    'provider_ptg_info': [123]})
                }

    def _cast_firewall(self, conf, context, body,
                       method_type, device_config=False,
                       network_function_event=False):
        g_cnfg = GeneralConfigStructure()
        self.assertTrue(g_cnfg._check_general_structure(body, 'firewall'))

    def test_create_firewall(self):
        import_send = self.import_lib + '.send_request_to_configurator'
        with mock.patch(self.import_fw_api) as gfw,\
                mock.patch(self.import_fwp_api) as gfwp,\
                mock.patch(self.import_fwr_api) as gfwr,\
                mock.patch(import_send) as mock_send:
            gfw.return_value = []
            gfwp.return_value = []
            gfwr.return_value = []
            mock_send.side_effect = self._cast_firewall
            self.fw_handler.create_firewall(self.context, self.fw, self.host)

    def test_delete_firewall(self):
        import_send = self.import_lib + '.send_request_to_configurator'
        with mock.patch(self.import_fw_api) as gfw,\
                mock.patch(self.import_fwp_api) as gfwp,\
                mock.patch(self.import_fwr_api) as gfwr,\
                mock.patch(import_send) as mock_send:
            gfw.return_value = []
            gfwp.return_value = []
            gfwr.return_value = []
            mock_send.side_effect = self._cast_firewall
            self.fw_handler.delete_firewall(self.context, self.fw, self.host)


class LoadBalanceTestCase(unittest.TestCase):

    def setUp(self):
        self.conf = Conf()
        self.lb_handler = loadbalancer.LbAgent(self.conf, 'sc')
        self.context = TestContext().get_context()
        import_path = ("neutron_lbaas.db.loadbalancer.loadbalancer_db."
                       "LoadBalancerPluginDb")
        self.import_gp_api = import_path + '.get_pools'
        self.import_gv_api = import_path + '.get_vips'
        self.import_gm_api = import_path + '.get_members'
        self.import_ghm_api = import_path + '.get_health_monitors'
        self.import_lib = 'gbpservice.nfp.lib.transport'
        self._call = 'oslo_messaging.rpc.client._CallContext.call'

    def _cast_loadbalancer(self, conf, context, body,
                           method_type, device_config=False,
                           network_function_event=False):
        g_cnfg = GeneralConfigStructure()
        try:
            resource = body['config'][0]['resource']
            if resource == 'pool_health_monitor':
                resource = 'health_monitor'
            self.assertTrue(g_cnfg._check_general_structure(
                body, 'loadbalancer', resource))
        except Exception:
            self.assertTrue(False)

    def _call_core_plugin_data(self, context, method, **kwargs):
        return []

    def _vip_data(self):
        vip_desc = str({'network_function_id': 123})
        return {'tenant_id': 123,
                'description': vip_desc,
                'id': 123
                }

    def test_create_vip(self):
        import_send = self.import_lib + '.send_request_to_configurator'
        with mock.patch(self.import_gp_api) as gp,\
                mock.patch(self.import_gv_api) as gv,\
                mock.patch(self.import_gm_api) as gm,\
                mock.patch(self.import_ghm_api) as ghm,\
                mock.patch(self._call) as mock_call,\
                mock.patch(import_send) as mock_send:
            gp.return_value = []
            gv.return_value = []
            gm.return_value = []
            ghm.return_value = []
            mock_call.side_effect = self._call_core_plugin_data
            mock_send.side_effect = self._cast_loadbalancer
            vip = self._vip_data()
            self.lb_handler.create_vip(self.context, vip)

    def test_delete_vip(self):
        import_send = self.import_lib + '.send_request_to_configurator'
        with mock.patch(self.import_gp_api) as gp,\
                mock.patch(self.import_gv_api) as gv,\
                mock.patch(self.import_gm_api) as gm,\
                mock.patch(self.import_ghm_api) as ghm,\
                mock.patch(self._call) as mock_call,\
                mock.patch(import_send) as mock_send:
            gp.return_value = []
            gv.return_value = []
            gm.return_value = []
            ghm.return_value = []
            mock_call.side_effect = self._call_core_plugin_data
            mock_send.side_effect = self._cast_loadbalancer
            vip = self._vip_data()
            self.lb_handler.delete_vip(self.context, vip)

    def test_create_pool(self):
        import_send = self.import_lib + '.send_request_to_configurator'
        with mock.patch(self.import_gp_api) as gp,\
                mock.patch(self.import_gv_api) as gv,\
                mock.patch(self.import_gm_api) as gm,\
                mock.patch(self.import_ghm_api) as ghm,\
                mock.patch(self._call) as mock_call,\
                mock.patch(import_send) as mock_send:
            gp.return_value = []
            gv.return_value = []
            gm.return_value = []
            ghm.return_value = []
            mock_call.side_effect = self._call_core_plugin_data
            mock_send.side_effect = self._cast_loadbalancer
            pool = {'tenant_id': 123}
            driver_name = "dummy"
            self.lb_handler.create_pool(self.context, pool, driver_name)

    def test_delete_pool(self):
        import_send = self.import_lib + '.send_request_to_configurator'
        with mock.patch(self.import_gp_api) as gp,\
                mock.patch(self.import_gv_api) as gv,\
                mock.patch(self.import_gm_api) as gm,\
                mock.patch(self.import_ghm_api) as ghm,\
                mock.patch(self._call) as mock_call,\
                mock.patch(import_send) as mock_send:
            gp.return_value = []
            gv.return_value = []
            gm.return_value = []
            ghm.return_value = []
            mock_call.side_effect = self._call_core_plugin_data
            mock_send.side_effect = self._cast_loadbalancer
            pool = {'id': 123, 'tenant_id': 123}
            self.lb_handler.delete_pool(self.context, pool)

    def test_create_member(self):
        import_send = self.import_lib + '.send_request_to_configurator'
        with mock.patch(self.import_gp_api) as gp,\
                mock.patch(self.import_gv_api) as gv,\
                mock.patch(self.import_gm_api) as gm,\
                mock.patch(self.import_ghm_api) as ghm,\
                mock.patch(self._call) as mock_call,\
                mock.patch(import_send) as mock_send:
            gp.return_value = []
            gv.return_value = []
            gm.return_value = []
            ghm.return_value = []
            mock_call.side_effect = self._call_core_plugin_data
            mock_send.side_effect = self._cast_loadbalancer
            member = {'tenant_id': 123}
            self.lb_handler.create_member(self.context, member)

    def test_delete_member(self):
        import_send = self.import_lib + '.send_request_to_configurator'
        with mock.patch(self.import_gp_api) as gp,\
                mock.patch(self.import_gv_api) as gv,\
                mock.patch(self.import_gm_api) as gm,\
                mock.patch(self.import_ghm_api) as ghm,\
                mock.patch(self._call) as mock_call,\
                mock.patch(import_send) as mock_send:
            gp.return_value = []
            gv.return_value = []
            gm.return_value = []
            ghm.return_value = []
            mock_call.side_effect = self._call_core_plugin_data
            mock_send.side_effect = self._cast_loadbalancer
            member = {'id': 123, 'tenant_id': 123}
            self.lb_handler.delete_member(self.context, member)

    def test_create_pool_health_monitor(self):
        import_send = self.import_lib + '.send_request_to_configurator'
        with mock.patch(self.import_gp_api) as gp,\
                mock.patch(self.import_gv_api) as gv,\
                mock.patch(self.import_gm_api) as gm,\
                mock.patch(self.import_ghm_api) as ghm,\
                mock.patch(self._call) as mock_call,\
                mock.patch(import_send) as mock_send:
            gp.return_value = []
            gv.return_value = []
            gm.return_value = []
            ghm.return_value = []
            mock_call.side_effect = self._call_core_plugin_data
            mock_send.side_effect = self._cast_loadbalancer
            hm = {'tenant_id': 123}
            pool_id = "123"
            self.lb_handler.create_pool_health_monitor(
                self.context, hm, pool_id)

    def test_delete_pool_health_monitor(self):
        import_send = self.import_lib + '.send_request_to_configurator'
        with mock.patch(self.import_gp_api) as gp,\
                mock.patch(self.import_gv_api) as gv,\
                mock.patch(self.import_gm_api) as gm,\
                mock.patch(self.import_ghm_api) as ghm,\
                mock.patch(self._call) as mock_call,\
                mock.patch(import_send) as mock_send:
            gp.return_value = []
            gv.return_value = []
            gm.return_value = []
            ghm.return_value = []
            mock_call.side_effect = self._call_core_plugin_data
            mock_send.side_effect = self._cast_loadbalancer
            hm = {'id': 123, 'tenant_id': 123}
            pool_id = 123
            self.lb_handler.delete_pool_health_monitor(
                self.context, hm, pool_id)


class VPNTestCase(unittest.TestCase):

    def setUp(self):
        self.conf = Conf()
        self.vpn_handler = vpn.VpnAgent(self.conf, 'sc')
        self.context = TestContext().get_context()
        import_path = "neutron_vpnaas.db.vpn.vpn_db.VPNPluginDb"
        self.import_gvs_api = import_path + '.get_vpnservices'
        self.import_gikp_api = import_path + '.get_ikepolicies'
        self.import_gipsp_api = import_path + '.get_ipsecpolicies'
        self.import_gisc_api = import_path + '.get_ipsec_site_connections'
        self.import_lib = 'gbpservice.nfp.lib.transport'
        self._call = 'oslo_messaging.rpc.client._CallContext.call'

    def _cast_vpn(self, conf, context, body,
                  method_type, device_config=False,
                  network_function_event=False):
        g_cnfg = GeneralConfigStructure()
        try:
            resource = body['config'][0]['resource']
            self.assertTrue(g_cnfg._check_general_structure(
                body, 'vpn', resource))
        except Exception:
            self.assertTrue(False)

    def _call_core_plugin_data(self, context, method, **kwargs):
        return []

    def _prepare_request_data(self, reason, rsrc_type):
        resource = {'tenant_id': 123,
                    'id': 123
                    }
        if rsrc_type == 'ipsec_site_connection':
            resource.update(self._ipsec_data())
        return {'resource': resource,
                'rsrc_type': rsrc_type,
                'reason': reason,
                'rsrc_id': 123
                }

    def _ipsec_data(self):
        ipsec_desc = ("network_function_id=123;"
                      "ipsec_site_connection_id=123")
        return {'description': ipsec_desc}

    def test_update_vpnservice_for_vpnservice(self):
        import_send = self.import_lib + '.send_request_to_configurator'
        with mock.patch(self.import_gvs_api) as gvs,\
                mock.patch(self.import_gikp_api) as gikp,\
                mock.patch(self.import_gipsp_api) as gipsp,\
                mock.patch(self.import_gisc_api) as gisc,\
                mock.patch(self._call) as mock_call,\
                mock.patch(import_send) as mock_send:
            gvs.return_value = []
            gikp.return_value = []
            gipsp.return_value = []
            gisc.return_value = []
            mock_call.side_effect = self._call_core_plugin_data
            mock_send.side_effect = self._cast_vpn
            rsrc_type = 'vpnservice'
            reason = 'create'
            kwargs = self._prepare_request_data(reason, rsrc_type)
            self.vpn_handler.vpnservice_updated(self.context, **kwargs)

    def test_update_vpnservice_for_ipsec_site_connection(self):
        import_send = self.import_lib + '.send_request_to_configurator'
        with mock.patch(self.import_gvs_api) as gvs,\
                mock.patch(self.import_gikp_api) as gikp,\
                mock.patch(self.import_gipsp_api) as gipsp,\
                mock.patch(self.import_gisc_api) as gisc,\
                mock.patch(self._call) as mock_call,\
                mock.patch(import_send) as mock_send:
            gvs.return_value = []
            gikp.return_value = []
            gipsp.return_value = []
            gisc.return_value = []
            mock_call.side_effect = self._call_core_plugin_data
            mock_send.side_effect = self._cast_vpn
            rsrc_type = 'ipsec_site_connection'
            reason = 'delete'
            kwargs = self._prepare_request_data(reason, rsrc_type)
            self.vpn_handler.vpnservice_updated(self.context, **kwargs)


class NotificationHandlerTestCase(unittest.TestCase):

    def setUp(self):
        self.conf = Conf()
        self.n_handler = notification_handler.NotificationAgent(
            self.conf, 'sc')
        self.context = TestContext().get_context()
        self.n_fw = ("gbpservice.nfp.config_orchestrator.agent"
                     ".firewall.FirewallNotifier")

    def _fw_nh_api(self, context, notification_data):
        return

    def test_network_function_notification(self):
        notification_data = \
            {'info':
                {'service_type': 'firewall'},
             'notification': [
                    {'data':
                     {'notification_type': 'set_firewall_status'}
                     }]
             }
        with mock.patch(self.n_fw + '.set_firewall_status') as mock_fw:
            mock_fw.side_effect = self._fw_nh_api
            self.n_handler.network_function_notification(self.context,
                                                         notification_data)

if __name__ == '__main__':
    unittest.main()
