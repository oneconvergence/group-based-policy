import keepalived_cfg
import constants
import commands
import logging

HAPROXY_BINARY_PATH = '/usr/sbin/keepalived'
KEEPALIVED_CONFIG_FILE_ABS_PATH = '/etc/keepalived/keepalived.conf'
HAPROXY_PID_FILE_ABS_PATH = '/var/run/haproxy.pid'


class KeepalivedDriver:

    def __init__(self, logger):
        self.logger = logger

    def _get_vrrp_instance(self, logical_config):
        try:
            vrrp_instance = logical_config["vrrp_instance"]['LB_1']
        except Exception, e:
            self.logger.error('Unable to get vrrp_instance for config: %s' % logical_config)
            raise(e)
        return vrrp_instance

    def setup_ha(self, logical_config, active_mgmt_ip, standby_mgmt_ip,
                 priority, interface='eth0'):
        try:
            vrrp_instance = self._get_vrrp_instance(logical_config)
            vrrp_instance['interface'] = interface
            vrrp_instance['priority'] = priority
            vrrp_instance['unicast_src_ip'] = active_mgmt_ip
            vrrp_instance['track_interface'].append(interface)
            vrrp_instance['unicast_peer'].append(standby_mgmt_ip)
            keepalived_cfg.save_config(logical_config,
                                       constants.KEEPALIVED_CONFIG_FILE_ABS_PATH)
            self.restart_keepalived_service()
        except Exception, e:
            self.logger.error('Unable to setup ha for config: %s' % logical_config)
            raise(e)

    def create_vip_config(self, logical_config, vip_ip, interface):
        try:
            vrrp_instance = self._get_vrrp_instance(logical_config)
            vip_ip_entry = keepalived_cfg.get_virtual_ipaddress(vip_ip, interface)
            vrrp_instance['virtual_ipaddress'].append(vip_ip_entry)
            vrrp_instance['track_interface'].append(interface)
            keepalived_cfg.save_config(logical_config,
                                       constants.KEEPALIVED_CONFIG_FILE_ABS_PATH)
        except Exception, e:
            self.logger.error('Unable to create vip config for vip: %s and \
                                interface: %s' % (vip_ip, interface))
            raise(e)
        else:
            self.restart_keepalived_service()

    def delete_vip_config(self, logical_config, vip_ip, interface):
        try:
            vrrp_instance = self._get_vrrp_instance(logical_config)
            vip_ip_entry = keepalived_cfg.get_virtual_ipaddress(vip_ip, interface)
            vrrp_instance['virtual_ipaddress'].remove(vip_ip_entry)
            vrrp_instance['track_interface'].remove(interface)
            keepalived_cfg.save_config(logical_config,
                                       constants.KEEPALIVED_CONFIG_FILE_ABS_PATH)
            self.restart_keepalived_service()
        except Exception, e:
            self.logger.error('Unable to delete vip config for vip: %s and \
                                interface: %s' % (vip_ip, interface))
            raise(e)

    def is_ha_setup(self, logical_config):
        vrrp_instance = self._get_vrrp_instance(logical_config)
        if vrrp_instance['interface']:
            return True
        return False 

    def is_vip_configured(self, logical_config, vip_ip, interface):
        try:
            vrrp_instance = self._get_vrrp_instance(logical_config)
            vip_ip_entry = keepalived_cfg.get_virtual_ipaddress(vip_ip, interface)
            if vip_ip_entry in vrrp_instance['virtual_ipaddress']:
                return True
            else:
                return False
        except Exception, e:
            self.logger.error('failed while getting vip: %s configuration: %s' % (vip_ip, interface))
            raise(e)

    def restart_keepalived_service(self):
        command = ['sudo',
                   'service',
                   'keepalived',
                   'restart']
        status, _ = commands.getstatusoutput(' '.join(command))
        if status != 0:
            raise Exception("command %s failed" % ' '.join(command))

    def stop_keepalived_service(self):
        command = ['sudo',
                   'service',
                   'keepalived',
                   'stop']
        status, _ = commands.getstatusoutput(' '.join(command))

