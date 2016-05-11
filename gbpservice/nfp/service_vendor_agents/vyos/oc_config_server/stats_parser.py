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

import logging
import subprocess
import netifaces

from netifaces import AF_LINK
from vyos_session import utils

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
        """
        sample data for command show_firewall_detail.xsl :

        IPv4 Firewall "oc_fw_eth1":

        Active on (eth1,OUT)

        rule  action   proto     packets  bytes
        ----  ------   -----     -------  -----
        11    accept   tcp       476405   24805598
          condition - saddr 11.0.1.0/24 daddr 11.0.2.0/24 tcp dpt:22

        12    accept   icmp      1222414  101692572
          condition - saddr 11.0.1.0/24 daddr 11.0.2.0/24

        13    drop     udp        150770055788 DROP
          condition - saddr 11.0.2.0/24 daddr /*

        14    accept   tcp       3589762  238449000
          condition - saddr 11.0.1.0/24 daddr 11.0.2.0/24 tcp dpt:80

        10000 drop     all       0        0
          condition - saddr 0.0.0.0/0 daddr 0.0.0.0/0

        """
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
                    command = ('/opt/vyatta/bin/vyatta-show-firewall.pl "all_all" ' +
                               '/opt/vyatta/share/xsl/show_firewall_detail.xsl')
                    show_fw_data = self.run_command(command)
                    firewall = self.add_protocol_and_dest_port_info(firewall, show_fw_data)
                    logger.info("packed firewall \n %s" % firewall)
                    firewalls.append(firewall)
                    break

        except KeyError as keyerr:
            logger.error('Unable to Parse Firewall Stats Data, ' +
                    'KeyError: {}'.format(keyerr))

        except IndexError as inderr:
            logger.error('Unable to Parse Firewall Stats Data, ' +
                    'IndexError: {}'.format(inderr))

        return firewalls

    def add_protocol_and_dest_port_info(self, firewall, show_fw_data):
        firewall_started = False
        firewall_info_started = False
        firewall_matcher = "Active on (" + firewall['interface']
        firewall_info_end = "-------------"
        firewall_info = []
        for line in show_fw_data.split('\n'):
            if "IPv4 Firewall" in line:
                firewall_started = True
            if firewall_matcher in line:
                firewall_info_started = True
            if firewall_started and firewall_info_started:
                firewall_info.append(line)
            if firewall_started and firewall_info_started and firewall_info_end in line:
                break
        try:
            for rule in firewall.get('rules', []):
                for index, stats in enumerate(firewall_info):
                    if stats is not '':
                        extract_stats = stats.split()
                        if rule['rulepriority'] in extract_stats[0]:
                            rule['protocol'] = extract_stats[2]
                            for key in firewall_info[index + 1].split():
                                if "dpt:" in key:
                                    rule['dest_port'] = key.split(':')[1]
                                    break
                            break

        except KeyError as keyerr:
            logger.error('Unable to Parse Firewall Stats Data, ' +
                    'KeyError: {}'.format(keyerr))

        except IndexError as inderr:
            logger.error('Unable to Parse Firewall Stats Data, ' +
                    'IndexError: {}'.format(inderr))

        return firewall

    def parse_vpn_s2s(self, raw_stats):
        """
        sample data for command show-ipsec-sa-detail :

        Peer IP:                192.168.20.194
        Peer ID:                120.0.0.2
        Local IP:               91.0.0.11
        Local ID:               91.0.0.11
        NAT Traversal:          no
        NAT Source Port:        n/a
        NAT Dest Port:          n/a

            Tunnel 1:
                State:                  up
                Inbound SPI:            c6621bd8
                Outbound SPI:           cbf2ab18
                Encryption:             aes128
                Hash:                   sha1
                PFS Group:              5

                Local Net:              90.0.0.0/24
                Local Protocol:         all
                Local Port:             all

                Remote Net:             120.0.0.0/24
                Remote Protocol:        all
                Remote Port:            all

                Inbound Bytes:          654.0
                Outbound Bytes:         504.0
                Active Time (s):        289
                Lifetime (s):           1800

        """
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
        """
        sample data for command vyatta-show-ovpn.pl --mode=server :

        OpenVPN server status on vtun0 []

        Client CN       Remote IP       Tunnel IP       TX byte RX byte Connected Since
        ---------       ---------       ---------       ------- ------- ---------------
        UNDEF           192.168.2.81    192.168.200.4      8.0K    2.7K Tue Mar  8 09:01:05 2016
        """
        table = False
        remote_connection = {}
        remote_connections = []
        keys = ['clientCN', 'remoteip', 'tunnelip', 'in', 'out', 'connected_since']

        try:
            for line in raw_stats.split('\n'):
                if "Client CN" in line:
                    table = True
                elif len(line.split()) >= 5 and table and "---" not in line:
                    value_list = line.split()[:-5]
                    connected_since = " ".join(line.split()[5:])
                    clients = filter(lambda value: value.strip(), value_list)
                    clients.append(connected_since)
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
        """
        sample data for command show_firewall_statistics.xsl :

        IPv4 Firewall "oc_fw_eth1":

        Active on (eth1,OUT)

        rule  packets   bytes     action  source              destination
        ----  -------   -----     ------  ------              -----------
        11    476.22K   24.80M    ACCEPT  11.0.1.0/24         11.0.2.0/24
        12    1.22M     101.66M   ACCEPT  11.0.1.0/24         11.0.2.0/24
        13    3.43G     150.73G   DROP    11.0.1.0/24         11.0.2.0/24
        14    3.59M     238.39M   ACCEPT  11.0.1.0/24         11.0.2.0/24
        10000 0         0         DROP    0.0.0.0/0           0.0.0.0/0

        """
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
        if raw_ipsec_stats:
            ipsec_parsed_data = self.parse_vpn_s2s(raw_ipsec_stats)
            if ipsec_parsed_data:
                vpn_parsed_data['ipsec'] = ipsec_parsed_data
            else:
                logger.warning("Empty IPSec VPN Stats")
        else:
            logger.warning("Empty IPSec VPN Stats")

        command = ('sudo /opt/vyatta/bin/sudo-users/vyatta-show-ovpn.pl ' +
                    '--mode=server')

        raw_remote_stats = self.run_command(command)
        if raw_remote_stats:
            remote_parsed_data = self.parse_vpn_remote(raw_remote_stats)
            if remote_parsed_data:
                vpn_parsed_data['remote'] = remote_parsed_data
            else:
                logger.warning("Empty Remote VPN Stats")
        else:
            logger.warning("Empty Remote VPN Stats")

        logger.info("VPN stats Data, \n %s" % vpn_parsed_data)
        return vpn_parsed_data
