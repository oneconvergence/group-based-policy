import json
import requests

from gbpservice.nfp.configurator.drivers.firewall.vyos import vyos_fw_driver
from gbpservice.nfp.configurator.lib import constants as common_const
from gbpservice.nfp.core import log as nfp_logging
from oslo_config import cfg

LOG = nfp_logging.getLogger(__name__)

# TODO:(pritam) correct it
PROVIDER_VRRP_GROUP = 'PROVIDER_VRRP_GROUP'
STITCHING_VRRP_GROUP = 'STITCHING_VRRP_GROUP'

VYOS_CONFIG_OPTS = [cfg.StrOpt('event_queue_size', default=1,
                               help=_('Event Queue size for conntrack ')),
                    cfg.StrOpt('sync_queue_size', default=10,
                               help=_('Default sync queue size for vrrp')),
                    cfg.IntOpt('advertised_interval', default=10,
                               help=_('Advertising interval for config '
                                      'exchange between VYOS units')),
                    cfg.IntOpt('preempt_delay', default=10,
                               help=_("Delay for preemption")),
                    cfg.StrOpt('multicast_ip', default="225.0.0.2",
                               help=_("Multicast IP address")),
                    cfg.DictOpt('priority', default=dict(active=254,
                                                         standby=253),
                                help=_("Priority of group")),
                    ]
cfg.CONF.register_opts(VYOS_CONFIG_OPTS, 'VYOS_HA_CONFIG')


class VyosFWHADriver(vyos_fw_driver.FwaasDriver):
    ha = 'true'

    """(Pritam): Do we need to have separate classes to handle
    generic config and *aaS neutron apis or okay to have all
    apis here only ?
    """
    def __init__(self, conf):
        self.request_url = "http://%s:%s/%s"
        super(VyosFWHADriver, self).__init__(conf=conf)
        self._vrrp_params()

    def _vrrp_params(self):
        self.sync_queue_size = cfg.CONF.VYOS_HA_CONFIG.sync_queue_size
        self.event_queue_size = cfg.CONF.VYOS_HA_CONFIG.event_queue_size
        self.advertised_interval = cfg.CONF.VYOS_HA_CONFIG.advertised_interval
        self.preempt_delay = cfg.CONF.VYOS_HA_CONFIG.preempt_delay
        self.priority = cfg.CONF.VYOS_HA_CONFIG.priority
        self.multicast_ip = cfg.CONF.VYOS_HA_CONFIG.multicast_ip

    def _generate_cluster_name(self, resource_data):
        # TODO:(pritam) - correct it
        # cluster_name = "CLUSTER-%s" % str((resource_data['tenant_id'][:2] +
        #                                   resource_data['vm_id'][:2]))
        cluster_name = "CLUSTER-%s" % str((resource_data['tenant_id'][:2]))
        return cluster_name

    def _get_multicast_group(self, resource_data):
        # TODO:(pritam) - correct it
        return self.multicast_ip

    def _generate_vrrp_group(self, resource_data):
        # TODO:(pritam) - correct it
        return dict(provider_vrrp_group=PROVIDER_VRRP_GROUP,
                    stitching_vrrp_group=STITCHING_VRRP_GROUP)

    def _get_vrrp_params(self, api, resource_data):
        vrrp_params = {}
        vrrp_params['advertised_interval'] = self.advertised_interval
        vrrp_params['preempt_delay'] = self.preempt_delay
        vrrp_params['cluster_name'] = self._generate_cluster_name(
                                                        resource_data)
        vrrp_params['vrrp_group'] = self._generate_vrrp_group(resource_data)

        if api == "configure_ha":
            vrrp_params['sync_queue_size'] = self.sync_queue_size
            vrrp_params['queue_size'] = self.event_queue_size
            vrrp_params['mcast_group'] = self._get_multicast_group(
                                                                resource_data)
        return vrrp_params

    def _parse_nfd(self, nfd):
        monitoring_mac = None
        data_macs = {}
        networks = nfd.get('networks', {})
        for network in networks:
            if network['type'] == "monitor":
                monitoring_mac = network['ports'][0]['mac']
            elif network['type'] == "provider":
                data_macs['provider_mac'] = network['ports'][0]['mac']
            elif network['type'] == "stitching":
                data_macs['stitching_mac'] = network['ports'][0]['mac']

        vips = {}
        nfd_vips = nfd.get('vips', {})
        for nfd_vip in nfd_vips:
            if nfd_vip['type'] == "provider":
                vips["provider_vip"] = nfd_vip['ip']
            elif nfd_vip['type'] == "stitching":
                vips["stitching_vip"] = nfd_vip['ip']

        svc_mgmt_ip = nfd['svc_mgmt_fixed_ip']

        return svc_mgmt_ip, data_macs, vips, monitoring_mac

    def _rest_call(self, url, data, method):
        try:
            if method == common_const.CREATE:
                response = requests.post(url, data=data, timeout=self.timeout)
            elif method == common_const.DELETE:
                response = requests.delete(url, data=data,
                                           timeout=self.timeout)
            if response.status_code not in common_const.SUCCESS_CODES:
                LOG.exception("ERROR Response:%s\n" % response.content)
                raise Exception(response.content)
        except Exception as e:
            LOG.error("ERROR while configuring HA of %s.\n"
                      "Exception: %s" % (data, e))
            raise Exception(e)

    def configure_ha(self, context, resource_data):
        nfds = resource_data['nfds']
        for nfd in nfds:
            role = nfd['role']
            vrrp_params = self._get_vrrp_params("configure_ha", resource_data)
            vrrp_params.update({'priority':
                                [self.priority['active'] if role == 'master'
                                 else self.priority['standby']]})

            svc_mgmt_ip, data_macs, vips, monitoring_mac = self._parse_nfd(nfd)

            config = dict(vrrp_params,
                          monitoring_mac=monitoring_mac,
                          data_macs=data_macs,
                          vip=vips,
                          tenant_id=resource_data['tenant_id'])

            url = self.request_url % (svc_mgmt_ip, self.port,
                                      'configure_conntrack_sync')
            data = json.dumps(config)

            # TODO:(pritam) Use nfp task executor for _rest_call()
            # to parallelize it
            self._rest_call(url, data, common_const.CREATE)
            LOG.info("Succesfully configured HA of %s service at:%s\n"
                     % (role, svc_mgmt_ip))
        return common_const.STATUS_SUCCESS

    def clear_ha(self, context, resource_data):
        pass

    def configure_interfaces(self, context, resource_data):
        nfds = resource_data['nfds']
        for nfd in nfds:
            role = nfd['role']
            vrrp_params = self._get_vrrp_params("configure_interfaces",
                                                resource_data)
            vrrp_params.update({'priority':
                                [self.priority['active'] if role == 'master'
                                 else self.priority['standby']]})

            svc_mgmt_ip, data_macs, vips = self._parse_nfd(nfd)[0:3]

            config = dict(vrrp_params,
                          data_macs=data_macs,
                          vip=vips,
                          tenant_id=resource_data['tenant_id'])

            url = self.request_url % (svc_mgmt_ip, self.port,
                                      'configure_interface_ha')
            data = json.dumps(config)
            self._rest_call(url, data, common_const.CREATE)
            LOG.info("Succesfully configured interfaces HA of %s service at:%s"
                     % (role, svc_mgmt_ip))

            # TODO:(pritam) should we call add_persistent_rule api here ?
            self._add_persistent_rule(data_macs, svc_mgmt_ip)
        return common_const.STATUS_SUCCESS

    def _add_persistent_rule(self, rule_info, svc_mgmt_ip):
        url = self.request_url % (svc_mgmt_ip, self.port, 'add_rule')
        data = json.dumps(rule_info)
        self._rest_call(url, data, common_const.CREATE)
        LOG.info("Successfully added persistent rule %s for service at: %s "
                 % (rule_info, svc_mgmt_ip))

    def clear_interfaces(self, context, resource_data):
        nfds = resource_data['nfds']
        for nfd in nfds:
            role = nfd['role']
            svc_mgmt_ip, data_macs = self._parse_nfd(nfd)[0:2]

            # TODO:(pritam) - how to get cluster name ? Generate here ?
            # In SG's implementation cluster_name is passed in the request
            cluster_name = self._generate_cluster_name(resource_data)

            config = dict(data_macs=data_macs,
                          tenant_id=resource_data['tenant_id'],
                          cluster_name=cluster_name)
            url = self.request_url % (svc_mgmt_ip, self.port,
                                      'delete_vrrp')
            data = json.dumps(config)
            self._rest_call(url, data, common_const.DELETE)
            LOG.info("Successfully cleared interfaces HA of %s service at:%s"
                     % (role, svc_mgmt_ip))

            # TODO:(pritam) should we call delete persistent rule api here ?
            self._delete_persistent_rule(data_macs, svc_mgmt_ip)
        return common_const.STATUS_SUCCESS

    def _delete_persistent_rule(self, rule_info, svc_mgmt_ip):

        url = self.request_url % (svc_mgmt_ip, self.port, 'delete_rule')
        data = json.dumps(rule_info)
        self._rest_call(url, data, common_const.DELETE)
        LOG.info(" successfully deleted persistent rule %s for service at: %s "
                 % (rule_info, svc_mgmt_ip))

    def configure_routes(self, context, resource_data):
        return self._routes("configure_routes", context, resource_data)

    def clear_routes(self, context, resource_data):
        return self._routes("clear_routes", context, resource_data)

    def _routes(self, api, context, resource_data):
        nfds = resource_data['nfds']  # fetch nfds
        resource_data.pop('nfds')  # remove nfds from resource_data
        try:
            for nfd in nfds:
                # add single nfd to make it similar as if non HA api
                # is being called
                resource_data['nfds'] = [nfd]
                msg = ("Failed %s:%s for %s service vm"
                       % (api, resource_data, nfd['role']))
                method = getattr(super(VyosFWHADriver, self), api)
                result = method(context, resource_data)
                if result != common_const.STATUS_SUCCESS:
                    LOG.error(msg)
                    return result
        except Exception as e:
            LOG.error(msg)
            raise e
        finally:
            # restore all original nfds in resource_data
            resource_data['nfds'] = nfds
        return common_const.STATUS_SUCCESS

    def configure_healthmonitor(self, context, resource_data):
        # TODO:(pritam) - Modify generic config agent to loop on all the nfds
        # in the resource_data and when all the service vms are reachable
        # then only send result.
        try:
            return super(VyosFWHADriver, self).configure_healthmonitor(
                                                        context, resource_data)
        except Exception as e:
            raise e

    def create_firewall(self, context, firewall, host):
        return self._firewall("create_firewall", context, firewall, host)

    def update_firewall(self, context, firewall, host):
        return self._firewall("update_firewall", context, firewall, host)

    def delete_firewall(self, context, firewall, host):
        return self._firewall("delete_firewall", context, firewall, host)

    def _firewall(self, api, context, firewall, host):
        nfs = context['nfs']
        context.pop('nfs')
        msg = ""
        try:
            for nf in nfs:
                msg = ("Failed %s:%s for %s service vm"
                       % (api, firewall, nf['role']))
                context['nfs'] = [nf]
                method = getattr(super(VyosFWHADriver, self), api)
                result = method(context, firewall, host)
                if result == common_const.STATUS_ERROR:
                    LOG.error(msg)
                    return common_const.STATUS_ERROR
        except Exception as e:
            LOG.error(msg)
            raise e
        finally:
            context['nfs'] = nfs
        return common_const.STATUS_ACTIVE
