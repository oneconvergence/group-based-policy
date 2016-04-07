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
from gbpservice.nfp.config_orchestrator.agent import loadbalancer as lb
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
            if all(key in header_data for key in ["version", "service_type"]):
                data = request_data['config']
                for ele in data:
                    if all(key in ele for key in ["resource", "kwargs"]):
                        if self._check_resource_structure(rsrc_name,
                                                          ele['kwargs'],
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
        if all(k in blob_data for k in ["context", "host", "firewall"]):
            context = blob_data['context']
            try:
                if context['service_info']:
                    data = context['service_info']
                    if all(k in data for k in ["firewalls",
                                               "firewall_policies",
                                               "firewall_rules",
                                               "subnets", "routers",
                                               "ports"]):
                        return True
            except AttributeError:
                return False
        return False

    def verify_loadbalancer_structure(self, blob_data, resource):
        if all(k in blob_data for k in ["context", resource]):
            context = blob_data['context']
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
        if all(k in blob_data for k in ["context", "resource"]):
            context = blob_data['context']
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


class FirewallTestCase(unittest.TestCase):

    def _cast_delete_firewall(self, context, method, **kwargs):
        g_cnfg = GeneralConfigStructure()
        request_data = kwargs.get('body')
        if method == 'delete_network_function_config' and \
                g_cnfg._check_general_structure(request_data, 'firewall'):
            return

        print("delete method for firewall:FAIL")
        return

    def _cast_create_firewall(self, context, method, **kwargs):
        g_cnfg = GeneralConfigStructure()
        request_data = kwargs.get('body')
        if method == 'create_network_function_config' and \
                g_cnfg._check_general_structure(request_data, 'firewall'):
            return

        print("create method for firewall:FAIL")
        return

    def _prepare_firewall_request_data(self):
        context = TestContext().get_context()
        context.is_admin = False
        fw = {'tenant_id': 123}
        host = ''
        conf = Conf()
        sc = {}
        return context, fw, sc, conf, host

    def test_create_firewall(self):
        import_db = 'neutron_fwaas.db.firewall.firewall_db.\
Firewall_db_mixin.'

        with mock.patch(import_db + 'get_firewalls') as gfw,\
                mock.patch(import_db + 'get_firewall_policies') as gfwp,\
                mock.patch(import_db + 'get_firewall_rules') as gfwr,\
                mock.patch(
                    'oslo_messaging.rpc.client._CallContext.call') as call,\
                mock.patch(
                    'oslo_messaging.rpc.client._CallContext.cast') as cast:
            gfw.return_value = True
            gfwp.return_value = True
            gfwr.return_value = True
            call.side_effect = RpcMethods().call
            cast.side_effect = self._cast_create_firewall
            context, fw, sc, conf, host = self.\
                _prepare_firewall_request_data()
            fw_handler = firewall.FwAgent(conf, sc)
            fw_handler.create_firewall(context, fw, host)

    def test_delete_firewall(self):
        import_db = 'neutron_fwaas.db.firewall.firewall_db.\
Firewall_db_mixin.'

        with mock.patch(import_db + 'get_firewalls') as get_firewalls,\
                mock.patch(import_db + 'get_firewall_policies') as gfwp,\
                mock.patch(import_db + 'get_firewall_rules') as gfwr,\
                mock.patch(import_db + '_core_plugin') as _cp,\
                mock.patch(
                    'oslo_messaging.rpc.client._CallContext.call') as call,\
                mock.patch(
                    'oslo_messaging.rpc.client._CallContext.cast') as cast:
            get_firewalls.return_value = True
            gfwp.return_value = True
            gfwr.return_value = True
            _cp.return_value = True
            call.side_effect = RpcMethods().call
            cast.side_effect = self._cast_delete_firewall
            context, fw, sc, conf, host = self.\
                _prepare_firewall_request_data()
            fw_handler = firewall.FwAgent(conf, sc)
            fw_handler.delete_firewall(context, fw, host)


class LoadBalanceTestCase(unittest.TestCase):

    def _cast_delete(self, context, method, **kwargs):
        g_cnfg = GeneralConfigStructure()
        request_data = kwargs.get('body')
        try:
            resource = request_data['config'][0]['resource']
            if method == 'delete_network_function_config' and \
                    g_cnfg._check_general_structure(request_data,
                                                    'loadbalancer',
                                                    resource):
                return
            return
        except Exception:
            return

    def _cast_create(self, context, method, **kwargs):
        g_cnfg = GeneralConfigStructure()
        request_data = kwargs.get('body')
        try:
            resource = request_data['config'][0]['resource']
            if resource == 'pool_health_monitor':
                resource = 'health_monitor'
            if method == 'create_network_function_config' and \
                    g_cnfg._check_general_structure(request_data,
                                                    'loadbalancer',
                                                    resource):
                return
            print("create method for %s:FAIL" % (resource))
            return
        except Exception:
            print("create method for %s:FAIL" % (resource))
            return

    def _prepare_request_data(self):
        context = TestContext().get_context()
        context.is_admin = False
        conf = Conf()
        sc = {}
        return context, sc, conf

    def test_create_vip(self):
        import_db = 'neutron_lbaas.db.loadbalancer.loadbalancer_db\
.LoadBalancerPluginDb.'
        with mock.patch(import_db + 'get_pools') as get_pools,\
                mock.patch(import_db + 'get_vips') as get_vips,\
                mock.patch(import_db + 'get_members') as get_members,\
                mock.patch(import_db + 'get_health_monitors') as get_hm,\
                mock.patch(
                    'oslo_messaging.rpc.client._CallContext.call') as call,\
                mock.patch(
                    'oslo_messaging.rpc.client._CallContext.cast') as cast:
            get_pools.return_value = True
            get_vips.return_value = True
            get_members.return_value = True
            get_hm.return_value = True
            call.side_effect = RpcMethods().call
            cast.side_effect = self._cast_create

            context, sc, conf = self._prepare_request_data()
            vip = {'tenant_id': 123}
            lb_handler = lb.LbAgent(conf, sc)
            lb_handler.create_vip(context, vip)

    def test_create_pool(self):
        import_db = 'neutron_lbaas.db.loadbalancer.loadbalancer_db\
.LoadBalancerPluginDb.'
        with mock.patch(import_db + 'get_pools') as get_pools,\
                mock.patch(import_db + 'get_vips') as get_vips,\
                mock.patch(import_db + 'get_members') as get_members,\
                mock.patch(import_db + 'get_health_monitors') as get_hm,\
                mock.patch(
                    'oslo_messaging.rpc.client._CallContext.call') as call,\
                mock.patch(
                    'oslo_messaging.rpc.client._CallContext.cast') as cast:
            get_pools.return_value = True
            get_vips.return_value = True
            get_members.return_value = True
            get_hm.return_value = True
            call.side_effect = RpcMethods().call
            cast.side_effect = self._cast_create

            context, sc, conf = self._prepare_request_data()
            pool = {'tenant_id': 123}
            driver_name = "dummy"
            lb_handler = lb.LbAgent(conf, sc)
            lb_handler.create_pool(context, pool, driver_name)

    def test_create_member(self):
        import_db = 'neutron_lbaas.db.loadbalancer.loadbalancer_db\
.LoadBalancerPluginDb.'
        with mock.patch(import_db + 'get_pools') as get_pools,\
                mock.patch(import_db + 'get_vips') as get_vips,\
                mock.patch(import_db + 'get_members') as get_members,\
                mock.patch(import_db + 'get_health_monitors') as get_hm,\
                mock.patch(
                    'oslo_messaging.rpc.client._CallContext.call') as call,\
                mock.patch(
                    'oslo_messaging.rpc.client._CallContext.cast') as cast:
            get_pools.return_value = True
            get_vips.return_value = True
            get_members.return_value = True
            get_hm.return_value = True
            call.side_effect = RpcMethods().call
            cast.side_effect = self._cast_create

            context, sc, conf = self._prepare_request_data()
            member = {'tenant_id': 123}
            lb_handler = lb.LbAgent(conf, sc)
            lb_handler.create_member(context, member)

    def test_create_pool_health_monitor(self):
        import_db = 'neutron_lbaas.db.loadbalancer.loadbalancer_db\
.LoadBalancerPluginDb.'
        with mock.patch(import_db + 'get_pools') as get_pools,\
                mock.patch(import_db + 'get_vips') as get_vips,\
                mock.patch(import_db + 'get_members') as get_members,\
                mock.patch(import_db + 'get_health_monitors') as get_hm,\
                mock.patch(
                    'oslo_messaging.rpc.client._CallContext.call') as call,\
                mock.patch(
                    'oslo_messaging.rpc.client._CallContext.cast') as cast:
            get_pools.return_value = True
            get_vips.return_value = True
            get_members.return_value = True
            get_hm.return_value = True
            call.side_effect = RpcMethods().call
            cast.side_effect = self._cast_create

            context, sc, conf = self._prepare_request_data()
            hm = {'tenant_id': 123}
            pool_id = "123"
            lb_handler = lb.LbAgent(conf, sc)
            lb_handler.create_pool_health_monitor(context, hm, pool_id)

    def test_delete_vip(self):
        import_db = 'neutron_lbaas.db.loadbalancer.loadbalancer_db\
.LoadBalancerPluginDb.'
        with mock.patch(import_db + 'get_pools') as get_pools,\
                mock.patch(import_db + 'get_vips') as get_vips,\
                mock.patch(import_db + 'get_members') as get_members,\
                mock.patch(import_db + 'get_health_monitors') as get_hm,\
                mock.patch(
                    'oslo_messaging.rpc.client._CallContext.call') as call,\
                mock.patch(
                    'oslo_messaging.rpc.client._CallContext.cast') as cast:
            get_pools.return_value = True
            get_vips.return_value = True
            get_members.return_value = True
            get_hm.return_value = True
            call.side_effect = RpcMethods().call
            cast.side_effect = self._cast_delete

            context, sc, conf = self._prepare_request_data()
            vip = {'id': 123, 'tenant_id': 123}
            lb_handler = lb.LbAgent(conf, sc)
            lb_handler.delete_vip(context, vip)

    def test_delete_pool(self):
        import_db = 'neutron_lbaas.db.loadbalancer.loadbalancer_db\
.LoadBalancerPluginDb.'
        with mock.patch(import_db + 'get_pools') as get_pools,\
                mock.patch(import_db + 'get_vips') as get_vips,\
                mock.patch(import_db + 'get_members') as get_members,\
                mock.patch(import_db + 'get_health_monitors') as get_hm,\
                mock.patch(
                    'oslo_messaging.rpc.client._CallContext.call') as call,\
                mock.patch(
                    'oslo_messaging.rpc.client._CallContext.cast') as cast:
            get_pools.return_value = True
            get_vips.return_value = True
            get_members.return_value = True
            get_hm.return_value = True
            call.side_effect = RpcMethods().call
            cast.side_effect = self._cast_delete

            context, sc, conf = self._prepare_request_data()
            pool = {'id': 123, 'tenant_id': 123}
            lb_handler = lb.LbAgent(conf, sc)
            lb_handler.delete_pool(context, pool)

    def test_delete_member(self):
        import_db = 'neutron_lbaas.db.loadbalancer.loadbalancer_db\
.LoadBalancerPluginDb.'
        with mock.patch(import_db + 'get_pools') as get_pools,\
                mock.patch(import_db + 'get_vips') as get_vips,\
                mock.patch(import_db + 'get_members') as get_members,\
                mock.patch(import_db + 'get_health_monitors') as get_hm,\
                mock.patch(
                    'oslo_messaging.rpc.client._CallContext.call') as call,\
                mock.patch(
                    'oslo_messaging.rpc.client._CallContext.cast') as cast:
            get_pools.return_value = True
            get_vips.return_value = True
            get_members.return_value = True
            get_hm.return_value = True
            call.side_effect = RpcMethods().call
            cast.side_effect = self._cast_delete

            context, sc, conf = self._prepare_request_data()
            member = {'id': 123, 'tenant_id': 123}
            lb_handler = lb.LbAgent(conf, sc)
            lb_handler.delete_member(context, member)

    def test_delete_pool_health_monitor(self):
        import_db = 'neutron_lbaas.db.loadbalancer.loadbalancer_db\
.LoadBalancerPluginDb.'
        with mock.patch(import_db + 'get_pools') as get_pools,\
                mock.patch(import_db + 'get_vips') as get_vips,\
                mock.patch(import_db + 'get_members') as get_members,\
                mock.patch(import_db + 'get_health_monitors') as get_hm,\
                mock.patch(
                    'oslo_messaging.rpc.client._CallContext.call') as call,\
                mock.patch(
                    'oslo_messaging.rpc.client._CallContext.cast') as cast:
            get_pools.return_value = True
            get_vips.return_value = True
            get_members.return_value = True
            get_hm.return_value = True
            call.side_effect = RpcMethods().call
            cast.side_effect = self._cast_delete

            context, sc, conf = self._prepare_request_data()
            hm = {'id': 123, 'tenant_id': 123}
            pool_id = 123
            lb_handler = lb.LbAgent(conf, sc)
            lb_handler.delete_pool_health_monitor(context, hm, pool_id)


class VPNTestCase(unittest.TestCase):

    def _prepare_request_data(self):
        context = TestContext().get_context()
        context.is_admin = False
        conf = Conf()
        sc = {}
        return context, sc, conf

    def _prepare_request_data1(self, reason, rsrc_type):
        resource = {'tenant_id': 123,
                    'rsrc_type': rsrc_type,
                    'reason': reason}
        return resource

    def _cast(self, context, method, **kwargs):
        g_cnfg = GeneralConfigStructure()
        request_data = kwargs.get('body')
        try:
            resource = request_data['config'][0]['resource']
            if (method == 'delete_network_function_config' or
                    method == 'create_network_function_config') \
                    and g_cnfg._check_general_structure(request_data,
                                                        'vpn', resource):
                return
            print("method for %s:FAIL" % (resource))
            return
        except Exception:
            print("method for %s:FAIL" % (resource))
            return

    def test_update_vpnservice(self):
        import_db = 'neutron_vpnaas.db.vpn.vpn_db.VPNPluginDb.'
        with mock.patch(import_db + 'get_vpnservices') as gvs,\
                mock.patch(import_db + 'get_ikepolicies') as gikp,\
                mock.patch(import_db + 'get_ipsecpolicies') as gipp,\
                mock.patch(import_db + 'get_ipsec_site_connections') as gisc,\
                mock.patch(
                    'oslo_messaging.rpc.client._CallContext.call') as call,\
                mock.patch(
                    'oslo_messaging.rpc.client._CallContext.cast') as cast:
            gvs.return_value = True
            gikp.return_value = True
            gipp.return_value = True
            gisc.return_value = True
            call.side_effect = RpcMethods().call
            cast.side_effect = self._cast

            context, sc, conf = self._prepare_request_data()
            rsrc_types = ['ipsec', 'vpnservice']
            reasons = ['create', 'delete']
            for rsrc_type in rsrc_types:
                for reason in reasons:
                    if rsrc_type == 'vpnservice' and reason == 'delete':
                        continue
                    else:
                        resource = self._prepare_request_data1(reason,
                                                               rsrc_type)
                        vpn_handler = vpn.VpnAgent(conf, sc)
                        vpn_handler.vpnservice_updated(context,
                                                       resource=resource)


if __name__ == '__main__':
    unittest.main()
