import cfg
import keepalived_cfg
import commands
import eventlet
import netifaces
import os
import socket
import time
import traceback

import constants
import lockutils
from netifaces import AF_INET, AF_INET6, AF_LINK, AF_PACKET, AF_BRIDGE
from keepalived_config_driver import KeepalivedDriver

HAPROXY_BINARY_PATH = '/usr/sbin/haproxy'
HAPROXY_CONFIG_FILE_ABS_PATH = '/etc/haproxy/haproxy.cfg'
HAPROXY_PID_FILE_ABS_PATH = '/var/run/haproxy.pid'

HAPROXY_SOCK_ABS_PATH = '/etc/haproxy/stats'
HAPROXY_RSYSLOG_CONF_FILE_ABS_PATH = "/etc/rsyslog.d/haproxy.conf"


class HaproxyDriver:

    def __init__(self, logger):
        self.update_haproxy = False
        self.logger = logger
        self.keepalived_driver = KeepalivedDriver(self.logger)
        self.logical_config = dict()
        self._update_default_config()
        self._update_default_keepalived_config()
        self._update_existing_keepalived_config()
        self._update_existing_config()
        self._spawn()

    def _update_default_config(self):
        server_ip = cfg.get_interface_to_bind()
        self.logical_config = {
            "global": {
                "daemon": True,
                "user": "nobody",
                "group": "nogroup",
                "log": {
                    "/dev/log": {
                        "local0": [
                        ],
                        "local1": [
                            "notice"
                        ]
                    }
                },
                "stats" : {
                    "socket": {
                        HAPROXY_SOCK_ABS_PATH : {"level": "admin"}
                              }
                          }
            },
            "defaults": {
                "log": "global",
                "retries": 3,
                "option": {
                    "redispatch": True
                },
                "timeout": {
                    "connect": 5000,
                    "client": 50000,
                    "server": 50000
                },
            },
            "listen": {
                "stats " + server_ip + ":1936": {
                    "mode": "http",
                    "stats": {
                        "enable": True,
                        "uri": "/",
                        "hide-version": True,
                        "auth": "admin:haproxy"
                    }
                }
            },
            'frontends': {},
            'backends': {}
        }

    def _update_default_keepalived_config(self):
        self.keepalived_config = keepalived_cfg.conf

    def _update_existing_keepalived_config(self):
        vip_info = self._get_vip_info(HAPROXY_CONFIG_FILE_ABS_PATH)
        keepalived_cfg.update_existing_config(self.keepalived_config,
                                              constants.KEEPALIVED_CONFIG_FILE_ABS_PATH,
                                              vip_info)
        if self.keepalived_driver.is_ha_setup(self.keepalived_config):
            self.keepalived_driver.restart_keepalived_service()
            self.logger.debug('Started keepalived service with config: %s' % self.keepalived_config)
        else:
            self.keepalived_driver.stop_keepalived_service()

    def _update_existing_config(self):
        config = cfg.get_existing_config(HAPROXY_CONFIG_FILE_ABS_PATH)
        self.logical_config['frontends'] = config['frontends']
        self.logical_config['backends'] = config['backends']
        for frontend in config['frontends']:
            vip_ip = config['frontends'][frontend]['bind'].split(':')[0]
            provider_interface_mac = config['frontends'][frontend]['#provider_interface_mac']
            provider_standby_interface_mac = config['frontends'][frontend]['#standby_provider_interface_mac']
            interface_mac = self._get_interface_mac(
                                provider_interface_mac,
                                provider_standby_interface_mac)
            self._add_vip_ip(vip_ip, interface_mac)
        self._kill_dhcp()

    def _get_vip_info(self, config_file):
        frontends = cfg.get_existing_frontends(config_file)
        vip_info = {}
        for frontend in frontends:
            vip_ip = frontends[frontend]['bind'].split(':')[0]
            provider_interface_mac = frontends[frontend]['#provider_interface_mac']
            provider_standby_interface_mac = frontends[frontend].get('#standby_provider_interface_mac')
            interface_mac = self._get_interface_mac(
                                provider_interface_mac,
                                provider_standby_interface_mac)
            interface_name = self._get_interface_name(interface_mac)
            vip_info[vip_ip] = [interface_mac, interface_name]
        return vip_info

    # Send Gratuitous arp to inform the fabric of the vip ip
    def _arping(self, interface_name, ip_address):
        eventlet.sleep(10)
        arping_cmd = ['arping', '-U', ip_address, '-S', ip_address, '-P',
                      '-I', interface_name, '-c', '5']
        try:
            commands.getstatusoutput(' '.join(arping_cmd))
        except Exception as e:
            self.logger.error("Failed sending gratuitous ARP: %s", str(e))
        # Do it once more in case the previous one was not processed
        eventlet.sleep(60)
        arping_cmd = ['arping', '-U', ip_address, '-S', ip_address, '-P',
                      '-I', interface_name, '-c', '5']
        try:
            commands.getstatusoutput(' '.join(arping_cmd))
        except Exception as e:
            self.logger.error("Failed sending gratuitous ARP: %s", str(e))

    def _add_vip_ip(self, vip_ip, interface_mac):
        interface_name = self._get_interface_name(interface_mac)
        if (self.keepalived_driver.is_ha_setup(self.keepalived_config) and
            not self.keepalived_driver.is_vip_configured(self.keepalived_config,
                                                    vip_ip, interface_name)):
            self.keepalived_driver.create_vip_config(self.keepalived_config,
                                                     vip_ip, interface_name)
            self.logger.debug('Created %s vip in keepalived config' % vip_ip)
            time.sleep(5)
        else:
            command = ['sudo',
                       'ip', 'addr',
                       'add',
                       'dev', interface_name,
                       vip_ip]
            commands.getstatusoutput(' '.join(command))
        route_cmd = ['sudo',
                     'bash',
                     '/etc/dhcp/dhclient-exit-hooks.d/haproxy_routing']
        commands.getstatusoutput(' '.join(route_cmd))

        eventlet.spawn_n(self._arping, interface_name, vip_ip)

    def _remove_vip_ip(self, vip_ip, frontend):
        provider_interface_mac = frontend.get('#provider_interface_mac')
        if frontend.get('#standby_provider_interface_mac'):
            standby_provider_interface_mac = frontend.get('#standby_provider_interface_mac')
        else:
            standby_provider_interface_mac = None
        interface_mac = self._get_interface_mac(
                                provider_interface_mac,
                                standby_provider_interface_mac)

        interface_name = self._get_interface_name(interface_mac)
        #command = ['sudo',
        #           'ip', 'addr',
        #           'del',
        #           'dev', interface_name,
        #           vip_ip]
        #commands.getstatusoutput(' '.join(command))
        if self.keepalived_driver.is_ha_setup(self.keepalived_config):
            self.keepalived_driver.delete_vip_config(self.keepalived_config,
                                                     vip_ip, interface_name)
            self.logger.debug('deleted %s vip from keepalived config' % vip_ip)

    def _get_interface_name(self, interface_mac):
        interfaces = netifaces.interfaces()
        for interface in interfaces:
            mac_addr = netifaces.ifaddresses(interface)[AF_LINK][0]['addr']

            if mac_addr == interface_mac:
                return interface

    def _get_interface_mac(self, provider_interface_mac, standby_provider_interface_mac):
        interfaces = netifaces.interfaces()
        for interface in interfaces:
            mac_addr = netifaces.ifaddresses(interface)[AF_LINK][0]['addr']
            if mac_addr == provider_interface_mac:
                interface_mac = mac_addr
                break
            elif mac_addr == standby_provider_interface_mac:
                interface_mac = mac_addr
                break
            else:
                interface_mac = None
        return interface_mac

    def _kill_dhcp(self):
        command = ['sudo',
                   'killall', 'dhclient']
        commands.getstatusoutput(' '.join(command))

    def _request_dhcp(self, interface):
        command = ['sudo',
                   'dhclient', interface]
        commands.getstatusoutput(' '.join(command))
    def _spawn(self):
        cfg.save_config(self.logical_config, HAPROXY_CONFIG_FILE_ABS_PATH)
        command = ['sudo',
                   HAPROXY_BINARY_PATH,
                   '-f', HAPROXY_CONFIG_FILE_ABS_PATH,
                   '-p', HAPROXY_PID_FILE_ABS_PATH]
        if self.update_haproxy:
            command.extend(['-sf'])
            command.extend(p.strip() for p in open(HAPROXY_PID_FILE_ABS_PATH, 'r'))
        else:
            self.update_haproxy = True
        commands.getstatusoutput(' '.join(command))

    def _kill(self):
        command = ['sudo',
                   'pkill',
                   'haproxy']
        commands.getstatusoutput(' '.join(command))

    @lockutils.synchronized('haproxy_agent', 'sync-')
    def create_frontend(self, frontend):
        self.logger.debug("create frontend : %s\n old frontend : "
                  "%s" %(repr(frontend), repr(self.logical_config['frontends'])))
        interface_mac = None
        if frontend.values():
            frontend_dict = frontend.values()[0]
            provider_interface_mac = frontend_dict.pop('provider_interface_mac')
            if frontend_dict.get('standby_provider_interface_mac'):
                standby_provider_interface_mac = frontend_dict.pop('standby_provider_interface_mac')
            else:
                standby_provider_interface_mac = None
            interface_mac = self._get_interface_mac(
                                provider_interface_mac,
                                standby_provider_interface_mac)
            frontend_dict['#provider_interface_mac'] = provider_interface_mac
            frontend_dict['#standby_provider_interface_mac'] = standby_provider_interface_mac

        self.logical_config['frontends'].update(frontend)

        for v in frontend.itervalues():
            frontend = v
            break
        vip_ip = frontend['bind'].split(':')[0]

        try:
            interface_name = self._get_interface_name(interface_mac)
            self._request_dhcp(interface_name)
            self._add_vip_ip(vip_ip, interface_mac)
            self._kill_dhcp()
        except:
            self.logger.error('Unable to kill dhclient')
        self._spawn()

    @lockutils.synchronized('haproxy_agent', 'sync-')
    def update_frontend(self, frnt_id, frontend):
        self.logger.debug("update frontend : %s\n old frontend : "
                  "%s" %(repr(frontend), repr(self.logical_config['frontends'])))
        self.logical_config['frontends'].update({frnt_id: frontend})
        self._spawn()

    @lockutils.synchronized('haproxy_agent', 'sync-')
    def delete_frontend(self, frnt_id):
        self.logger.debug("delete frontend : %s, existing frontends : "
                  "%s"  %(frnt_id, repr(self.logical_config['frontends'])))
        frontend = self.show_frontend(frnt_id)
        frontend_copy = frontend.copy()
        vip_ip = frontend['bind'].split(':')[0]
        del self.logical_config['frontends'][frnt_id]
        self._spawn()
        # Comment it for Sungard, We don't need to remove vip ip,
        # As we are deleting interface, vip alias ip will also get remove.
        # We don't have interface mac in delete, we need interface mac to
        # identify corresponding interface, similar way which we are doing in create.
        # In sungard we not supported case of multiple vips per interface.
        self._remove_vip_ip(vip_ip, frontend_copy)

    def show_frontend(self, frnt_id):
        self.logger.debug("show frontend : %s, existing frontends : "
                  "%s"  %(frnt_id, repr(self.logical_config['frontends'])))
        return self.logical_config['frontends'][frnt_id]

    @lockutils.synchronized('haproxy_agent', 'sync-')
    def list_frontends(self):
        return self.logical_config['frontends'].keys()

    @lockutils.synchronized('haproxy_agent', 'sync-')
    def create_backend(self, backend):
        self.logger.debug("create backend : %s\n old backend : "
                  "%s" %(repr(backend), repr(self.logical_config['backends'])))
        self.logical_config['backends'].update(backend)
        self._spawn()

    @lockutils.synchronized('haproxy_agent', 'sync-')
    def update_backend(self, bck_id, backend):
        self.logger.debug("update backend : %s\n old backend : "
                  "%s" %(repr(backend), repr(self.logical_config['backends'])))
        self.logical_config['backends'].update({bck_id: backend})
        self._spawn()

    @lockutils.synchronized('haproxy_agent', 'sync-')
    def delete_backend(self, bck_id):
        self.logger.debug("delete backend : %s, existing backends : "
                  "%s"  %(bck_id, repr(self.logical_config['backends'])))
        # Assuming frontend is deleted prior to this request
        del self.logical_config['backends'][bck_id]
        self._spawn()

    @lockutils.synchronized('haproxy_agent', 'sync-')
    def show_backend(self, bck_id):
        self.logger.debug("show backend : %s, existing backends : "
                  "%s"  %(bck_id, repr(self.logical_config['backends'])))
        return self.logical_config['backends'][bck_id]

    @lockutils.synchronized('haproxy_agent', 'sync-')
    def list_backends(self):
        return self.logical_config['backends'].keys()

    def get_stats(self, pool_id):
        #TODO: pool_id usage
        backend_exist = None
        backends = self.logical_config['backends']
        if backends:
            backend_exist = len([key for key in backends if pool_id in key])
        if (not backends or not backend_exist):
            err = 'Backend: %s not exist in deployed config' % pool_id
            self.logger.error('error : %s', err)
            raise Exception(err)

        socket_path = HAPROXY_SOCK_ABS_PATH
        TYPE_BACKEND_REQUEST = 2
        TYPE_SERVER_REQUEST = 4
        try:
          if os.path.exists(socket_path):
            parsed_stats = self._get_stats_from_socket(
                socket_path,
                entity_type=TYPE_BACKEND_REQUEST | TYPE_SERVER_REQUEST)
            stats = self._get_backend_stats(parsed_stats)
            stats['members'] = self._get_servers_stats(parsed_stats)
            return stats
          else:
            self.logger.error('Stats socket not found for pool %s', pool_id)
            return {}
        except Exception, err:
            self.logger.error('exception : %s and exception : %s', err, traceback.format_exc())

    def _get_backend_stats(self, parsed_stats):
        TYPE_BACKEND_RESPONSE = '1'
        for stats in parsed_stats:
            if stats.get('type') == TYPE_BACKEND_RESPONSE:
                unified_stats = dict((k, stats.get(v, ''))
                                     for k, v in cfg.STATS_MAP.items())
                return unified_stats
        return {}

    def _get_servers_stats(self, parsed_stats):
        TYPE_SERVER_RESPONSE = '2'
        res = {}
        for stats in parsed_stats:
            if stats.get('type') == TYPE_SERVER_RESPONSE:
                res[stats['svname']] = {
                    constants.STATS_STATUS: (constants.INACTIVE
                                            if stats['status'] == 'DOWN'
                                            else constants.ACTIVE),
                    constants.STATS_HEALTH: stats['check_status'],
                    constants.STATS_FAILED_CHECKS: stats['chkfail']
                }
        return res

    def _get_stats_from_socket(self, socket_path, entity_type):
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.connect(socket_path)
            s.send('show stat -1 %s -1\n' % entity_type)
            raw_stats = ''
            chunk_size = 1024
            while True:
                chunk = s.recv(chunk_size)
                raw_stats += chunk
                if len(chunk) < chunk_size:
                    break

            return self._parse_stats(raw_stats)
        except socket.error as e:
            self.logger.error('Error while connecting to stats socket: %s', e)
            return {}

    def _parse_stats(self, raw_stats):
        stat_lines = raw_stats.splitlines()
        if len(stat_lines) < 2:
            return []
        stat_names = [name.strip('# ') for name in stat_lines[0].split(',')]
        res_stats = []
        for raw_values in stat_lines[1:]:
            if not raw_values:
                continue
            stat_values = [value.strip() for value in raw_values.split(',')]
            res_stats.append(dict(zip(stat_names, stat_values)))

        return res_stats

    @lockutils.synchronized('haproxy_agent', 'sync-')
    def sync_config(self, logical_config):
        try:
            if logical_config:
                frontends = self.get_frontends_from_cfg(logical_config)
                for frontend in frontends:
                    frnt_cfg = frontends[frontend]
                    vip_ip = frnt_cfg['bind'].split(':')[0]
                    provider_interface_mac = frnt_cfg.get('provider_interface_mac')
                    if frnt_cfg.get('standby_provider_interface_mac'):
                        standby_provider_interface_mac = frnt_cfg.get('standby_provider_interface_mac')
                    else:
                        standby_provider_interface_mac = None
                    interface_mac = self._get_interface_mac(
                                            provider_interface_mac,
                                            standby_provider_interface_mac)
                    self._add_vip_ip(vip_ip, interface_mac)
                self.deploy_instance(logical_config)
        except Exception, err:
            self.logger.error('exception : %s and exception : %s', err,
                              traceback.format_exc())

    def deploy_instance(self, logical_config):
        self._update_default_config()
        frontends = self.get_frontends_from_cfg(logical_config)
        backends = self.get_backends_from_cfg(logical_config)
        self.logical_config['frontends'] = frontends
        self.logical_config['backends'] = backends
        self.logger.info('Deploying following config : %s',
                          self.logical_config)
        self._spawn()

    def get_frontends_from_cfg(self, logical_config):
        frontends = {}
        for key in logical_config:
            if 'frnt' in key:
                frontends[key] = logical_config[key]
        return frontends

    def get_backends_from_cfg(self, logical_config):
        backends = {}
        for key in logical_config:
            if 'bck' in key:
                backends[key] = logical_config[key]
        return backends

    def setup_ha(self, body):
        if self.keepalived_driver.is_ha_setup(self.keepalived_config):
            self.logger.info('HA already set in keepalived config')
            return
        active_mgmt_ip = body['active_monitoring_ip']
        standby_mgmt_ip = body['standby_monitoring_ip']
        active_mgmt_mac = body['active_monitoring_mac']
        standby_mgmt_mac = body['standby_monitoring_mac']
        active_priority  = body['active_priority']
        standby_priority = body['standby_priority']
        interfaces = netifaces.interfaces()
        for interface in interfaces:
            mac_addr = netifaces.ifaddresses(interface)[AF_LINK][0]['addr']
            if mac_addr == active_mgmt_mac:
                active_ip = active_mgmt_ip
                standby_ip = standby_mgmt_ip
                priority = active_priority
                mgmt_interface = interface
                break
            elif mac_addr == standby_mgmt_mac:
                active_ip = standby_mgmt_ip
                standby_ip = active_mgmt_ip
                priority = standby_priority
                mgmt_interface = interface
                break
            else:
                active_ip = standby_ip = None
        if not active_ip or not standby_ip:
            raise Exception('HA not configured')
        self.logger.debug('setup_ha body = %s' % body)
        self.keepalived_driver.setup_ha(self.keepalived_config,
                                        active_ip, standby_ip,
                                        priority, mgmt_interface)

    def get_lbstats_from_socket(self, socket_path):
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.connect(socket_path)
            s.send('show stat\n')
            raw_stats = ''
            chunk_size = 1024
            while True:
                chunk = s.recv(chunk_size)
                raw_stats += chunk
                if len(chunk) < chunk_size:
                    break

            return self._parse_stats(raw_stats)
        except socket.error as e:
            self.logger.error('Error while connecting to stats socket: %s', e)
            return {}

    def get_pool_id(self, vip_id):
        frontend_info = False
        pool_id = None

        command = ['sudo', 'cat', HAPROXY_CONFIG_FILE_ABS_PATH]
        status, output = commands.getstatusoutput(' '.join(command))

        if status >= 0 and output:
            for line in output.split('\n'):
                if ( "frontend frnt:" + vip_id ) in line:
                    frontend_info = True
                elif frontend_info and "default_backend bck:" in line:
                    pool_id = line.strip().split(':')[1]

        return pool_id

    def get_lbstats(self, vip_id):
        filtered_stats = []
        pool_id = self.get_pool_id(vip_id)

        socket_path = HAPROXY_SOCK_ABS_PATH
        try:
            if os.path.exists(socket_path):
                parsed_stats = self.get_lbstats_from_socket(
                                socket_path)
                for proxy in parsed_stats:
                    if vip_id in proxy['pxname']:
                        filtered_stats.append(proxy)
                    if pool_id and pool_id in proxy['pxname']:
                        filtered_stats.append(proxy)
                return { 'stats' : filtered_stats }
            else:
                self.logger.error('Stats socket not found for vip %s', vip_id)
                return {}
        except Exception, err:
            self.logger.error('exception : %s and exception : %s',
                             err, traceback.format_exc())
            return {}

    def is_configured(self, ip, port):
        config_to_check = "@" + ip + ":" + port
        command = ['sudo', 'cat', HAPROXY_RSYSLOG_CONF_FILE_ABS_PATH]
        status, output = commands.getstatusoutput(' '.join(command))

        if status >= 0 and output:
            for line in output.split('\n'):
                if config_to_check in line:
                    return True
        return False

    def configure_rsyslog_as_client(self, config):
        OP_FAILED = { 'status' : False }
        OP_SUCCESS = { 'status' : True }
        try:
            ip = config['server_ip']
            port = str(config['server_port'])
            if self.is_configured(ip, port):
                return OP_SUCCESS
            config_command = ['sed',
                              '-i',
                              "'1 i\*.* @" + ip + ":" + port + "' ",
                              HAPROXY_RSYSLOG_CONF_FILE_ABS_PATH
                            ]

            status, output = commands.getstatusoutput(' '.join(config_command))
            if status >= 0:
                restart_command = ['service', 'rsyslog', 'restart']
                status, output = commands.getstatusoutput(' '.join(
                                            restart_command))
                if status >= 0:
                    return OP_SUCCESS
                else:
                    self.logger.error('failed to execute command : %s',
                                    restart_command)
                    return OP_FAILED
            else:
                self.logger.error('failed to execute command : %s',
                                    config_command)
                return OP_FAILED
        except Exception, err:
            self.logger.error('exception : %s and exception : %s',
                             err, traceback.format_exc())
            return OP_FAILED
