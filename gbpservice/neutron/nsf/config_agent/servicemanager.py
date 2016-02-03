import sys
import ast

from oslo_config import cfg
from oslo_messaging import target
from oslo_log import log as logging
from gbpservice.neutron.nsf.config_agent import RestClientOverUnix as rc

LOG = logging.getLogger(__name__)


class SmAgent(object):
    RPC_API_VERSION = '1.0'
    target = target.Target(version=RPC_API_VERSION)

    def __init__(self, conf, sc):
        self._conf = conf
        self._sc = sc
        super(ServiceManager, self).__init__()

    def _post(self, context, name, **kwargs):
        body = {'kwargs': kwargs,
                'context': context}
        try:
            resp, content = rc.post('gc/%s' % (name), body=body)
        except:
            LOG.error("create_%s -> request failed." % (name))

    def _delete(self, context, name, **kwargs):
        body = {'kwargs': kwargs,
                'context': context}
        try:
            resp, content = rc.delete('gc/%s' % (name), body=body)
        except:
            LOG.error("delete_%s -> request failed." % (name))

    def configure_interfaces(self, context, **kwargs):
        self._post(context, 'configure_interfaces', **kwargs)

    def clear_interfaces(self, context, floating_ip, service_vendor,
                         provider_interface_position,
                         stitching_interface_position):
        self._delete(context, 'clear_interfaces',
                     floating_ip=floating_ip,
                     service_vendor=service_vendor,
                     provider_interface_position=provider_interface_position,
                     stitching_interface_position=stitching_interface_position)

    def configure_license(self, context, floating_ip,
                          service_vendor, license_key):
        self._post(context, 'configure_license',
                   floating_ip=floating_ip,
                   service_vendor=service_vendor,
                   license_key=license_key)

    def release_license(self, context, floating_ip,
                        service_vendor, license_key):
        self._delete(context, 'release_license',
                     floating_ip=floating_ip,
                     service_vendor=service_vendor,
                     license_key=license_key)

    def configure_source_routes(self, context, floating_ip, service_vendor,
                                source_cidrs, destination_cidr, gateway_ip,
                                provider_interface_position,
                                standby_floating_ip=None):
        self._post(context, 'configure_source_routes',
                   floating_ip=floating_ip,
                   service_vendor=service_vendor,
                   source_cidrs=source_cidrs,
                   destination_cidr=destination_cidr,
                   gateway_ip=gateway_ip,
                   provider_interface_position=provider_interface_position,
                   standby_floating_ip=standby_floating_ip)

    def delete_source_routes(self, context, floating_ip, service_vendor,
                             source_cidrs, provider_interface_position,
                             standby_floating_ip=None):
        self._delete(context, 'delete_source_routes',
                     floating_ip=floating_ip,
                     service_vendor=service_vendor,
                     source_cidrs=source_cidrs,
                     provider_interface_position=provider_interface_position,
                     standby_floating_ip=standby_floating_ip)

    def add_persistent_rule(self, context, **kwargs):
        self._post(context, 'add_persistent_rule', **kwargs)

    def del_persistent_rule(self, context, **kwargs):
        self._delete(context, 'del_persistent_rule', **kwargs)
