from oslo_config import cfg
from neutron import manager
from oslo_messaging import target

from gbpservice.neutron.nsf.config_agent import RestClientOverUnix as rc
from oslo_log import log as logging
from neutron_lbaas.db.loadbalancer import loadbalancer_db
from neutron_lbaas.db.loadbalancer import loadbalancer_db
from neutron.common import rpc as n_rpc

LOG = logging.getLogger(__name__)

class Lb(object):
    API_VERSION = '1.0'
    def __init__(self, host):
        self.topic = topics.LB_NSF_PLUGIN_TOPIC
        target = target.Target(topic=self.topic,
                     version=self.API_VERSION)
        self.client = n_rpc.get_client(target)
        self.cctxt = self.client.prepare(version=self.API_VERSION,
                                    topic=self.topic)

    def report_state(self, **kwargs):
        context = kwargs.get('context')
        del kwargs['context']
        cctxt.cast(context, 'report_state',
                   **kwargs)

    def update_status(self, **kwargs):
        context = kwargs.get('context')
        del kwargs['context']
        cctxt.cast(context, 'update_status',
                   **kwargs)

    def update_pool_stats(self, **kwargs):
        context = kwargs.get('context')
        del kwargs['context']
        cctxt.cast(context, 'update_pool_stats',
                   **kwargs)

    def resource_deleted(self, **kwargs):
        context = kwargs.get('context')
        del kwargs['context']
        cctxt.cast(context, 'resource_deleted',
                   **kwargs)

class LbAgent(loadbalancer_db.LoadBalancerPluginDb):
    RPC_API_VERSION = '1.0'
    target = target.Target(version=RPC_API_VERSION)

    def __init__(self, conf, sc):
        self._conf = conf
        self._sc = sc
        super(LbAgent, self).__init__()

    def _post(self, context, tenant_id, name, **kwargs):
        db = self._context(context, tenant_id)
        context['service_info'] = db
        kwargs.update({'context': context})
        body = {'kwargs': kwargs}
        try:
            resp, content = rc.post('lb/%s' % (name), body=body)
        except:
            LOG.error("create_%s -> request failed." % (name))

    def _put(self, context, tenant_id, name, id, **kwargs):
        db = self._context(context, tenant_id)
        context['service_info'] = db
        kwargs.update({'context': context})
        body = {'kwargs': kwargs}
        try:
            resp, content = rc.put('lb/%s/%s' % (name, id), body=body)
        except:
            LOG.error("update_%s -> request failed." % (name))

    def _delete(self, context, tenant_id, name, id, **kwargs):
        db = self._context(context, tenant_id)
        context['service_info'] = db
        kwargs.update({'context': context})
        body = {'kwargs': kwargs}
        try:
            resp, content = rc.put('lb/%s/%s' %
                                   (name, id), body=body, delete=True)
        except:
            LOG.error("delete_%s -> request failed." % (name))

    def create_vip(self, context, vip):
        self._post(context, vip['tenant_id'], 'vip', vip=vip)

    def update_vip(self, context, old_vip, vip):
        self._put(context, old_vip['tenant_id'], 'vip', old_vip[
                  'id'], oldvip=old_vip, vip=vip)

    def delete_vip(self, context, vip):
        self._delete(context, vip['tenant_id'], 'vip', vip['id'], vip=vip)

    def create_pool(self, context, pool, driver_name):
        self._post(
            context, pool['tenant_id'],
            'pool', pool=pool, driver_name=driver_name)

    def update_pool(self, context, old_pool, pool):
        self._put(context, old_pool['tenant_id'], 'pool', old_pool[
                  'id'], oldpool=old_pool, pool=pool)

    def delete_pool(self, context, pool):
        self._delete(context, pool['tenant_id'], 'pool', pool['id'], pool=pool)

    def create_member(self, context, member):
        self._post(context, member['tenant_id'], 'member', member=member)

    def update_member(self, context, old_member, member):
        self._put(context, old_member['tenant_id'], 'member', old_member[
                  'id'], oldmember=old_member, member=member)

    def delete_member(self, context, member):
        self._delete(
            context, member['tenant_id'], 'member',
            member['id'], member=member)

    def create_pool_health_monitor(self, context, hm, pool_id):
        self._post(context, health_monitor[
                   'tenant_id'], 'hm',
                   hm=hm, pool_id=pool_id)

    def update_pool_health_monitor(self, context, old_hm,
                                   hm, pool_id):
        self._put(context, old_hm['tenant_id'], 'hm',
                  old_hm['id'], oldhm=old_hm,
                  hm=hm, pool_id=pool_id)

    def delete_pool_health_monitor(self, context, hm, pool_id):
        self._delete(
            context, health_monitor['tenant_id'], 'hm',
            hm['id'], hm=hm, pool_id=pool_id)

    def _context(self, context, tenant_id):
        if context.is_admin:
            tenant_id = context.tenant_id
        filters = {'tenant_id': tenant_id}
        db = self._get_vpn_context(context, filters)
        db.update(self._get_core_context(context, filters))
        return db

    def _get_core_context(self, context, filters):
        core_plugin = self._core_plugin
        subnets = core_plugin.get_subnets(
            context, filters)
        ports = core_plugin.get_ports(
            context, filters)
        '''
        routers = core_plugin.get_routers(
                      context,
                      filters)
        '''
        return {'subnets': subnets, 'ports': ports}

    def _get_lb_context(self, context, filters):
        pools = super(LbAgent, self).\
            get_pools(context, filters)
        vips = super(LbAgent, self).\
            get_vips(context, filters)
        members = super(LbAgent, self).\
            get_members(context, filters)
        health_monitors = super(LbAgent, self).\
            get_health_monitors(context, filters)
        return {'pools': pools,
                'vips': vips,
                'members': members,
                'health_monitors': health_monitors}
