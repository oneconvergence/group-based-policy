import sys
import ast

from oslo_config import cfg
from oslo_messaging import target
from oslo_log import log as logging
from gbpservice.neutron.nsf.config_agent import RestClientOverUnix as rc
from gbpservice.neutron.nsf.config_agent import topics
from neutron.common import rpc as n_rpc

LOG = logging.getLogger(__name__)


class Gc(object):
    API_VERSION = '1.0'

    def __init__(self, host):
        self.topic = topics.GC_NSF_PLUGIN_TOPIC
        target = target.Target(topic=self.topic,
                               version=self.API_VERSION)
        self.client = n_rpc.get_client(target)
        self.cctxt = self.client.prepare(version=self.API_VERSION,
                                         topic=self.topic)

    def configure_interface_complete(self, **kwargs):
        context = kwargs.get('context')
        del kwargs['context']
        cctxt.cast(context, 'configure_interface_complete',
                   **kwargs)

    def clear_interface_complete(self, **kwargs):
        context = kwargs.get('context')
        del kwargs['context']
        cctxt.cast(context, 'clear_interface_complete',
                   **kwargs)

    def configure_source_routes_complete(self, **kwargs):
        context = kwargs.get('context')
        del kwargs['context']
        cctxt.cast(context, 'configure_source_routes_complete',
                   **kwargs)

    def clear_source_routes_complete(self, **kwargs):
        context = kwargs.get('context')
        del kwargs['context']
        cctxt.cast(context, 'clear_source_routes_complete',
                   **kwargs)

    def configure_healthmonitor_complete(self, **kwargs):
        context = kwargs.get('context')
        del kwargs['context']
        cctxt.cast(context, 'configure_healthmonitor_complete',
                   **kwargs)

    def clear_healthmonitor_complete(self, **kwargs):
        context = kwargs.get('context')
        del kwargs['context']
        cctxt.cast(context, 'clear_healthmonitor_complete',
                   **kwargs)


class GcAgent(object):
    RPC_API_VERSION = '1.0'
    target = target.Target(version=RPC_API_VERSION)

    def __init__(self, conf, sc):
        self._conf = conf
        self._sc = sc
        super(GcAgent, self).__init__()

    def _post(self, context, name, **kwargs):
        kwargs.update({'context': context})
        body = {'kwargs': kwargs}
        try:
            resp, content = rc.post('gc/%s' % (name), body=body)
        except:
            LOG.error("create_%s -> request failed." % (name))

    def _delete(self, context, name, **kwargs):
        kwargs.update({'context': context})
        body = {'kwargs': kwargs}
        try:
            resp, content = rc.put('gc/%s' % (name), body=body, delete=True)
        except:
            LOG.error("delete_%s -> request failed." % (name))

    def configure_interfaces(self, context, **kwargs):
        self._post(context, 'interfaces', **kwargs)

    def clear_interfaces(self, context, floating_ip, service_vendor,
                         provider_interface_position,
                         stitching_interface_position):
        self._delete(context, 'interfaces',
                     floating_ip=floating_ip,
                     service_vendor=service_vendor,
                     provider_interface_position=provider_interface_position,
                     stitching_interface_position=stitching_interface_position)

    def configure_source_routes(self, context, floating_ip, service_vendor,
                                source_cidrs, destination_cidr, gateway_ip,
                                provider_interface_position,
                                standby_floating_ip=None):
        self._post(context, 'source_routes',
                   floating_ip=floating_ip,
                   service_vendor=service_vendor,
                   source_cidrs=source_cidrs,
                   destination_cidr=destination_cidr,
                   gateway_ip=gateway_ip,
                   provider_interface_position=provider_interface_position,
                   standby_floating_ip=standby_floating_ip)

    def clear_source_routes(self, context, floating_ip, service_vendor,
                            source_cidrs, provider_interface_position,
                            standby_floating_ip=None):
        self._delete(context, 'source_routes',
                     floating_ip=floating_ip,
                     service_vendor=service_vendor,
                     source_cidrs=source_cidrs,
                     provider_interface_position=provider_interface_position,
                     standby_floating_ip=standby_floating_ip)

    def configure_healthmonitor(self, context, **kwargs):
        self._post(context, 'hm',  **kwargs)

    def clear_healthmonitor(self, context, **kwargs):
        self._delete(context, 'hm',  **kwargs)
