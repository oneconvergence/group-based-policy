# One Convergence, Inc. CONFIDENTIAL
# Copyright (c) 2012-2015, One Convergence, Inc., USA
# All Rights Reserved.
#
# All information contained herein is, and remains the property of
# One Convergence, Inc. and its suppliers, if any. The intellectual and
# technical concepts contained herein are proprietary to One Convergence,
# Inc. and its suppliers.
#
# Dissemination of this information or reproduction of this material is
# strictly forbidden unless prior written permission is obtained from
# One Convergence, Inc., USA

import array
import fcntl
import logging
import socket
import subprocess
import struct
import netifaces

from netifaces import AF_LINK
from vyos_session import utils

OP_SUCCESS = True
OP_FAILED = False

logger = logging.getLogger(__name__)
utils.init_logger(logger)

class APIHandler(object):
    def __init__(self):
        pass

    def run_command(self, command):
        proc = subprocess.Popen(command, 
                shell=True, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE)

        out, err = proc.communicate()
        if err:
            logger.error("Unable to run command %s,  ERROR- %s" % 
                (command, err))
            return None
        return out

    def _get_interface_name(self, interface_mac):
        interfaces = netifaces.interfaces()

        for interface in interfaces:
            try:
                mac_addr = netifaces.ifaddresses(interface)[AF_LINK][0]['addr']
                if mac_addr == interface_mac:
                    return interface

            except KeyError as keyerr:
                logger.error('Unable to Parse Stats Data, ' +
                    'KeyError: {}'.format(keyerr))
        return None

    def parse_firewall_stats(self, interface, raw_stats):
        firewall  = {}
        firewalls = []
        firewall_start = False
        table = False
        status = None
        rule_keys = ['rulepriority', 'packets', 'bytes', 'action',
                    'source', 'destination']

        try:
            for line in raw_stats.split('\n'):
                words = line.split()
                if 'IPv4 Firewall' in line:
                    firewall_start = True
                if 'Active on' in line and interface in line and firewall_start:
                    status = "Active"
                    (interface, direction) = words[2][1:-1].split(',')
                    firewall['interface'] = interface
                    firewall['dir'] = direction
                    firewall['rules'] = []
                elif len(words) >= 4:
                    if words[3] in ['ACCEPT', 'DROP'] and status == "Active":
                        table = True
                        rule = dict(zip(rule_keys, words))
                        firewall['rules'].append(rule)
                elif table and status == "Active":
                    firewalls.append(firewall)
                    firewall = {}
                    table = False

        except KeyError as keyerr:
            logger.error('Unable to Parse Firewall Stats Data, ' + 
                    'KeyError: {}'.format(keyerr))

        except IndexError as inderr:
            logger.error('Unable to Parse Firewall Stats Data, ' + 
                    'IndexError: {}'.format(inderr))

        return firewalls

    def parse_vpn_s2s(self, raw_stats):
        s2s_connection = {}
        s2s_connections = []
        
        try:
            for line in raw_stats.split('\n'):
                key = ''
                value = ''
                if ':' in line:
                    key,value = line.split(":")

                if 'Peer IP' in key:
                    s2s_connection['peerip'] = value.strip(" \t\n\r")

                elif 'Local IP' in key:
                    s2s_connection['localip'] = value.strip(" \t\n\r")

                elif "Tunnel" in key:
                    s2s_connection['tunnels'] = []
                    tunnel_info = { 'tunnel' : 
                                key.strip(" \t\n\r").split(" ")[-1] }

                elif "Inbound Bytes" in key:
                    tunnel_info['in']  = value.strip(" \t\n\r")

                elif "Outbound Bytes" in key:
                    tunnel_info['out']  = value.strip(" \t\n\r")
                    s2s_connection['tunnels'].append(tunnel_info)
                    s2s_connections.append(s2s_connection)
                    s2s_connection = {}

        except KeyError as keyerr:
            logger.error('Unable to Parse IPSec VPN Stats Data, ' + 
                        'KeyError: {}'.format(keyerr))

        except IndexError as inderr:
            logger.error('Unable to Parse IPSec VPN Stats Data, ' + 
                        'IndexError: {}'.format(inderr))

        return s2s_connections

    def parse_vpn_remote(self, raw_stats):
        table = False
        remote_connection = {}
        remote_connections = []
        keys = ['clientCN', 'remoteip', 'tunnelip', 'in', 'out']

        try:
            for line in raw_stats.split('\n'):
                if "Client CN" in line:
                    table = True
                elif len(line.split()) >= 5 and table and "---" not in line:
                    value_list = line.split()[:-5]
                    clients = filter(lambda value: value.strip(), value_list)
                    remote_connection = dict(zip(keys, clients))
                    remote_connections.append(remote_connection)

        except KeyError as keyerr:
            logger.error('Unable to Parse Remote VPN Stats Data, ' + 
                        'KeyError: {}'.format(keyerr))

        except IndexError as inderr:
            logger.error('Unable to Parse Remote VPN Stats Data, ' + 
                        'IndexError: {}'.format(inderr))

        return remote_connections

    def get_fw_stats(self, mac_address):
        interface = None
        parsed_stats = {}

        command = ('/opt/vyatta/bin/vyatta-show-firewall.pl "all_all" ' + 
                    '/opt/vyatta/share/xsl/show_firewall_statistics.xsl')

        raw_stats = self.run_command(command)
        interface = self._get_interface_name(mac_address)
        if not interface:
            logger.error('No interface available for mac address: %s' % 
                        mac_address)
            return parsed_stats
        parsed_stats = self.parse_firewall_stats(interface, raw_stats)

        logger.info("Firewall stats Data, \n %s" % parsed_stats)
        return parsed_stats

    def get_vpn_stats(self):
        vpn_parsed_data = {}
        command = ('sudo /opt/vyatta/bin/sudo-users/vyatta-op-vpn.pl ' + 
                    '--show-ipsec-sa-detail')

        raw_ipsec_stats = self.run_command(command)
        ipsec_parsed_data = self.parse_vpn_s2s(raw_ipsec_stats)
        if ipsec_parsed_data:
            vpn_parsed_data['ipsec'] = ipsec_parsed_data
        else:
            logger.warning("Empty IPSec VPN Stats")

        command = ('sudo /opt/vyatta/bin/sudo-users/vyatta-show-ovpn.pl ' + 
                    '--mode=server')

        raw_remote_stats = self.run_command(command)

        remote_parsed_data = self.parse_vpn_remote(raw_remote_stats)
        if remote_parsed_data:
            vpn_parsed_data['remote'] = remote_parsed_data
        else:
            logger.warning("Empty Remote VPN Stats")

        logger.info("VPN stats Data, \n %s" % vpn_parsed_data)
        return vpn_parsed_data

    def configure_rsyslog_as_client(self, config):
        command = """
                /opt/vyatta/sbin/vyatta-cfg-cmd-wrapper begin
                /opt/vyatta/sbin/vyatta-cfg-cmd-wrapper set system syslog host %s facility all level %s
                /opt/vyatta/sbin/vyatta-cfg-cmd-wrapper commit
                /opt/vyatta/sbin/vyatta-cfg-cmd-wrapper save
                """ %(config['server_ip'], config['log_level'])

        try:
            out = self.run_command(command)
            return OP_SUCCESS
        except Exception as ex:
            logger.error("Error while configuring rsyslog as client. %s" % ex)
            return OP_FAILED
