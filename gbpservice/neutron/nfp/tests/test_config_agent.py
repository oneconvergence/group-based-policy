import unittest
import os
import sys
import json
import mock
from mock import patch
from gbpservice.neutron.nfp.config_agent import firewall
from gbpservice.neutron.nfp.config_agent import loadbalancer as lb
from gbpservice.neutron.nfp.config_agent import vpn
from gbpservice.neutron.nfp.config_agent import generic as gc
from gbpservice.neutron.nfp.config_agent import rpc_cb
from gbpservice.neutron.nfp.config_agent import topics
from gbpservice.neutron.nfp.core import main as controller
from gbpservice.neutron.nfp.core import cfg as core_cfg
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


class FirewallTestCase(unittest.TestCase):

    def _verify_body_structure(self, path, body):
        flag = 0
        default_path_prefix = 'network_function_config'
        default_paths_suffix = ['create', 'delete']
        path = path.split('_',  1)
        if default_paths_suffix.__contains__(path[0]) and\
                default_path_prefix == path[1]:
            if 'request_data' in body:
                rdata = body['request_data']
                if all(k in rdata for k in ["info", "config"]):
                    hd = rdata['info']
                    if all(k in hd for k in ["version", "service_type"]):
                        d = rdata['config']
                        for ele in d:
                            if all(k in ele for k in ["resource", "kwargs"]):
                                if self._verify_firewall_data(ele['kwargs']):
                                    flag = 1
                                else:
                                    flag = 0
                            else:
                                flag = 0
        if flag == 1:
            return True
        return False

    def _verify_firewall_data(self, blob_data):

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

    def _verify_firewall_data_for_post(self, path, body, delete=False):
        if self._verify_body_structure(path, body):
            if delete:
                print("delete_firewall_verified:Success")
                return (httplib.OK, "delete_firewall_verified:Success")
            print("create_firewall_verified:Success")
            return (httplib.OK, "create_firewall_verified:Success")
        if delete:
            print("delete_firewall_verified:Failed")
            return (httplib.OK, "delete_firewall_verified:Failed")
        print("create_firewall_verified:Failed")
        return (httplib.NOT_FOUND, "create_firewall_verified:Failed")

    def _prepare_firewall_request_data(self):
        context = TestContext().get_context()
        context.__setattr__('service_info', {})
        context.is_admin = False
        fw = {'tenant_id': 123}
        host = ''
        conf = {}
        sc = {}
        return context, fw, sc, conf, host

    def test_create_firewall(self):
        import_db = 'neutron_fwaas.db.firewall.firewall_db.\
Firewall_db_mixin.'
        import_ca = 'gbpservice.neutron.nfp.config_agent.'

        with patch(import_db + 'get_firewalls') as gfw,\
                patch(import_db + 'get_firewall_policies') as gfwp,\
                patch(import_db + 'get_firewall_rules') as gfwr,\
                patch(import_db + '_core_plugin') as _cp,\
                patch(import_ca + 'RestClientOverUnix.post') as post:

            post.side_effect = self._verify_firewall_data_for_post
            context, fw, sc, conf, host = self.\
                _prepare_firewall_request_data()
            fw_handler = firewall.FwAgent(conf, sc)
            fw_handler.create_firewall(context, fw, host)

    def test_delete_firewall(self):
        import_db = 'neutron_fwaas.db.firewall.firewall_db.\
Firewall_db_mixin.'
        import_cfg_agent = 'gbpservice.neutron.nfp.config_agent.'

        with patch(import_db + 'get_firewalls') as get_firewalls,\
                patch(import_db + 'get_firewall_policies') as gfwp,\
                patch(import_db + 'get_firewall_rules') as gfwr,\
                patch(import_db + '_core_plugin') as _cp,\
                patch(import_cfg_agent + 'RestClientOverUnix.post') as post:

            post.side_effect = self._verify_firewall_data_for_post
            context, fw, sc, conf, host = self.\
                _prepare_firewall_request_data()
            fw_handler = firewall.FwAgent(conf, sc)
            fw_handler.delete_firewall(context, fw, host)


class LoadBalanceTestCase(unittest.TestCase):

    def _verify_body_structure(self, path, body):
        flag = 0
        default_path_prefix = 'network_function_config'
        default_paths_suffix = ['create', 'delete']
        path = path.split('_', 1)
        if default_paths_suffix.__contains__(path[0]) and\
                default_path_prefix == path[1]:
            if 'request_data' in body:
                rdata = body['request_data']
                if all(k in rdata for k in ["info", "config"]):
                    hd = rdata['info']
                    if all(k in hd for k in ["version", "service_type"]):
                        d = rdata['config']
                        for ele in d:
                            if all(k in ele for k in ["resource", "kwargs"]):
                                if self._verify_loadbalancer_data(
                                        ele['kwargs'], ele['resource']):
                                    flag = 1
                                else:
                                    flag = 0
                            else:
                                flag = 0
        if flag == 1:
            return True
        return False

    def _verify_loadbalancer_data(self, blob_data, resource):
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

    def _verify_delete_post(self, path, body, delete=False):
        if self._verify_body_structure(path, body):
            '''
            This case resource type will be same for whole list##
            '''
            resource = body['request_data']['config'][0]['resource']
            if delete:
                print("delete_%s_verified:Success" % (resource))
                return (httplib.OK, "delete_%s_verified:Success" % (resource))
            print("create_%s_verified:Success" % (resource))
            return (httplib.OK, "create_%s_verified:Success" % (resource))
        if delete:
            print("delete_%s_verified:Failed" % (resource))
            return (httplib.NOT_FOUND, "delete_%s_verified:Failed" % (
                resource))
        print("create_%s_verified:Failed" % (resource))
        return (httplib.NOT_FOUND, "create_%s_verified:Failed" % (resource))

    def _prepare_request_data(self):
        context = TestContext().get_context()
        context.__setattr__('service_info', {})
        context.is_admin = False
        conf = {}
        sc = {}
        return context, sc, conf

    def test_create_vip(self):
        import_db = 'neutron_lbaas.db.loadbalancer.loadbalancer_db\
.LoadBalancerPluginDb.'
        import_config_agent = 'gbpservice.neutron.nfp.config_agent.'
        with patch(import_db + 'get_pools') as get_pools,\
                patch(import_db + 'get_vips') as get_vips,\
                patch(import_db + 'get_members') as get_members,\
                patch(import_db + 'get_health_monitors') as get_hm,\
                patch(import_db + '_core_plugin') as _core_plugin,\
                patch(import_config_agent + 'RestClientOverUnix.post') as post:

            post.side_effect = self._verify_delete_post
            context, sc, conf = self._prepare_request_data()
            vip = {'tenant_id': 123}
            lb_handler = lb.LbAgent(conf, sc)
            lb_handler.create_vip(context, vip)

    def test_create_pool(self):
        import_db = 'neutron_lbaas.db.loadbalancer.loadbalancer_db\
.LoadBalancerPluginDb.'
        import_config_agent = 'gbpservice.neutron.nfp.config_agent.'
        with patch(import_db + 'get_pools') as get_pools,\
                patch(import_db + 'get_vips') as get_vips,\
                patch(import_db + 'get_members') as get_members,\
                patch(import_db + 'get_health_monitors') as get_hm,\
                patch(import_db + '_core_plugin') as _core_plugin,\
                patch(import_config_agent + 'RestClientOverUnix.post') as post:

            post.side_effect = self._verify_delete_post
            context, sc, conf = self._prepare_request_data()
            pool = {'tenant_id': 123}
            driver_name = "dummy"
            lb_handler = lb.LbAgent(conf, sc)
            lb_handler.create_pool(context, pool, driver_name)

    def test_create_member(self):
        import_db = 'neutron_lbaas.db.loadbalancer.loadbalancer_db\
.LoadBalancerPluginDb.'
        import_config_agent = 'gbpservice.neutron.nfp.config_agent.'
        with patch(import_db + 'get_pools') as get_pools,\
                patch(import_db + 'get_vips') as get_vips,\
                patch(import_db + 'get_members') as get_members,\
                patch(import_db + 'get_health_monitors') as get_hm,\
                patch(import_db + '_core_plugin') as _core_plugin,\
                patch(import_config_agent + 'RestClientOverUnix.post') as post:

            post.side_effect = self._verify_delete_post
            context, sc, conf = self._prepare_request_data()
            member = {'tenant_id': 123}
            lb_handler = lb.LbAgent(conf, sc)
            lb_handler.create_member(context, member)

    def test_create_pool_health_monitor(self):
        import_db = 'neutron_lbaas.db.loadbalancer.loadbalancer_db\
.LoadBalancerPluginDb.'
        import_config_agent = 'gbpservice.neutron.nfp.config_agent.'
        with patch(import_db + 'get_pools') as get_pools,\
                patch(import_db + 'get_vips') as get_vips,\
                patch(import_db + 'get_members') as get_members,\
                patch(import_db + 'get_health_monitors') as get_hm,\
                patch(import_db + '_core_plugin') as _core_plugin,\
                patch(import_config_agent + 'RestClientOverUnix.post') as post:

            post.side_effect = self._verify_delete_post
            context, sc, conf = self._prepare_request_data()
            hm = {'tenant_id': 123}
            pool_id = "123"
            lb_handler = lb.LbAgent(conf, sc)
            lb_handler.create_pool_health_monitor(context, hm, pool_id)

    def test_delete_vip(self):
        import_db = 'neutron_lbaas.db.loadbalancer.loadbalancer_db\
.LoadBalancerPluginDb.'
        import_config_agent = 'gbpservice.neutron.nfp.config_agent.'
        with patch(import_db + 'get_pools') as get_pools,\
                patch(import_db + 'get_vips') as get_vips,\
                patch(import_db + 'get_members') as get_members,\
                patch(import_db + 'get_health_monitors') as get_hm,\
                patch(import_db + '_core_plugin') as _core_plugin,\
                patch(import_config_agent + 'RestClientOverUnix.post') as post:

            post.side_effect = self._verify_delete_post
            context, sc, conf = self._prepare_request_data()
            vip = {'id': 123, 'tenant_id': 123}
            lb_handler = lb.LbAgent(conf, sc)
            lb_handler.delete_vip(context, vip)

    def test_delete_pool(self):
        import_db = 'neutron_lbaas.db.loadbalancer.loadbalancer_db\
.LoadBalancerPluginDb.'
        import_config_agent = 'gbpservice.neutron.nfp.config_agent.'
        with patch(import_db + 'get_pools') as get_pools,\
                patch(import_db + 'get_vips') as get_vips,\
                patch(import_db + 'get_members') as get_members,\
                patch(import_db + 'get_health_monitors') as get_hm,\
                patch(import_db + '_core_plugin') as _core_plugin,\
                patch(import_config_agent + 'RestClientOverUnix.post') as post:

            post.side_effect = self._verify_delete_post
            context, sc, conf = self._prepare_request_data()
            pool = {'id': 123, 'tenant_id': 123}
            lb_handler = lb.LbAgent(conf, sc)
            lb_handler.delete_pool(context, pool)

    def test_delete_member(self):
        import_db = 'neutron_lbaas.db.loadbalancer.loadbalancer_db\
.LoadBalancerPluginDb.'
        import_config_agent = 'gbpservice.neutron.nfp.config_agent.'
        with patch(import_db + 'get_pools') as get_pools,\
                patch(import_db + 'get_vips') as get_vips,\
                patch(import_db + 'get_members') as get_members,\
                patch(import_db + 'get_health_monitors') as get_hm,\
                patch(import_db + '_core_plugin') as _core_plugin,\
                patch(import_config_agent + 'RestClientOverUnix.post') as post:

            post.side_effect = self._verify_delete_post
            context, sc, conf = self._prepare_request_data()
            member = {'id': 123, 'tenant_id': 123}
            lb_handler = lb.LbAgent(conf, sc)
            lb_handler.delete_member(context, member)

    def test_delete_pool_health_monitor(self):
        import_db = 'neutron_lbaas.db.loadbalancer.loadbalancer_db\
.LoadBalancerPluginDb.'
        import_config_agent = 'gbpservice.neutron.nfp.config_agent.'
        with patch(import_db + 'get_pools') as get_pools,\
                patch(import_db + 'get_vips') as get_vips,\
                patch(import_db + 'get_members') as get_members,\
                patch(import_db + 'get_health_monitors') as get_hm,\
                patch(import_db + '_core_plugin') as _core_plugin,\
                patch(import_config_agent + 'RestClientOverUnix.post') as post:

            post.side_effect = self._verify_delete_post
            context, sc, conf = self._prepare_request_data()
            hm = {'id': 123, 'tenant_id': 123}
            pool_id = 123
            lb_handler = lb.LbAgent(conf, sc)
            lb_handler.delete_pool_health_monitor(context, hm, pool_id)


class VPNTestCase(unittest.TestCase):

    def _verify_body_structure(self, path, body):
        flag = 0
        default_path_prefix = 'network_function_config'
        default_paths_suffix = ['create', 'delete']
        path = path.split('_', 1)
        if default_paths_suffix.__contains__(path[0]) and\
                default_path_prefix == path[1]:
            if 'request_data' in body:
                rdata = body['request_data']
                if all(k in rdata for k in ["info", "config"]):
                    hd = rdata['info']
                    if all(k in hd for k in ["version", "service_type"]):
                        d = rdata['config']
                        for ele in d:
                            if all(k in ele for k in ["resource", "kwargs"]):
                                if self._verify_vpn_data(
                                        ele['kwargs'], ele['resource']):
                                    flag = 1
                                else:
                                    flag = 0
                            else:
                                flag = 0
        if flag == 1:
            return True
        return False

    def _verify_vpn_data(self, blob_data, resource):
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

    def _verify_delete_post(self, path, body, delete=False):
        if self._verify_body_structure(path, body):
            '''
            This case resource type will be same for whole list##
            '''
            resource = body['request_data']['config'][0]['resource']
            if delete:
                print("delete_%s_verified:Success" % (resource))
                return (httplib.OK, "delete_%s_verified:Success" % (resource))
            print("create_%s_verified:Success" % (resource))
            return (httplib.OK, "create_%s_verified:Success" % (resource))
        if delete:
            print("delete_%s_verified:Failed" % (resource))
            return (httplib.NOT_FOUND, "delete_%s_verified:Failed" % (
                resource))
        print("create_%s_verified:Failed" % (resource))
        return (httplib.NOT_FOUND, "create_%s_verified:Failed" % (resource))

    def _prepare_request_data(self):
        context = TestContext().get_context()
        context.__setattr__('service_info', {})
        context.is_admin = False
        conf = {}
        sc = {}
        return context, sc, conf

    def _prepare_request_data1(self, reason, rsrc_type):
        resource = {'tenant_id': 123,
                    'rsrc_type': rsrc_type,
                    'reason': reason}
        return resource

    def test_update_vpnservice(self):
        import_db = 'neutron_vpnaas.db.vpn.vpn_db.VPNPluginDb.'
        import_ca = 'gbpservice.neutron.nfp.config_agent.'
        with patch(import_db + 'get_vpnservices') as gvs,\
                patch(import_db + 'get_ikepolicies') as gikp,\
                patch(import_db + 'get_ipsecpolicies') as gipp,\
                patch(import_db + 'get_ipsec_site_connections') as gisc,\
                patch(import_ca + 'vpn.VpnAgent.core_plugin') as _cp,\
                patch(import_ca + 'RestClientOverUnix.post') as post:
            post.side_effect = self._verify_delete_post
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


class GenericConfigTestCase(unittest.TestCase):

    def _verify_body_structure(self, path, body):
        flag = 0
        default_path_prefix = 'network_function_device_config'
        default_paths_suffix = ['create', 'delete']
        path = path.split('_', 1)
        if default_paths_suffix.__contains__(path[0]) and\
                default_path_prefix == path[1]:
            if 'request_data' in body:
                rdata = body['request_data']
                if all(k in rdata for k in ["info", "config"]):
                    hd = rdata['info']
                    if all(k in hd for k in ["version"]):
                        d = rdata['config']
                        for ele in d:
                            if all(k in ele for k in ["resource", "kwargs"]):
                                flag = 1
                            else:
                                flag = 0
        if flag == 1:
            return True
        return False

    def _prepare_request_data(self):
        context = TestContext().get_context()
        context.__setattr__('service_info', {})
        context.is_admin = False
        conf = {}
        sc = {}
        return context, sc, conf

    def _prepare_request_data1(self):
        request_data = {'info': {
            'version': 'v1'},
            'config': [{
                'kwargs': {},
                'resource': ''}]
        }
        return {'request_data': request_data}

    def _verify_delete_post(self, path, body, delete=False):
        if self._verify_body_structure(path, body):
            '''
            This case resource type will be same for whole list##
            '''
            if delete:
                print("delete_network_function_device_config_verified:Success")
                return (
                    httplib.OK,
                    "delete_network_function_device_config_verified:Success")
            print("create_network_function_device_config_verified:Success")
            return (httplib.OK,
                    "create_network_function_device_config_verified:Success")
        if delete:
            print("delete_network_function_device_config_verified:Failed")
            return (httplib.NOT_FOUND,
                    "delete_network_function_device_config_verified:Failed")
        print("create_network_function_device_config_verified:Failed")
        return (httplib.NOT_FOUND,
                "create_network_function_device_config_verified:Failed")

    def test_create_network_function_device_config(self):
        import_ca = 'gbpservice.neutron.nfp.config_agent.'
        with patch(import_ca + 'RestClientOverUnix.post') as post:
            post.side_effect = self._verify_delete_post
            context, sc, conf = self._prepare_request_data()
            request_data = self._prepare_request_data1()
            gc_handler = gc.GcAgent(conf, sc)
            gc_handler.create_network_function_device_config(context,
                                                             request_data)

    def test_delete_network_function_device_config(self):
        import_ca = 'gbpservice.neutron.nfp.config_agent.'
        with patch(import_ca + 'RestClientOverUnix.post') as post:
            post.side_effect = self._verify_delete_post
            context, sc, conf = self._prepare_request_data()
            request_data = self._prepare_request_data1()
            gc_handler = gc.GcAgent(conf, sc)
            gc_handler.delete_network_function_device_config(context,
                                                             request_data)


class NotificationTestCase(unittest.TestCase):

    def _get_context(self):
        context = TestContext().get_context()
        context.__setattr__('service_info', {})
        context.is_admin = False
        return context

    def _prepare_request_data(self, receiver, resource,
                              method, kwargs):
        response_data = {'response_data': [
            {'receiver': receiver,  # <neutron/orchestrator>,
             'resource': resource,  # <firewall/vpn/loadbalancer/generic>,
             'method': method,  # <notification method name>,
             'kwargs': kwargs
             }
        ]}
        for ele in response_data['response_data']:
            ele['kwargs'].update({'context': self._get_context()})
        return response_data

    def _get(self, path):
        if path == 'nfp/get_notifications':
            if n_count == 1:
                print("cast method: orchestrator")
                return self.\
                    _prepare_request_data(
                        'orchestrator',
                        'interface',
                        'network_function_device_notification',
                        {})
            print("cast method:neutron")
            kwargs = {'host': '', 'firewall_id': 123, 'status': 'Active'}
            return self._prepare_request_data('neutron', 'firewall',
                                              'set_firewall_status',
                                              kwargs)

    def _cast(self, context, method, **kwargs):
        print("cast method:Success")
        return

    def test_rpc_pull_event(self):
        import_ca = 'gbpservice.neutron.nfp.config_agent.'
        with patch(import_ca + 'RestClientOverUnix.get') as get,\
                patch('oslo_messaging.rpc.client._CallContext.cast') as cast:
            cast.side_effect = self._cast
            get.side_effect = self._get
            ev = ''
            sc = {}
            rpc_cb_handler = rpc_cb.RpcCallback(sc)
            for i in range(0, 2):
                global n_count
                n_count = (n_count + 1) % 2
                rpc_cb_handler.rpc_pull_event(ev)

if __name__ == '__main__':
    unittest.main()
