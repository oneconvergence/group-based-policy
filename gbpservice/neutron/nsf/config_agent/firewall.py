import sys
import ast

from oslo_config import cfg
from oslo_messaging import target
from neutron import manager

from neutron.db.firewall import firewall_db

from gbpservice.neutron.nsf.config_agent import RestClientOverUnix as rc

LOG = logging.getLogger(__name__)


class FirewallAgent(firewall_db.Firewall_db_mixin):

    RPC_API_VERSION = '1.0'
    target = target.Target(version=RPC_API_VERSION)

    def __init__(self, conf, sc):
        self._conf = conf
        self._sc = sc
        super(FirewallAgent, self).__init__()

    def create_firewall(self, context, fw, host):

        db = self._context(context, fw['tenant_id'])
        context['service_info'] = db
        kwargs = {'fw': fw, 'host': host, 'context': context}
        body = {'kwargs': kwargs}
        try:
            resp, content = rc.post('fw', body=body)
        except:
            LOG.error("create_firewall -> POST request failed.")

    def update_firewall(self, context, fw, host):

        db = self._context(context, fw['tenant_id'])
        context['service_info'] = db
        kwargs = {'fw': fw, 'host': host, 'context': context}
        body = {'kwargs': kwargs}
        try:
            resp, content = rc.put('fw', body=body)
        except:
            LOG.error("update_firewall -> UPDATE request failed.")

    def delete_firewall(self, context, firewall, host):

        db = self._context(context, fw['tenant_id'])
        context['service_info'] = db
        kwargs = {'fw': fw, 'host': host, 'context': context}
        body = {'kwargs': kwargs}
        try:
            resp, content = rc.put('fw', body=body, delete=True)
        except:
            LOG.error("delete_firewall -> DELETE request failed.")

    def _context(self, context, tenant_id):
        if context.is_admin:
            tenant_id = context.tenant_id
        filters = {'tenant_id': tenant_id}
        db = self._get_firewall_context(context, filters)
        db.update(self._get_core_context(context, filters))
        return db

    def _get_firewall_context(self, context, filters):

        firewalls = super(OCFWAgent, self).\
            get_firewalls(context, filters)

        firewall_policies = super(OCFWAgent, self).\
            get_firewall_policies(context, filters)

        firewall_rules = super(OCFWAgent, self).\
            get_firewall_rules(context, filters)

        return {'firewalls': firewalls,
                'firewall_policies': firewall_policies,
                'firewall_rules': firewall_rules}

    def _get_core_context(self, context, filters):
        core_plugin = self._core_plugin
        subnets = core_plugin.get_subnets(
            context,
            filters)

        routers = core_plugin.get_routers(
            context,
            filters)

        ports = core_plugin.get_ports(
            context,
            filters)

        return {'subnets': subnets,
                'routers': routers,
                'ports': ports}