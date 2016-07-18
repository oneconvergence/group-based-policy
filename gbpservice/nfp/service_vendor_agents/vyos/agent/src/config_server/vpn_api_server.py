#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import array
import copy
import fcntl
import logging
import socket
import struct
import subprocess
import time

from execformat.executor import session
from netaddr import IPAddress
from netaddr import IPNetwork
from operations import ConfigOpts
from vyos_session import utils

SUCCESS = True
FAILED = False

OP_COMMAND_SCRIPT = "/usr/share/vyos/vpn_op_commands.pl"

IPSEC_SITE2SITE_COMMANDS = {
    'ike': [
        'set vpn ipsec ike-group %s proposal 1',
        'set vpn ipsec ike-group %s proposal 1 encryption %s',
        'set vpn ipsec ike-group %s proposal 1  hash %s',
        'set vpn ipsec ike-group %s proposal 2 encryption %s',
        'set vpn ipsec ike-group %s proposal 2 hash %s',
        'set vpn ipsec ike-group %s lifetime %d',
        'set vpn ipsec ike-group %s dead-peer-detection action restart',
        'set vpn ipsec ike-group %s dead-peer-detection interval %s',
        'set vpn ipsec ike-group %s dead-peer-detection timeout %s'],
    'esp': [
        'set vpn ipsec esp-group %s proposal 1',
        'set vpn ipsec esp-group %s proposal 1 encryption %s',
        'set vpn ipsec esp-group %s proposal 1 hash %s',
        'set vpn ipsec esp-group %s proposal 2 encryption %s',
        'set vpn ipsec esp-group %s proposal 2 hash %s',
        'set vpn ipsec esp-group %s lifetime %d',
        'set vpn ipsec auto-update 60'],
    'conn': [
        'set vpn ipsec ipsec-interfaces interface %s',
        'set vpn ipsec site-to-site peer %s \
            authentication mode pre-shared-secret',
        'set vpn ipsec site-to-site peer %s \
            authentication pre-shared-secret %s',
        'set vpn ipsec site-to-site peer %s default-esp-group %s',
        'set vpn ipsec site-to-site peer %s ike-group %s',
        'set vpn ipsec site-to-site peer %s local-address %s',
        'set vpn ipsec site-to-site peer %s authentication remote-id %s',
        'set vpn ipsec site-to-site peer %s tunnel %d local prefix %s',
        'set vpn ipsec site-to-site peer %s tunnel %d remote prefix %s',
        'set vpn ipsec site-to-site peer %s authentication id %s'],
    'delete': [
        'delete vpn ipsec site-to-site peer %s',
        'delete vpn ipsec site-to-site peer %s tunnel %s',
        'delete vpn ipsec'],
    'show': [
        'show vpn ipsec sa peer %s']}

SSL_VPN_COMMANDS = {
    'create': [
        'set interfaces openvpn %s',
        'set interfaces openvpn %s mode server',
        'set interfaces openvpn %s server subnet %s',
        'set interfaces openvpn %s tls ca-cert-file /config/auth/ca.crt',
        'set interfaces openvpn %s tls cert-file /config/auth/server.crt',
        'set interfaces openvpn %s tls dh-file /config/auth/dh.pem',
        'set interfaces openvpn %s tls key-file /config/auth/server.key',
        'set interfaces openvpn %s server push-route %s',
        'set interfaces openvpn %s openvpn-option \
            "--client-cert-not-required --script-security 3 \
            --auth-user-pass-verify /usr/share/vyos/auth_pam.pl via-file"'],
    'delete': [
        'delete interfaces openvpn %s',
        'delete interfaces openvpn vtun0 server push-route %s']}

logger = logging.getLogger(__name__)
utils.init_logger(logger)


class NoInterfaceOnCidr(Exception):

    def __init__(self, **kwargs):
        self.message = _("No interface in the network '%(cidr)s'") % kwargs


class VPNHandler(ConfigOpts):

    def __init__(self):
        super(VPNHandler, self).__init__()

    def create_ipsec_site_conn(self, ctx):
        session.setup_config_session()
        siteconn = ctx['siteconns'][0]
        self._create_ike_group(siteconn['ikepolicy'],
                               siteconn['connection']['dpd'])
        self._create_esp_group(siteconn['ipsecpolicy'])
        self._create_ipsec_site_conn(ctx)
        session.commit()
        session.save()
        time.sleep(2)
        session.teardown_config_session()
        return SUCCESS

    def create_ipsec_site_tunnel(self, tunnel):
        session.setup_config_session()
        self._create_ipsec_site_tunnel(tunnel)
        session.commit()
        session.save()
        time.sleep(2)
        session.teardown_config_session()
        return SUCCESS

    def _ipsec_get_tunnel_idx(self, tunnel):
        command = 'perl'
        command += " " + OP_COMMAND_SCRIPT
        command += " " + 'get_ipsec_tunnel_idx'
        command += " " + tunnel['peer_address']
        command += " " + tunnel['local_cidr']
        command += " " + tunnel['peer_cidr']
        proc = subprocess.Popen(
            command, shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        out, err = proc.communicate()
        tunidx = out.split('=')[1]
        return int(tunidx)

    def _ipsec_get_tunnel_count(self, tunnel):
        command = 'perl'
        command += " " + OP_COMMAND_SCRIPT
        command += " " + 'get_ipsec_tunnel_count'
        command += " " + tunnel['peer_address']
        proc = subprocess.Popen(
            command, shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        out, err = proc.communicate()
        tuncount = out.split('=')[1]
        return int(tuncount)

    def delete_ipsec_site_tunnel(self, tunnel):
        try:
            session.setup_config_session()
            self._delete_ipsec_site_tunnel(tunnel)
            session.commit()
            session.save()
            time.sleep(2)
            session.teardown_config_session()
            return SUCCESS
        except Exception as ex:
            logger.error("Error in deleting ipsec site tunnel. %s" % ex)
            return FAILED

    def delete_ipsec_site_conn(self, peer_address):
        try:
            session.setup_config_session()
            self._delete_ipsec_site_conn(peer_address)
            session.commit()
            session.save()
            time.sleep(2)
            session.teardown_config_session()
            return SUCCESS
        except Exception as ex:
            logger.error("Error in deleting ipsec site connection. %s" % ex)
            return FAILED

    def get_ipsec_site_tunnel_state(self, tunnel):
        tunidx = self._ipsec_get_tunnel_idx(tunnel)
        command = 'perl'
        command += " " + OP_COMMAND_SCRIPT
        command += " " + 'get_ipsec_tunnel_state'
        command += " " + tunnel['peer_address']
        command += " " + str(tunidx)
        proc = subprocess.Popen(
            command, shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        out, err = proc.communicate()
        state = out.split('=')[1]
        state = state[:-1]
        return SUCCESS, state

    def _delete_ipsec_site_tunnel(self, tunnel):
        tunidx = self._ipsec_get_tunnel_idx(tunnel)
        cmds = copy.deepcopy(IPSEC_SITE2SITE_COMMANDS)
        cmd = cmds['delete'][1]

        cmd = cmd % (tunnel['peer_address'], tunidx)

        self._set_commands([cmd])

    def _delete_ipsec_site_conn(self, peer_address):
        cmds = copy.deepcopy(IPSEC_SITE2SITE_COMMANDS)
        cmd = cmds['delete'][2]

        self._set_commands([cmd])

    def _set_commands(self, cmds):
        for cmd in cmds:
            logger.debug(cmd)
            self.set_full(cmd.split(' '))

    def _create_ike_group(self, ike, dpd):
        cmds = copy.deepcopy(IPSEC_SITE2SITE_COMMANDS)
        ike_cmds = cmds['ike']

        ike_cmds[0] = ike_cmds[0] % (ike['name'])
        ike_cmds[1] = ike_cmds[1] % (ike['name'], ike['encryption_algorithm'])
        ike_cmds[2] = ike_cmds[2] % (ike['name'], ike['auth_algorithm'])
        ike_cmds[3] = ike_cmds[3] % (ike['name'], ike['encryption_algorithm'])
        ike_cmds[4] = ike_cmds[4] % (ike['name'], ike['auth_algorithm'])
        ike_cmds[5] = ike_cmds[5] % (ike['name'], ike['lifetime']['value'])
        ike_cmds[6] = ike_cmds[6] % ike['name']
        ike_cmds[7] = ike_cmds[7] % (ike['name'], dpd['interval'])
        ike_cmds[8] = ike_cmds[8] % (ike['name'], dpd['timeout'])
        self._set_commands(ike_cmds)

    def _create_esp_group(self, esp):
        cmds = copy.deepcopy(IPSEC_SITE2SITE_COMMANDS)
        esp_cmds = cmds['esp']

        esp_cmds[0] = esp_cmds[0] % (esp['name'])
        esp_cmds[1] = esp_cmds[1] % (esp['name'], esp['encryption_algorithm'])
        esp_cmds[2] = esp_cmds[2] % (esp['name'], esp['auth_algorithm'])
        esp_cmds[3] = esp_cmds[3] % (esp['name'], esp['encryption_algorithm'])
        esp_cmds[4] = esp_cmds[4] % (esp['name'], esp['auth_algorithm'])
        esp_cmds[5] = esp_cmds[5] % (esp['name'], esp['lifetime']['value'])

        self._set_commands(esp_cmds)

    def _create_ipsec_site_tunnel(self, tunnel):
        cmds = copy.deepcopy(IPSEC_SITE2SITE_COMMANDS)
        conn_cmds = cmds['conn']
        tun_cmds = ['', '']

        tunidx = self._ipsec_get_tunnel_count(tunnel) + 1
        """
        Neutron + GBP model supports only one local subnet.
        For now also assuming only one peer cidr.
        """
        tun_cmds[0] = conn_cmds[7] % (
            tunnel['peer_address'], tunidx, tunnel['local_cidr'])
        tun_cmds[1] = conn_cmds[8] % (
            tunnel['peer_address'], tunidx, tunnel['peer_cidrs'][0])

        self._set_commands(tun_cmds)

    def _create_ipsec_site_conn(self, ctx):
        cmds = copy.deepcopy(IPSEC_SITE2SITE_COMMANDS)
        conn_cmds = cmds['conn']

        """
        Get the name of the interface which has ipaddr from
        the local cidr on which vpn service is launched.
        Also get the ip addr assigned to it
        """
        ifname, ip = self._get_if_details_by_cidr(ctx['service']['cidr'])

        conn = ctx['siteconns'][0]['connection']
        esp = ctx['siteconns'][0]['ipsecpolicy']
        ike = ctx['siteconns'][0]['ikepolicy']

        conn_cmds[0] = conn_cmds[0] % (ifname)
        conn_cmds[1] = conn_cmds[1] % (conn['peer_address'])
        conn_cmds[2] = conn_cmds[2] % (conn['peer_address'], conn['psk'])
        conn_cmds[3] = conn_cmds[3] % (conn['peer_address'], esp['name'])
        conn_cmds[4] = conn_cmds[4] % (conn['peer_address'], ike['name'])
        conn_cmds[5] = conn_cmds[5] % (conn['peer_address'], ip)
        conn_cmds[6] = conn_cmds[6] % (conn['peer_address'], conn['peer_id'])

        """
        Neutron + GBP model supports only one local subnet.
        For now also assuming only one peer cidr.
        """
        conn_cmds[7] = conn_cmds[7] % (
            conn['peer_address'], 1, conn['tunnel_local_cidr'])
        conn_cmds[8] = conn_cmds[8] % (
            conn['peer_address'], 1, conn['peer_cidrs'][0])
        conn_cmds[9] = conn_cmds[9] % (conn['peer_address'], conn['access_ip'])

        self._set_commands(conn_cmds)

    def configure_static_route(self, action, cidr, gateway_ip):
        if action == "set":
            route_cmd = ("%s protocols static route %s next-hop"
                         " %s distance 1" % (action, cidr, gateway_ip))
        else:
            route_cmd = "%s protocols static route %s" % (action, cidr)
        # The config module we use everywhere else is not used here
        # because of the issue mentioned here:
        # http://vyatta38.rssing.com/chan-10627532/all_p7.html
        # Note: The issue is inconsistent, but not seen anymore with this
        # new approach of setting configuration
        utils._alternate_set_and_commit(route_cmd)
        return SUCCESS

    def _get_all_ifs(self):
        max_possible = 128  # arbitrary. raise if needed.
        bytes = max_possible * 32
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        names = array.array('B', '\0' * bytes)
        outbytes = struct.unpack('iL', fcntl.ioctl(
            s.fileno(),
            0x8912,  # SIOCGIFCONF
            struct.pack('iL', bytes, names.buffer_info()[0])
        ))[0]
        namestr = names.tostring()
        lst = []
        for i in range(0, outbytes, 40):
            name = namestr[i:i + 16].split('\0', 1)[0]
            ip = namestr[i + 20:i + 24]
            lst.append((name, ip))
        return lst

    def _format_ip(self, addr):
        return str(ord(addr[0])) + '.' + \
            str(ord(addr[1])) + '.' + \
            str(ord(addr[2])) + '.' + \
            str(ord(addr[3]))

    def _get_if_details_by_cidr(self, cidr):
        """
        Get interface name and ip address which is in the
        given cidr
        """
        # It is observed sometimes that infs take time to get ip address
        logger.info("IPSec: get interface ip and name for cidr %s." % cidr)
        retry_count = 0
        while True:
            ifs = self._get_all_ifs()
            for inf in ifs:
                ifname = inf[0]
                if 'v' in ifname:
                    continue
                ip = self._format_ip(inf[1])
                if IPAddress(ip) in IPNetwork(cidr):
                    logger.info("Found interface %s for cidr %s" % (ifname,
                                                                    cidr))
                    return ifname, ip
            if retry_count < 10:
                time.sleep(1)
                retry_count += 1
                continue
            break

        raise NoInterfaceOnCidr(cidr=cidr)
