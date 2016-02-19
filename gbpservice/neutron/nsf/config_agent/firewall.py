import sys
import ast

from oslo_config import cfg
from oslo_messaging import target
from oslo_log import log as logging
from neutron import manager

from neutron_fwaas.db.firewall import firewall_db

from gbpservice.neutron.nsf.config_agent import RestClientOverUnix as rc
from gbpservice.neutron.nsf.config_agent import topics
from neutron.common import rpc as n_rpc

LOG = logging.getLogger(__name__)

Version = 'v1'  # v1/v2/v3#


class Firewall(object):
    API_VERSION = '1.0'

    def __init__(self):
        self.topic = topics.FW_NSF_PLUGIN_TOPIC
        _target = target.Target(topic=self.topic,
                                version=self.API_VERSION)
        n_rpc.init(cfg.CONF)
        self.client = n_rpc.get_client(_target)
        self.cctxt = self.client.prepare(version=self.API_VERSION,
                                         topic=self.topic)

    def set_firewall_status(self, **kwargs):
        context = kwargs.get('context')
        del kwargs['context']
        self.cctxt.cast(context, 'set_firewall_status',
                        host=kwargs['host'],
                        firewall_id=kwargs['firewall_id'],
                        status=kwargs['status'])

    def firewall_deleted(self, **kwargs):
        context = kwargs.get('context')
        del kwargs['context']
        self.cctxt.cast(context, 'firewall_deleted',
                        host=kwargs['host'],
                        firewall_id=kwargs['firewall_id'])


class FwAgent(firewall_db.Firewall_db_mixin):

    RPC_API_VERSION = '1.0'
    _target = target.Target(version=RPC_API_VERSION)

    def __init__(self, conf, sc):
        self._conf = conf
        self._sc = sc
        super(FwAgent, self).__init__()

    def _prepare_request_data(self, resource, kwargs):

        request_data = {'info': {
            'version': Version,
            'service_type': "firewall"
        },

            'config': [{
                'resource': resource,
                'kwargs': kwargs
            }]
        }

        return {'request_data': request_data}

    def create_firewall(self, context, fw, host):

        db = self._context(context, fw['tenant_id'])
        context.__setattr__('service_info', db)
        kwargs = {'fw': fw,
                  'host': host,
                  'context': context}
        resource = 'fw'
        body = self._prepare_request_data(resource, kwargs)
        try:
            resp, content = rc.post(
                'create_network_function_config', body=body)
        except:
            LOG.error("create_firewall -> POST request failed.")

    '''
    def update_firewall(self, context, fw, host):

        db = self._context(context, fw['tenant_id'])
        context.__setattr__('service_info', db)
        kwargs = {'fw': fw, 'host': host, 'context': context}
        resource = 'fw'
        body = self._prepare_request_data(resource, kwargs)
        try:
            resp, content = rc.put('update_network_service_config', body=body)
        except:
            LOG.error("update_firewall -> UPDATE request failed.")
    '''

    def delete_firewall(self, context, fw, host):

        db = self._context(context, fw['tenant_id'])
        context.__setattr__('service_info', db)
        kwargs = {'fw': fw, 'host': host, 'context': context}
        resource = 'fw'
        body = self._prepare_request_data(resource, kwargs)
        try:
            resp, content = rc.post('delete_network_function_config',
                                    body=body, delete=True)
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

        firewalls = super(FwAgent, self).\
            get_firewalls(context, filters)

        firewall_policies = super(FwAgent, self).\
            get_firewall_policies(context, filters)

        firewall_rules = super(FwAgent, self).\
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
