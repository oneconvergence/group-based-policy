import unittest
import os
import sys
import json
import mock
from mock import patch
from gbpservice.nfp.config_orchestrator.agent import firewall
from gbpservice.nfp.config_orchestrator.agent import loadbalancer as lb
from gbpservice.nfp.config_orchestrator.agent import vpn
from gbpservice.nfp.config_orchestrator.agent import generic as gc
from gbpservice.nfp.config_orchestrator.agent import rpc_cb
from gbpservice.nfp.config_orchestrator.agent import topics
from gbpservice.nfp.core import main as controller
from gbpservice.nfp.core import cfg as core_cfg
from neutron import manager
from oslo_messaging import target
import threading
from neutron.common import rpc as n_rpc
from neutron.agent.common import config
from neutron import context as ctx
from neutron.common import config as common_config
from oslo_config import cfg
import time
from multiprocessing import Process
import httplib

n_count = 0

class TestContext:

    def get_context(self):
        try:
            return ctx.Context('some_user', 'some_tenant')
        except:
            return ctx.Context('some_user', 'some_tenant')

class Conf:
    class Test_RPC:
        def __init__(self):
            self.topic = 'xyz_topic'
    def __init__(self):
        self.host = 'dummy_host'
        self.backend = 'rpc'
        self.RPC = self.Test_RPC()

class RpcMethods:
    def cast(self, context, method, **kwargs):
        #print("cast method:Success")
        return
    def call(self, context, method, **kwargs):
        #print("call method:Success")
        return {}


class GeneralConfigStructure:
    def _check_general_structure(self, request_data, rsrc_name, resource=None):
        flag = 0
        if all(key in request_data for key in ["info", "config"]):
            header_data = request_data['info']
            if all(key in header_data for key in ["version", "service_type"]):
                data = request_data['config']
                for ele in data:
                    if all(key in ele for key in ["resource", "kwargs"]):
                        if self._check_resource_structure(rsrc_name, ele['kwargs'], resource):
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
        mod_method = getattr(mod, "verify_%s_structure"%rsrc_name)
        return mod_method(data, resource)


class FirewallTestCase(unittest.TestCase):

    def _cast_delete_firewall(self, context, method, **kwargs):
        g_cnfg = GeneralConfigStructure()
        request_data = kwargs.get('body')
        if method == 'delete_network_function_config' and \
            g_cnfg._check_general_structure(request_data, 'firewall') :
            #print ("delete method for firewall:SUCCESS")
            return

        print("delete method for firewall:FAIL")
        return

    def _cast_create_firewall(self, context, method, **kwargs):
        g_cnfg = GeneralConfigStructure()
        request_data = kwargs.get('body')
        if method == 'create_network_function_config' and \
            g_cnfg._check_general_structure(request_data, 'firewall') :
            #print ("create method for firewall:SUCCESS")
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
        import_ca = 'gbpservice.nfp.config_orchestrator.'

        with patch(import_db + 'get_firewalls') as gfw,\
                patch(import_db + 'get_firewall_policies') as gfwp,\
                patch(import_db + 'get_firewall_rules') as gfwr,\
                patch('oslo_messaging.rpc.client._CallContext.call') as call,\
                patch('oslo_messaging.rpc.client._CallContext.cast') as cast:
            call.side_effect = RpcMethods().call
            cast.side_effect = self._cast_create_firewall
            context, fw, sc, conf, host = self.\
                _prepare_firewall_request_data()
            fw_handler = firewall.FwAgent(conf, sc)
            fw_handler.create_firewall(context, fw, host)

    def test_delete_firewall(self):
        import_db = 'neutron_fwaas.db.firewall.firewall_db.\
Firewall_db_mixin.'

        with patch(import_db + 'get_firewalls') as get_firewalls,\
                patch(import_db + 'get_firewall_policies') as gfwp,\
                patch(import_db + 'get_firewall_rules') as gfwr,\
                patch(import_db + '_core_plugin') as _cp,\
                patch('oslo_messaging.rpc.client._CallContext.call') as call,\
                patch('oslo_messaging.rpc.client._CallContext.cast') as cast:
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
        try :
            resource = request_data['config'][0]['resource']
            if method == 'delete_network_function_config' and \
                    g_cnfg._check_general_structure(request_data, 'loadbalancer', resource) :
                #print ("delete method for %s:SUCCESS"%(resource))
                return
            #print("delete method for %s:FAIL"%(resource))
            return
        except :
            #print("delete method for %s:FAIL"%(resource))
            return

    def _cast_create(self, context, method, **kwargs):
        g_cnfg = GeneralConfigStructure()
        request_data = kwargs.get('body')
        try :
            resource = request_data['config'][0]['resource']
            if method == 'create_network_function_config' and \
                g_cnfg._check_general_structure(request_data, 'loadbalancer', resource) :
                #print ("create method for %s:SUCCESS"%(resource))
                return
            print("create method for %s:FAIL"%(resource))
            return
        except :
            print("create method for %s:FAIL"%(resource))
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
        import_config_agent = 'gbpservice.nfp.config_orchestrator.'
        with patch(import_db + 'get_pools') as get_pools,\
                patch(import_db + 'get_vips') as get_vips,\
                patch(import_db + 'get_members') as get_members,\
                patch(import_db + 'get_health_monitors') as get_hm,\
                patch('oslo_messaging.rpc.client._CallContext.call') as call,\
                patch('oslo_messaging.rpc.client._CallContext.cast') as cast:
            call.side_effect = RpcMethods().call
            cast.side_effect = self._cast_create

            context, sc, conf = self._prepare_request_data()
            vip = {'tenant_id': 123}
            lb_handler = lb.LbAgent(conf, sc)
            lb_handler.create_vip(context, vip)

    def test_create_pool(self):
        import_db = 'neutron_lbaas.db.loadbalancer.loadbalancer_db\
.LoadBalancerPluginDb.'
        import_config_agent = 'gbpservice.nfp.config_orchestrator.'
        with patch(import_db + 'get_pools') as get_pools,\
                patch(import_db + 'get_vips') as get_vips,\
                patch(import_db + 'get_members') as get_members,\
                patch(import_db + 'get_health_monitors') as get_hm,\
                patch('oslo_messaging.rpc.client._CallContext.call') as call,\
                patch('oslo_messaging.rpc.client._CallContext.cast') as cast:
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
        import_config_agent = 'gbpservice.nfp.config_orchestrator.'
        with patch(import_db + 'get_pools') as get_pools,\
                patch(import_db + 'get_vips') as get_vips,\
                patch(import_db + 'get_members') as get_members,\
                patch(import_db + 'get_health_monitors') as get_hm,\
                patch('oslo_messaging.rpc.client._CallContext.call') as call,\
                patch('oslo_messaging.rpc.client._CallContext.cast') as cast:
            call.side_effect = RpcMethods().call
            cast.side_effect = self._cast_create

            context, sc, conf = self._prepare_request_data()
            member = {'tenant_id': 123}
            lb_handler = lb.LbAgent(conf, sc)
            lb_handler.create_member(context, member)

    def test_create_pool_health_monitor(self):
        import_db = 'neutron_lbaas.db.loadbalancer.loadbalancer_db\
.LoadBalancerPluginDb.'
        import_config_agent = 'gbpservice.nfp.config_orchestrator.'
        with patch(import_db + 'get_pools') as get_pools,\
                patch(import_db + 'get_vips') as get_vips,\
                patch(import_db + 'get_members') as get_members,\
                patch(import_db + 'get_health_monitors') as get_hm,\
                patch('oslo_messaging.rpc.client._CallContext.call') as call,\
                patch('oslo_messaging.rpc.client._CallContext.cast') as cast:
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
        import_config_agent = 'gbpservice.nfp.config_orchestrator.'
        with patch(import_db + 'get_pools') as get_pools,\
                patch(import_db + 'get_vips') as get_vips,\
                patch(import_db + 'get_members') as get_members,\
                patch(import_db + 'get_health_monitors') as get_hm,\
                patch('oslo_messaging.rpc.client._CallContext.call') as call,\
                patch('oslo_messaging.rpc.client._CallContext.cast') as cast:
            call.side_effect = RpcMethods().call
            cast.side_effect = self._cast_delete

            context, sc, conf = self._prepare_request_data()
            vip = {'id': 123, 'tenant_id': 123}
            lb_handler = lb.LbAgent(conf, sc)
            lb_handler.delete_vip(context, vip)

    def test_delete_pool(self):
        import_db = 'neutron_lbaas.db.loadbalancer.loadbalancer_db\
.LoadBalancerPluginDb.'
        import_config_agent = 'gbpservice.nfp.config_orchestrator.'
        with patch(import_db + 'get_pools') as get_pools,\
                patch(import_db + 'get_vips') as get_vips,\
                patch(import_db + 'get_members') as get_members,\
                patch(import_db + 'get_health_monitors') as get_hm,\
                patch('oslo_messaging.rpc.client._CallContext.call') as call,\
                patch('oslo_messaging.rpc.client._CallContext.cast') as cast:
            call.side_effect = RpcMethods().call
            cast.side_effect = self._cast_delete

            context, sc, conf = self._prepare_request_data()
            pool = {'id': 123, 'tenant_id': 123}
            lb_handler = lb.LbAgent(conf, sc)
            lb_handler.delete_pool(context, pool)

    def test_delete_member(self):
        import_db = 'neutron_lbaas.db.loadbalancer.loadbalancer_db\
.LoadBalancerPluginDb.'
        import_config_agent = 'gbpservice.nfp.config_orchestrator.'
        with patch(import_db + 'get_pools') as get_pools,\
                patch(import_db + 'get_vips') as get_vips,\
                patch(import_db + 'get_members') as get_members,\
                patch(import_db + 'get_health_monitors') as get_hm,\
                patch('oslo_messaging.rpc.client._CallContext.call') as call,\
                patch('oslo_messaging.rpc.client._CallContext.cast') as cast:
            call.side_effect = RpcMethods().call
            cast.side_effect = self._cast_delete

            context, sc, conf = self._prepare_request_data()
            member = {'id': 123, 'tenant_id': 123}
            lb_handler = lb.LbAgent(conf, sc)
            lb_handler.delete_member(context, member)

    def test_delete_pool_health_monitor(self):
        import_db = 'neutron_lbaas.db.loadbalancer.loadbalancer_db\
.LoadBalancerPluginDb.'
        import_config_agent = 'gbpservice.nfp.config_orchestrator.'
        with patch(import_db + 'get_pools') as get_pools,\
                patch(import_db + 'get_vips') as get_vips,\
                patch(import_db + 'get_members') as get_members,\
                patch(import_db + 'get_health_monitors') as get_hm,\
                patch('oslo_messaging.rpc.client._CallContext.call') as call,\
                patch('oslo_messaging.rpc.client._CallContext.cast') as cast:
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
        try :
            resource = request_data['config'][0]['resource']
            if (method == 'delete_network_function_config' \
                   or method == 'create_network_function_config') \
                       and g_cnfg._check_general_structure(request_data, 'vpn', resource) :
                #print ("method for %s:SUCCESS"%(resource))
                return
            print("method for %s:FAIL"%(resource))
            return
        except :
            print("method for %s:FAIL"%(resource))
            return

    def test_update_vpnservice(self):
        import_db = 'neutron_vpnaas.db.vpn.vpn_db.VPNPluginDb.'
        import_ca = 'gbpservice.nfp.config_orchestrator.'
        with patch(import_db + 'get_vpnservices') as gvs,\
                patch(import_db + 'get_ikepolicies') as gikp,\
                patch(import_db + 'get_ipsecpolicies') as gipp,\
                patch(import_db + 'get_ipsec_site_connections') as gisc,\
                patch('oslo_messaging.rpc.client._CallContext.call') as call,\
                patch('oslo_messaging.rpc.client._CallContext.cast') as cast:
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

class NotificationTestCase(unittest.TestCase):

    def _get_context(self):
        context = TestContext().get_context()
        context.is_admin = False
        context_dict = context.to_dict()
        return context_dict

    def _prepare_request_data(self, receiver, resource,
                              method, kwargs):
        response_data = [
            {'receiver': receiver,  # <neutron/orchestrator>,
             'resource': resource,  # <firewall/vpn/loadbalancer/generic>,
             'method': method,  # <notification method name>,
             'kwargs': kwargs
             }
        ]
        for ele in response_data:
            ele['kwargs'].update({'context': self._get_context()})
        return response_data

    def _prepare_request_data_orchestrator(self, receiver, resource,
                              method, kwargs):
        response_data = [
            {'receiver': receiver,  # <neutron/orchestrator>,
             'resource': resource,  # <firewall/vpn/loadbalancer/generic>,
             'method': method,  # <notification method name>,
             'kwargs': [kwargs]
             }
        ]
        for ele in response_data:
            for e in ele['kwargs'] :
                e.update({'context': self._get_context()})
        return response_data

    def _call_orchestrator(self, context, method, **kwargs):
        if method == 'get_notifications':
            print("call method: orchestrator")
            return self.\
                _prepare_request_data_orchestrator(
                    'orchestrator',
                    'interface',
                    'network_function_device_notification',
                    {})

    def _call_neutron_firewall_status(self, context, method, **kwargs):
        if method == 'get_notifications':
            print("cast method:neutron")
            kwargs = {'host': '', 'firewall_id': 123, 'status': 'Active'}
            return self._prepare_request_data('neutron', 'firewall',
                                              'set_firewall_status',
                                              kwargs)


    def test_rpc_pull_event_orchestrator(self):
        import_ca = 'gbpservice.nfp.config_orchestrator.'
        with patch('oslo_messaging.rpc.client._CallContext.call') as call,\
                patch('oslo_messaging.rpc.client._CallContext.cast') as cast:
            call.side_effect = self._call_orchestrator
            cast.side_effect = RpcMethods().cast
            ev = ''
            sc = {}
            conf = Conf()
            rpc_cb_handler = rpc_cb.RpcCallback(sc, conf)
            rpc_cb_handler.rpc_pull_event(ev)

    def test_rpc_pull_event_neutron(self):
        import_ca = 'gbpservice.nfp.config_orchestrator.'
        with patch('oslo_messaging.rpc.client._CallContext.call') as call,\
                patch('oslo_messaging.rpc.client._CallContext.cast') as cast:
            call.side_effect = self._call_neutron_firewall_status
            cast.side_effect = RpcMethods().cast
            ev = ''
            sc = {}
            conf = Conf()
            rpc_cb_handler = rpc_cb.RpcCallback(sc, conf)
            rpc_cb_handler.rpc_pull_event(ev)

if __name__ == '__main__':
    unittest.main()
