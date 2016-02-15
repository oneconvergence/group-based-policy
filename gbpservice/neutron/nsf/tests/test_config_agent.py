import unittest
import os
import sys
import json
import mock
from mock import patch
from gbpservice.neutron.nsf.config_agent import firewall
from gbpservice.neutron.nsf.config_agent import loadbalancer as lb
from gbpservice.neutron.nsf.config_agent import vpn
from gbpservice.neutron.nsf.config_agent import topics
from gbpservice.neutron.nsf.core import main as controller
from gbpservice.neutron.nsf.core import cfg as core_cfg
from neutron import manager
from oslo_messaging import target
import threading
from neutron.common import rpc as n_rpc
from neutron.agent.common import config
from neutron import context
from neutron.common import config as common_config
from oslo_config import cfg
import time
from multiprocessing import Process
import httplib


class Context(object):

    def to_dict(self):
        return {}


class FirewallTestCase(unittest.TestCase):

    def _verify_firewall_data(self, path, body):

        if path == 'fw' and ('kwargs' in body):
            kwargs = body['kwargs']
            if all(k in kwargs for k in ("context", "host", "fw")):
                context = kwargs['context']
                if context.service_info:
                    data = context.service_info
                    if all(k in data for k in ("firewalls",
                                               "firewall_policies",
                                               "firewall_rules",
                                               "subnets", "routers",
                                               "ports")):
                        return True
        return False

    def _verify_firewall_data_for_post(self, path, body):
        if self._verify_firewall_data(path, body):
            print "[%s: %s]\n" % (httplib.OK,
                                  "create_firewall_verified:Success")
            return (httplib.OK, "create_firewall_verified:Success")

        print "[%s: %s]\n" % (httplib.NOT_FOUND,
                              "create_firewall_verified:Failed")
        return (httplib.NOT_FOUND, "create_firewall_verified:Failed")

    def _verify_firewall_data_for_put(self, path, body, delete=False):
        if self._verify_firewall_data(path, body):
            if delete:
                print "[%s: %s]\n" % (httplib.OK,
                                      "delete_firewall_verified:Success")
                return (httplib.OK, "delete_firewall_verified:Success")

            print "[%s: %s]\n" % (httplib.OK,
                                  "update_firewall_verified:Success")
            return (httplib.OK, "update_firewall_verified:Success")

        if delete:
            print "[%s: %s]\n" % (httplib.NOT_FOUND,
                                  "delete_firewall_verified:Failed")
            return (httplib.NOT_FOUND, "delete_firewall_verified:Failed")

        print "[%s: %s]\n" % (httplib.OK, "update_firewall_verified:Success")
        return (httplib.OK, "update_firewall_verified:Success")

    def _prepare_firewall_request_data(self):
        context.__setattr__('service_info', {})
        context.__setattr__('is_admin', False)
        fw = {'tenant_id': 123}
        host = ''
        conf = {}
        sc = {}
        return context, fw, sc, conf, host

    def test_create_firewall(self):
        import_db = 'neutron_fwaas.db.firewall.firewall_db.\
Firewall_db_mixin.'
        import_ca = 'gbpservice.neutron.nsf.config_agent.'

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

    def test_update_firewall(self):
        import_db = 'neutron_fwaas.db.firewall.firewall_db.\
Firewall_db_mixin.'
        import_cfg_agent = 'gbpservice.neutron.nsf.config_agent.'
        with patch(import_db + 'get_firewalls') as get_firewalls,\
                patch(import_db + 'get_firewall_policies') as gfwp,\
                patch(import_db + 'get_firewall_rules') as gfwr,\
                patch(import_db + '_core_plugin') as _cp,\
                patch(import_cfg_agent + 'RestClientOverUnix.put') as put:

            put.side_effect = self._verify_firewall_data_for_put
            context, fw, sc, conf, host = self.\
                _prepare_firewall_request_data()
            fw_handler = firewall.FwAgent(conf, sc)
            fw_handler.update_firewall(context, fw, host)

    def test_delete_firewall(self):
        import_db = 'neutron_fwaas.db.firewall.firewall_db.\
Firewall_db_mixin.'
        import_cfg_agent = 'gbpservice.neutron.nsf.config_agent.'

        with patch(import_db + 'get_firewalls') as get_firewalls,\
                patch(import_db + 'get_firewall_policies') as gfwp,\
                patch(import_db + 'get_firewall_rules') as gfwr,\
                patch(import_db + '_core_plugin') as _cp,\
                patch(import_cfg_agent + 'RestClientOverUnix.put') as put:

            put.side_effect = self._verify_firewall_data_for_put
            context, fw, sc, conf, host = self.\
                _prepare_firewall_request_data()
            fw_handler = firewall.FwAgent(conf, sc)
            fw_handler.delete_firewall(context, fw, host)


class LoadBalanceTestCase(unittest.TestCase):

    def _verify_path(self, path):
        resources = ["vip", "pool", "member", "hm"]
        rsrc_input = path.split("/")[1]
        if resources.__contains__(rsrc_input):
            return True, rsrc_input
        return False, rsrc_input

    def _verify_post_or_delete_data(self, body, resource):

        if 'kwargs' in body:
            kwargs = body['kwargs']
            if all(k in kwargs for k in ("context", resource)):
                context = kwargs['context']
                if context.service_info:
                    data = context.service_info
                    if all(k in data for k in ("pools", "vips", "members",
                                               "health_monitors",
                                               "subnets", "ports")):
                        return True
        return False

    def _verify_update_data(self, body, resource):

        if 'kwargs' in body:
            kwargs = body['kwargs']
            if all(k in kwargs for k in ("context", resource,
                                         "old" + resource)):
                context = kwargs['context']
                if context.service_info:
                    data = context.service_info
                    if all(k in data for k in ("pools", "vips", "members",
                                               "health_monitors",
                                               "subnets", "ports")):
                        return True
        return False

    def _verify_post(self, path, body):
        result, resource = self._verify_path(path)
        if result and self._verify_post_or_delete_data(body, resource):
            print "[%s: create_%s_verified:Success]\n" % (
                httplib.OK, resource)
            return (httplib.OK, "create_%s_verified:Success" % (resource))

        print "[%s: create_%s_verified:Failed]\n" % (httplib.NOT_FOUND,
                                                     resource)
        return (httplib.NOT_FOUND, "create_%s_verified:Failed" % (resource))

    def _verify_delete_update(self, path, body, delete=False):
        result, resource = self._verify_path(path)
        if delete:
            if result and self._verify_post_or_delete_data(body, resource):
                print "[%s: delete_%s_verified:Success]\n" % (httplib.OK,
                                                              resource)
                return (httplib.OK, "delete_%s_verified:Success" % (resource))

            print "[%s: delete_%s_verified:Failed]\n" % (httplib.OK, resource)
            return (httplib.OK, "delete_%s_verified:Failed" % (resource))

        if result and self._verify_update_data(body, resource):
            print "[%s: update_%s_verified:Success]\n" % (httplib.OK,
                                                          resource)
            return (httplib.OK, "update_%s_verified:Success" % (resource))

        print "[%s: update_%s_verified:Failed]\n" % (httplib.OK, resource)
        return (httplib.OK, "update_%s_verified:Failed" % (resource))

    def _prepare_request_data(self):
        context.__setattr__('service_info', {})
        context.__setattr__('is_admin', False)
        conf = {}
        sc = {}
        return context, sc, conf

    def test_create_vip(self):
        import_db = 'neutron_lbaas.db.loadbalancer.loadbalancer_db\
.LoadBalancerPluginDb.'
        import_config_agent = 'gbpservice.neutron.nsf.config_agent.'
        with patch(import_db + 'get_pools') as get_pools,\
                patch(import_db + 'get_vips') as get_vips,\
                patch(import_db + 'get_members') as get_members,\
                patch(import_db + 'get_health_monitors') as get_hm,\
                patch(import_db + '_core_plugin') as _core_plugin,\
                patch(import_config_agent + 'RestClientOverUnix.post') as post:

            post.side_effect = self._verify_post
            context, sc, conf = self._prepare_request_data()
            vip = {'tenant_id': 123}
            lb_handler = lb.LbAgent(conf, sc)
            lb_handler.create_vip(context, vip)

    def test_create_pool(self):
        import_db = 'neutron_lbaas.db.loadbalancer.loadbalancer_db\
.LoadBalancerPluginDb.'
        import_config_agent = 'gbpservice.neutron.nsf.config_agent.'
        with patch(import_db + 'get_pools') as get_pools,\
                patch(import_db + 'get_vips') as get_vips,\
                patch(import_db + 'get_members') as get_members,\
                patch(import_db + 'get_health_monitors') as get_hm,\
                patch(import_db + '_core_plugin') as _core_plugin,\
                patch(import_config_agent + 'RestClientOverUnix.post') as post:

            post.side_effect = self._verify_post
            context, sc, conf = self._prepare_request_data()
            pool = {'tenant_id': 123}
            driver_name = "dummy"
            lb_handler = lb.LbAgent(conf, sc)
            lb_handler.create_pool(context, pool, driver_name)

    def test_create_member(self):
        import_db = 'neutron_lbaas.db.loadbalancer.loadbalancer_db\
.LoadBalancerPluginDb.'
        import_config_agent = 'gbpservice.neutron.nsf.config_agent.'
        with patch(import_db + 'get_pools') as get_pools,\
                patch(import_db + 'get_vips') as get_vips,\
                patch(import_db + 'get_members') as get_members,\
                patch(import_db + 'get_health_monitors') as get_hm,\
                patch(import_db + '_core_plugin') as _core_plugin,\
                patch(import_config_agent + 'RestClientOverUnix.post') as post:

            post.side_effect = self._verify_post
            context, sc, conf = self._prepare_request_data()
            member = {'tenant_id': 123}
            lb_handler = lb.LbAgent(conf, sc)
            lb_handler.create_member(context, member)

    def test_create_pool_health_monitor(self):
        import_db = 'neutron_lbaas.db.loadbalancer.loadbalancer_db\
.LoadBalancerPluginDb.'
        import_config_agent = 'gbpservice.neutron.nsf.config_agent.'
        with patch(import_db + 'get_pools') as get_pools,\
                patch(import_db + 'get_vips') as get_vips,\
                patch(import_db + 'get_members') as get_members,\
                patch(import_db + 'get_health_monitors') as get_hm,\
                patch(import_db + '_core_plugin') as _core_plugin,\
                patch(import_config_agent + 'RestClientOverUnix.post') as post:

            post.side_effect = self._verify_post
            context, sc, conf = self._prepare_request_data()
            hm = {'tenant_id': 123}
            pool_id = "123"
            lb_handler = lb.LbAgent(conf, sc)
            lb_handler.create_pool_health_monitor(context, hm, pool_id)

    def test_update_vip(self):
        import_db = 'neutron_lbaas.db.loadbalancer.loadbalancer_db\
.LoadBalancerPluginDb.'
        import_config_agent = 'gbpservice.neutron.nsf.config_agent.'
        with patch(import_db + 'get_pools') as get_pools,\
                patch(import_db + 'get_vips') as get_vips,\
                patch(import_db + 'get_members') as get_members,\
                patch(import_db + 'get_health_monitors') as get_hm,\
                patch(import_db + '_core_plugin') as _core_plugin,\
                patch(import_config_agent + 'RestClientOverUnix.put') as put:

            put.side_effect = self._verify_delete_update
            context, sc, conf = self._prepare_request_data()
            old_vip = {'id': 123, 'tenant_id': 123}
            vip = {}
            lb_handler = lb.LbAgent(conf, sc)
            lb_handler.update_vip(context, old_vip, vip)

    def test_update_pool(self):
        import_db = 'neutron_lbaas.db.loadbalancer.loadbalancer_db\
.LoadBalancerPluginDb.'
        import_config_agent = 'gbpservice.neutron.nsf.config_agent.'
        with patch(import_db + 'get_pools') as get_pools,\
                patch(import_db + 'get_vips') as get_vips,\
                patch(import_db + 'get_members') as get_members,\
                patch(import_db + 'get_health_monitors') as get_hm,\
                patch(import_db + '_core_plugin') as _core_plugin,\
                patch(import_config_agent + 'RestClientOverUnix.put') as put:

            put.side_effect = self._verify_delete_update
            context, sc, conf = self._prepare_request_data()
            old_pool = {'id': 123, 'tenant_id': 123}
            pool = {}
            lb_handler = lb.LbAgent(conf, sc)
            lb_handler.update_pool(context, old_pool, pool)

    def test_update_member(self):
        import_db = 'neutron_lbaas.db.loadbalancer.loadbalancer_db\
.LoadBalancerPluginDb.'
        import_config_agent = 'gbpservice.neutron.nsf.config_agent.'
        with patch(import_db + 'get_pools') as get_pools,\
                patch(import_db + 'get_vips') as get_vips,\
                patch(import_db + 'get_members') as get_members,\
                patch(import_db + 'get_health_monitors') as get_hm,\
                patch(import_db + '_core_plugin') as _core_plugin,\
                patch(import_config_agent + 'RestClientOverUnix.put') as put:

            put.side_effect = self._verify_delete_update
            context, sc, conf = self._prepare_request_data()
            old_member = {'id': 123, 'tenant_id': 123}
            member = {}
            lb_handler = lb.LbAgent(conf, sc)
            lb_handler.update_member(context, old_member, member)

    def test_update_pool_health_monitor(self):
        import_db = 'neutron_lbaas.db.loadbalancer.loadbalancer_db\
.LoadBalancerPluginDb.'
        import_config_agent = 'gbpservice.neutron.nsf.config_agent.'
        with patch(import_db + 'get_pools') as get_pools,\
                patch(import_db + 'get_vips') as get_vips,\
                patch(import_db + 'get_members') as get_members,\
                patch(import_db + 'get_health_monitors') as get_hm,\
                patch(import_db + '_core_plugin') as _core_plugin,\
                patch(import_config_agent + 'RestClientOverUnix.put') as put:

            put.side_effect = self._verify_delete_update
            context, sc, conf = self._prepare_request_data()
            old_hm = {'id': 123, 'tenant_id': 123}
            hm = {}
            pool_id = 123
            lb_handler = lb.LbAgent(conf, sc)
            lb_handler.update_pool_health_monitor(context, old_hm, hm, pool_id)

    def test_delete_vip(self):
        import_db = 'neutron_lbaas.db.loadbalancer.loadbalancer_db\
.LoadBalancerPluginDb.'
        import_config_agent = 'gbpservice.neutron.nsf.config_agent.'
        with patch(import_db + 'get_pools') as get_pools,\
                patch(import_db + 'get_vips') as get_vips,\
                patch(import_db + 'get_members') as get_members,\
                patch(import_db + 'get_health_monitors') as get_hm,\
                patch(import_db + '_core_plugin') as _core_plugin,\
                patch(import_config_agent + 'RestClientOverUnix.put') as put:

            put.side_effect = self._verify_delete_update
            context, sc, conf = self._prepare_request_data()
            vip = {'id': 123, 'tenant_id': 123}
            lb_handler = lb.LbAgent(conf, sc)
            lb_handler.delete_vip(context, vip)

    def test_delete_pool(self):
        import_db = 'neutron_lbaas.db.loadbalancer.loadbalancer_db\
.LoadBalancerPluginDb.'
        import_config_agent = 'gbpservice.neutron.nsf.config_agent.'
        with patch(import_db + 'get_pools') as get_pools,\
                patch(import_db + 'get_vips') as get_vips,\
                patch(import_db + 'get_members') as get_members,\
                patch(import_db + 'get_health_monitors') as get_hm,\
                patch(import_db + '_core_plugin') as _core_plugin,\
                patch(import_config_agent + 'RestClientOverUnix.put') as put:

            put.side_effect = self._verify_delete_update
            context, sc, conf = self._prepare_request_data()
            pool = {'id': 123, 'tenant_id': 123}
            lb_handler = lb.LbAgent(conf, sc)
            lb_handler.delete_pool(context, pool)

    def test_delete_member(self):
        import_db = 'neutron_lbaas.db.loadbalancer.loadbalancer_db\
.LoadBalancerPluginDb.'
        import_config_agent = 'gbpservice.neutron.nsf.config_agent.'
        with patch(import_db + 'get_pools') as get_pools,\
                patch(import_db + 'get_vips') as get_vips,\
                patch(import_db + 'get_members') as get_members,\
                patch(import_db + 'get_health_monitors') as get_hm,\
                patch(import_db + '_core_plugin') as _core_plugin,\
                patch(import_config_agent + 'RestClientOverUnix.put') as put:

            put.side_effect = self._verify_delete_update
            context, sc, conf = self._prepare_request_data()
            member = {'id': 123, 'tenant_id': 123}
            lb_handler = lb.LbAgent(conf, sc)
            lb_handler.delete_member(context, member)

    def test_delete_pool_health_monitor(self):
        import_db = 'neutron_lbaas.db.loadbalancer.loadbalancer_db\
.LoadBalancerPluginDb.'
        import_config_agent = 'gbpservice.neutron.nsf.config_agent.'
        with patch(import_db + 'get_pools') as get_pools,\
                patch(import_db + 'get_vips') as get_vips,\
                patch(import_db + 'get_members') as get_members,\
                patch(import_db + 'get_health_monitors') as get_hm,\
                patch(import_db + '_core_plugin') as _core_plugin,\
                patch(import_config_agent + 'RestClientOverUnix.put') as put:

            put.side_effect = self._verify_delete_update
            context, sc, conf = self._prepare_request_data()
            hm = {'id': 123, 'tenant_id': 123}
            pool_id = 123
            lb_handler = lb.LbAgent(conf, sc)
            lb_handler.delete_pool_health_monitor(context, hm, pool_id)


class VPNTestCase(unittest.TestCase):

    def _prepare_request_data(self):
        context.__setattr__('service_info', {})
        context.__setattr__('is_admin', False)
        conf = {}
        sc = {}
        return context, sc, conf

    def _verify_update_data(self, path, body, delete=False):

        if path == 'vpn' and ('kwargs' in body):
            kwargs = body['kwargs']
            if all(k in kwargs for k in ("context", "resource")):
                context = kwargs['context']
                if context.service_info:
                    data = context.service_info
                    if all(k in data for k in ("vpnservices",
                                               "ikepolicies",
                                               "ipsecpolicies",
                                               "ipsec_site_conns",
                                               "subnets",
                                               "routers")):
                        return True
        return False

    def _verify_vpn_data(self, path, body):
        if self._verify_update_data(path, body):
            print "[%s: %s]\n" % (httplib.OK,
                                  "update_vpnservice_verified:Success")
            return (httplib.OK, "update_vpnservice_verified:Success")

        print "[%s: %s]\n" % (httplib.NOT_FOUND, "update_vpn_verified:Failed")
        return (httplib.NOT_FOUND, "update_vpn_verified:Failed")

    def test_update_vpnservice(self):
        import_db = 'neutron_vpnaas.db.vpn.vpn_db.VPNPluginDb.'
        import_ca = 'gbpservice.neutron.nsf.config_agent.'
        with patch(import_db + 'get_vpnservices') as gvs,\
                patch(import_db + 'get_ikepolicies') as gikp,\
                patch(import_db + 'get_ipsecpolicies') as gipp,\
                patch(import_db + 'get_ipsec_site_connections') as gisc,\
                patch(import_ca + 'vpn.VpnAgent.core_plugin') as _cp,\
                patch(import_ca + 'RestClientOverUnix.put') as put:
            put.side_effect = self._verify_vpn_data
            context, sc, conf = self._prepare_request_data()
            resource = {'tenant_id': 123}
            vpn_handler = vpn.VpnAgent(conf, sc)
            vpn_handler.vpnservice_updated(context, resource=resource)

if __name__ == '__main__':
    unittest.main()
