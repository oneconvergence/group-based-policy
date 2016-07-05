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

import jsonutils
import logging
import netaddr
import netifaces
import subprocess
import time

from vyos_session import utils

ROUTING_TABLE_BASE = 10

logger = logging.getLogger(__name__)
utils.init_logger(logger)


class RoutesConfigHandler(object):

    def __init__(self):
        super(RoutesConfigHandler, self).__init__()

    def add_source_route(self, routes_info):
        routes_info = jsonutils.loads(routes_info)
        for route_info in routes_info:
            source_cidr = route_info['source_cidr']
            gateway_ip = route_info['gateway_ip']
            source_interface = self._get_if_name_by_cidr(source_cidr)
            try:
                interface_number_string = source_interface.split("eth", 1)[1]
            except IndexError:
                logger.error("Retrieved wrong interface %s for configuring "
                             "routes" % (source_interface))
            routing_table_number = ROUTING_TABLE_BASE + int(
                interface_number_string.split('v')[0])
            ip_rule_command = "ip rule add from %s table %s" % (
                source_cidr, routing_table_number)
            out1 = subprocess.Popen(ip_rule_command, shell=True,
                                    stdout=subprocess.PIPE).stdout.read()
            ip_rule_command = "ip rule add to %s table main" % (source_cidr)
            out2 = subprocess.Popen(ip_rule_command, shell=True,
                                    stdout=subprocess.PIPE).stdout.read()
            ip_route_command = "ip route add table %s default via %s" % (
                routing_table_number, gateway_ip)
            out3 = self._add_default_route_in_table(ip_route_command,
                                                    routing_table_number)
            output = "%s\n%s\n%s" % (out1, out2, out3)
            logger.info("Static route configuration result: %s" % (output))
        return jsonutils.dumps(dict(status=True))

    def _del_default_route_in_table(self, table):
        route_del_command = "ip route del table %s default" % (table)
        command_pipe = subprocess.Popen(route_del_command, shell=True,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE)
        out, err = command_pipe.communicate()
        if command_pipe.returncode != 0:
            logger.error("Deleting default route failed: %s" % (err))

    def _add_default_route_in_table(self, route_cmd, table):
        command_pipe = subprocess.Popen(route_cmd, shell=True,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE)
        out, err = command_pipe.communicate()
        # Delete the existing default route if any and retry
        if command_pipe.returncode != 0:
            if "File exists" in err:
                self._del_default_route_in_table(table)
            else:
                logger.error("Adding default route failed: %s" % (route_cmd))
                logger.error("Error: %s" % (err))
                raise Exception("Setting Default Table route failed")
        else:
            return out

        command_pipe = subprocess.Popen(route_cmd, shell=True,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE)
        out, err = command_pipe.communicate()
        if command_pipe.returncode != 0:
            logger.error("Adding default route failed: %s" % (route_cmd))
            logger.error("Error: %s" % (err))
            raise Exception("Setting Default Table route failed")
        else:
            return out

    def _delete_ip_rule(self, cidr):
        count = 0
        for direction in ["from", "to"]:
            ip_rule_cmd = "ip rule del %s %s" % (direction, cidr)
            while True:
                command_pipe = subprocess.Popen(ip_rule_cmd, shell=True,
                                                stdout=subprocess.PIPE,
                                                stderr=subprocess.PIPE)
                out, err = command_pipe.communicate()
                # Delete the existing default route if any and retry
                if command_pipe.returncode != 0 and "No such file" in err:
                    break
                else:
                    count = count + 1
                    if count >= 10:
                        logger.error("Deleting policy based routing for CIDR: "
                                     "%s not completed even after 10 attempts"
                                     % (cidr))
                        break

    # REVISIT(Magesh): There may be a chance that there are duplicate rules
    # May have to do a list and cleanup multiple entries
    def delete_source_route(self, routes_info):
        routes_info = jsonutils.loads(routes_info)
        for route_info in routes_info:
            source_cidr = route_info['source_cidr']
            source_interface = self._get_if_name_by_cidr(source_cidr)
            try:
                interface_number_string = source_interface.split("eth", 1)[1]
            except IndexError:
                logger.error("Retrieved wrong interface %s for deleting routes"
                             % (source_interface))
            routing_table_number = ROUTING_TABLE_BASE + int(
                interface_number_string.split('v')[0])
            self._delete_ip_rule(source_cidr)
            ip_route_command = "ip route del table %s default" % (
                routing_table_number)
            out = subprocess.Popen(ip_route_command, shell=True,
                                   stdout=subprocess.PIPE).stdout.read()
            logger.info("Static route delete result: %s" % (out))
        return jsonutils.dumps(dict(status=True))

    def _get_if_name_by_cidr(self, cidr):
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
                            len(subnet_prefix) == 1 or subnet_prefix[
                                                                1] == "32")):
                        return interface
                    ip_address_netmask = '%s/%s' % (ip_address, netmask)
                    interface_cidr = netaddr.IPNetwork(ip_address_netmask)
                    if str(interface_cidr.cidr) == cidr:
                        return interface
            # Sometimes the hotplugged interface takes time to get IP
            if not all_interfaces_have_ip:
                if retry_count < 10:
                    time.sleep(3)
                    retry_count = retry_count + 1
                    continue
                else:
                    raise Exception("Some of the interfaces do not have "
                                    "IP Address")
