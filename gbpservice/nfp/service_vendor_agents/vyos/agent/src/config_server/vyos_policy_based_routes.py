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

import copy
import json
import logging
import subprocess
import time

import netaddr
import netifaces
from operations import configOpts
from vyos_session import utils

ROUTING_TABLE_BASE = 10

logger = logging.getLogger(__name__)
utils.init_logger(logger)


VYOS_PBR_COMMANDS = {
    'policy_route': [
        'set policy route %s rule %s protocol all',
        'set policy route %s rule %s set table %s',
        'set policy route %s rule %s source address %s'],
    'table_route': [
        'set protocols static table %s route %s next-hop %s'],
    'interface_pbr': [
        'set interfaces ethernet %s policy route %s'],
    'delete': [
        'delete interfaces ethernet %s policy route %s',
        'delete policy route %s',
        'delete protocols static table %s'],
    'show': [
        'show policy route %s',
        'show  protocols static table %s',
        'show interfaces ethernet %s policy route']}


class RoutesConfigHandler(configOpts):

    def __init__(self):
        super(RoutesConfigHandler, self).__init__()
        self.vyos_wrapper = "/opt/vyatta/sbin/vyatta-cfg-cmd-wrapper"

    def _run_command(self, command):
        try:
            exec_pipe = subprocess.Popen(command, shell=True,
                                         stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE)
        except Exception as err:
            message = 'Executing command %s failed with error %s' % (
                command, err)
            logger.error(message)
            return False

        cmd_output, cmd_error = exec_pipe.communicate()
        if exec_pipe.returncode != 0:
            message = 'Executing command %s failed with error %s' % (
                command, cmd_error)
            logger.error(message)
            return False
        else:
            logger.debug('command output: %s', cmd_output)
            return True

    def _begin_command(self):
        begin_cmd = "%s begin" % (self.vyos_wrapper)
        if self._run_command(begin_cmd):
            return True
        else:
            return False

    def _discard_changes(self):
        discard_cmd = "%s discard" % (self.vyos_wrapper)
        if self._run_command(discard_cmd):
            return True
        else:
            return False

    def _set_commands(self, cmds):
        for cmd in cmds:
            set_cmd = "%s %s" % (self.vyos_wrapper, cmd)
            if not self._run_command(set_cmd):
                return False
        return True

    def _commit_command(self):
        commit_cmd = "%s commit" % (self.vyos_wrapper)
        if self._run_command(commit_cmd):
            return True
        else:
            return False

    def _save_command(self):
        save_cmd = "%s save" % (self.vyos_wrapper)
        if self._run_command(save_cmd):
            return True
        else:
            return False

    def _configure_vyos(self, configure_commands):
        if not self._begin_command():
            logger.error("Starting a vyos session failed")
            return False

        if not self._set_commands(configure_commands):
            logger.error("Executing commands %s failed" % (configure_commands))
            self._discard_changes()
            return False

        if not self._commit_command():
            logger.error("Committing %s failed" % (configure_commands))
            self._discard_changes()
            return False

        if not self._save_command():
            logger.error("Saving %s failed" % (configure_commands))
            self._discard_changes()
            return False

        return True

    def _configure_policy_route(self, source_cidr, gateway_ip,
                                source_interface):
        try:
            interface_number_string = source_interface.split("eth", 1)[1]
        except IndexError:
            logger.error("Retrieved wrong interface %s for configuring "
                         "routes" % (source_interface))
            msg = "Wrong interface %s retrieved for source %s" % (
                source_interface, source_cidr)
            raise Exception(msg)
        routing_table_number = ROUTING_TABLE_BASE + int(
            interface_number_string.split('v')[0])
        pbr_name = "%s_%s" % ("pbr", source_interface)
        cmds = copy.deepcopy(VYOS_PBR_COMMANDS)
        pbr_commands = []
        pbr_commands.append(cmds['policy_route'][0] % (pbr_name, "1"))
        pbr_commands.append(cmds['policy_route'][1] % (
            pbr_name, "1", routing_table_number))
        pbr_commands.append(
            cmds['policy_route'][2] % (pbr_name, "1", source_cidr))

        pbr_commands.append(cmds['table_route'][0] % (
            routing_table_number, "0.0.0.0/0", gateway_ip))

        pbr_commands.append(
            cmds['interface_pbr'][0] % (source_interface, pbr_name))

        if not self._configure_vyos(pbr_commands):
            logger.error("Configuring Policy Based Routing failed")
            raise Exception("Pbr failed %s" % pbr_commands)
        else:
            return True

    def add_source_route(self, routes_info):
        routes_info = json.loads(routes_info)
        for route_info in routes_info:
            source_cidr = route_info['source_cidr']
            gateway_ip = route_info['gateway_ip']
            source_interface = self._get_if_name_by_cidr(source_cidr)
            try:
                self._delete_policy_route(source_cidr, source_interface)
            except Exception as err:
                logger.debug("Trying to clear any existing routes before "
                             "setting source routing failed with error: %s"
                             % (err))
            try:
                self._configure_policy_route(
                    source_cidr, gateway_ip, source_interface)
            except Exception as err:
                message = ("Configuring Policy based route failed. "
                           "Error: %s" % (err))
                raise Exception(message)
        return json.dumps(dict(status=True))

    # FIXME: When invoked on delete path we have to propagate the error
    def _delete_policy_route(self, source_cidr, source_interface):
        try:
            interface_number_string = source_interface.split("eth", 1)[1]
        except IndexError:
            logger.error("Retrieved wrong interface %s for configuring "
                         "routes" % (source_interface))
            msg = "Wrong interface %s retrieved for source %s" % (
                source_interface, source_cidr)
            raise Exception(msg)
        routing_table_number = ROUTING_TABLE_BASE + int(
            interface_number_string.split('v')[0])
        pbr_name = "%s_%s" % ("pbr", source_interface)
        cmds = copy.deepcopy(VYOS_PBR_COMMANDS)

        delete_pbr_commands = []
        delete_pbr_commands.append(cmds['delete'][0] % (
            source_interface, pbr_name))
        if not self._configure_vyos(delete_pbr_commands):
            logger.warn("Deleting PBR failed")

        delete_pbr_commands = []
        delete_pbr_commands.append(cmds['delete'][1] % (pbr_name))
        if not self._configure_vyos(delete_pbr_commands):
            logger.warn("Deleting PBR failed")

        delete_pbr_commands = []
        delete_pbr_commands.append(cmds['delete'][2] % (routing_table_number))
        if not self._configure_vyos(delete_pbr_commands):
            logger.warn("Deleting PBR failed")

        return

    def delete_source_route(self, routes_info):
        routes_info = json.loads(routes_info)
        for route_info in routes_info:
            source_cidr = route_info['source_cidr']
            source_interface = self._get_if_name_by_cidr(source_cidr,
                                                         delete=True)
            if source_interface:
                self._delete_policy_route(source_cidr, source_interface)
        return json.dumps(dict(status=True))

    def _get_if_name_by_cidr(self, cidr, delete=False):
        interfaces = netifaces.interfaces()
        retry_count = 0
        while True:
            all_interfaces_have_ip = True
            for interface in interfaces:
                inet_list = netifaces.ifaddresses(interface).get(
                    netifaces.AF_INET)
                if not inet_list:
                    all_interfaces_have_ip = False
                for inet_info in inet_list or []:
                    netmask = inet_info.get('netmask')
                    ip_address = inet_info.get('addr')
                    subnet_prefix = cidr.split("/")
                    if (ip_address == subnet_prefix[0] and (
                            len(subnet_prefix) == 1 or (
                                            subnet_prefix[1] == "32"))):
                        return interface
                    ip_address_netmask = '%s/%s' % (ip_address, netmask)
                    interface_cidr = netaddr.IPNetwork(ip_address_netmask)
                    if str(interface_cidr.cidr) == cidr:
                        return interface
            # Sometimes the hotplugged interface takes time to get IP
            if not all_interfaces_have_ip:
                if retry_count < 15:
                    if delete:
                        return None
                    time.sleep(2)
                    retry_count = retry_count + 1
                    continue
                else:
                    raise Exception("Some of the interfaces do not have "
                                    "IP Address")
