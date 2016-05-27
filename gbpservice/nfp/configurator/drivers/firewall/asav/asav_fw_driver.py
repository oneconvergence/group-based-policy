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

from gbpservice.nfp.core.common import ForkedPdb

import ast
import ipaddr
import iptools
import requests

from oslo_config import cfg
from oslo_log import log as logging
from oslo_serialization import jsonutils

from requests.auth import HTTPBasicAuth

from gbpservice.nfp.configurator.drivers.base import base_driver
from gbpservice.nfp.configurator.lib import fw_constants as const

LOG = logging.getLogger(__name__)

asav_auth_opts = [
    cfg.StrOpt(
        'mgmt_username',
        default='admin',
        help=('ASAv management user name')),
    cfg.StrOpt(
        'mgmt_userpass',
        default='b2Nhc2F2dm0=',
        help=('ASAv management user password')),
    cfg.StrOpt(
        'throughput_level',
        default='1G',
        help='throughput level'),
    cfg.StrOpt(
        'reg_token',
        default='',
        help='Token'),
    cfg.StrOpt('security_level',
               default='0',
               help='interface security level for asav'),
    cfg.StrOpt('radius_ip',
               help=('IP of radius server')),
    cfg.StrOpt('radius_secret',
               default='secret',
               help=('secret to talk to radius')),
    cfg.BoolOpt('scan_all_rule', default=False,
                help='Look for all rules in list for implicit deny')
]

""" REST API wrapper class that provides POST method to
communicate with the Service VM.

"""


class RestApi(object):
    def __init__(self, timeout):
        self.timeout = timeout
        self.content_header = {'Content-Type': 'application/json'}

    def post(self, url, data, auth_header, response_data_expected=None):
        """ Invokes REST POST call to the Service VM.

        :param url: URL to connect.
        :param data: data to be sent.
        :param auth_header: Authorization content to securely
        connect to the Service VM.
        :param response_data_expected: If set, the REST call to the Service VM
        returns the result of the call to the caller.

        Returns: SUCCESS/Error message/ Content of the POST response.

        """

        try:
            LOG.info("Initiating a POST call to URL: %r "
                     "with data: %r." % (url, data))
            data = jsonutils.dumps(data)
            resp = requests.post(url, data,
                                 headers=self.content_header, verify=False,
                                 auth=auth_header, timeout=self.timeout)
        except requests.exceptions.SSLError as err:
            msg = ("REST API POST request failed for ASAv. "
                   "URL: %r, Data: %r. Error: %r" % (
                            url, data, str(err).capitalize()))
            LOG.error(msg)
            return msg
        except Exception as err:
            msg = ("Failed to issue POST call "
                   "to service. URL: %r, Data: %r. Error: %r" %
                   (url, data, str(err).capitalize()))
            LOG.error(msg)
            return msg

        try:
            result = resp.json()
        except ValueError as err:
            msg = ("Unable to parse response, invalid JSON. URL: "
                   "%r. %r" % (url, str(err).capitalize()))
            LOG.error(msg)
            return msg
        if resp.status_code not in const.SUCCESS_CODES:
            msg = ("Successfully issued a POST call. However, the result "
                   "of the POST API is negative. URL: %r. Response code: %s."
                   "Result: %r." % (url, resp.status_code, result))
            LOG.error(msg)
            return msg
        LOG.info("Successfully issued a POST call and the result of "
                 "the API operation is positive. URL: %r. Result: %r. "
                 "Status Code: %r." % (url, result, resp.status_code))
        return (
            const.STATUS_SUCCESS
            if not response_data_expected
            else dict(GET_RESPONSE=result))

""" Firewall generic configuration driver for handling device
configuration requests.

"""


class FwGenericConfigDriver(base_driver.BaseDriver):
    def __init__(self):
        pass

    def configure_bulk_cli(self, mgmt_ip, commands=None,
                           response_data_expected=None):
        """ Prepares the set of commands in such a way so that it issues
            a bulk REST call to ASAv.

        Bulk REST call can contain all those commands that can
        be input through CLI.

        :param mgmt_ip: Management IP address of the Service VM
        :param commands: list of commands
        :param response_data_expected: If set, the REST call to the Service VM
        returns the result of the call to the caller.

        Returns: Result of the REST call.

        """

        resource_uri = "/api/cli"
        url = const.ASAV_REQUEST_URL % (mgmt_ip, resource_uri)

        if not response_data_expected or not commands:
            commands.append('write memory')
        data = {"commands": commands}

        return self.rest_api.post(url, data, self.auth, response_data_expected)

    def _get_interface_commands(self, interface_name, interface_index,
                                interface_ip, interface_net_mask,
                                security_level,
                                asav_interface_type='gigabitEthernet',
                                mac_address=None):
        """ Calculates the interface position.

        :param interface_name: Name of the interface
        :param interface_index: Position of the interface
        :param interface_ip: IP address of the interface
        :param interface_net_mask: Subnet mask of the interface
        :param security_level: Security level to be associated with
        the interface
        :param asav_interface_type: Management/Gigabitethernet
        :param mac_address: MAC address of the interface

        Returns: A list of commands to configure interface.

        """

        commands = list()
        commands.append("interface " + asav_interface_type + " 0/" +
                        interface_index)
        commands.append("nameif " + interface_name)
        commands.append("security-level " + security_level)
        command = "ip address " + interface_ip + " " + interface_net_mask

        commands.append(command)
        commands.append("no shutdown")

        allow_inter_interface_traffic = ("same-security-traffic permit "
                                         "inter-interface")
        commands.append(allow_inter_interface_traffic)
        return commands

    def get_interface_position(self, mgmt_ip, mac):
        """ Calculates the interface position.

        :param mgmt_ip: Management IP address of the Service VM
        :param mac: MAC address of the VM for which the
        interface position has to be found.

        Returns: interface index.

        """

        commands = list()

        commands.append("sh inte")
        result = self.configure_bulk_cli(mgmt_ip, commands,
                                         response_data_expected=True)

        if result.get('GET_RESPONSE'):
            data = ''.join(result['GET_RESPONSE']['response']).split(
                                                        'GigabitEthernet0/')
            for item in data:
                if mac in item:
                    return item[0]

    def _get_device_interface_name(self, cidr):
        """ Prepares the interface name.

        :param cidr: CIDR of the interface

        Returns: interface name.

        """

        return 'interface-' + cidr.replace('/', '_')

    def configure_interfaces(self, context, resource_data):
        """ Configures interfaces for the service VM.

        :param context: neutron context
        :param resource_data: a dictionary of firewall rules and objects
        send by neutron plugin

        Returns: SUCCESS/Failure message with reason.

        """

        try:
            mgmt_ip = resource_data['mgmt_ip']
            provider_ip = resource_data.get('provider_ip')
            provider_cidr = resource_data.get('provider_cidr')
            provider_mac = resource_data.get('provider_mac')
            stitching_ip = resource_data.get('stitching_ip')
            stitching_cidr = resource_data.get('stitching_cidr')
            stitching_mac = resource_data.get('stitching_mac')
            provider_interface_position = resource_data.get(
                                    'provider_interface_index')
            stitching_interface_position = resource_data.get(
                                    'stitching_interface_index')

            (provider_mac, stitching_mac) = self.get_asav_macs(
                [provider_mac, stitching_mac])

            provider_interface_position = self.get_interface_position(
                                                        mgmt_ip, provider_mac)
            stitching_interface_position = str(int(
                                            provider_interface_position) + 1)

            provider_macs = [provider_mac]
            stitching_macs = [stitching_mac]
        except Exception as err:
            msg = ("Failed before issuing a configure interfaces"
                   " call. Error: %r." % err)
            LOG.error(msg)
            raise Exception(msg)

        commands = list()
        try:
            provider_mask = str(ipaddr.IPv4Network(provider_cidr).netmask)
            stitching_mask = str(ipaddr.IPv4Network(stitching_cidr).netmask)

            provider_intf_name = self._get_device_interface_name(provider_cidr)
            stitching_intf_name = self._get_device_interface_name(
                                                            stitching_cidr)

            security_level = cfg.CONF.ASAV_CONFIG.security_level
            commands = self._get_interface_commands(
                provider_intf_name, str(provider_interface_position),
                provider_ip, provider_mask, security_level,
                mac_address=provider_macs)
            result = self.configure_bulk_cli(mgmt_ip, commands)
            if result is not const.STATUS_SUCCESS:
                return result

            commands = self._get_interface_commands(
                stitching_intf_name, str(stitching_interface_position),
                stitching_ip, stitching_mask, security_level,
                mac_address=stitching_macs)
            result = self.configure_bulk_cli(mgmt_ip, commands)
            if result is not const.STATUS_SUCCESS:
                msg = ("Failed to configure ASAv interfaces. Reason: %r" %
                       result)
                LOG.error(msg)
            else:
                msg = ("Configure ASAv interfaces.")
                LOG.info(msg)
            return result
        except Exception as err:
            LOG.error(_("Exception while configuring interface. "
                        "commands: %s, Reason: %s" % (commands, err)))
            raise Exception(err)

    def clear_interfaces(self, context, resource_data):
        """ Clears interfaces of the service VM.

        :param context: neutron context
        :param resource_data: a dictionary of firewall rules and objects
        send by neutron plugin

        Returns: SUCCESS/Failure message with reason.

        """

        mgmt_ip = resource_data['mgmt_ip']
        provider_interface_position = str(int(resource_data[
                                            'provider_interface_index']) - 2)
        stitching_interface_position = str(int(resource_data[
                                            'stitching_interface_index']) - 2)

        commands = []
        provider_interface_id = self._get_asav_interface_id(
                                                provider_interface_position)
        stitching_interface_id = self._get_asav_interface_id(
                                                stitching_interface_position)
        try:
            commands.append("clear configure interface " +
                            provider_interface_id)
            commands.append("clear configure interface " +
                            stitching_interface_id)
            result = self.configure_bulk_cli(mgmt_ip, commands)

            if result is not const.STATUS_SUCCESS:
                msg = ("Failed to clear ASAv interfaces. Reason: %r" %
                       result)
                LOG.error(msg)
            else:
                msg = ("Cleared ASAv interfaces.")
                LOG.info(msg)
            return result
        except Exception as err:
            LOG.error(_("Exception while clearing interface config. "
                        "commands: %s, Reason: %s" % (commands, err)))
            raise Exception(err)

    def configure_routes(self, context, resource_data):
        """ Configure routes for the service VM.

        Issues REST call to service VM for configuration of routes.

        :param context: neutron context
        :param resource_data: a dictionary of firewall rules and objects
        send by neutron plugin

        Returns: SUCCESS/Failure message with reason.

        """

        return self.configure_pbr_route(context, resource_data)

    def clear_routes(self, context, resource_data):
        """ Clear routes for the service VM.

        Issues REST call to service VM for deletion of routes.

        :param context: neutron context
        :param resource_data: a dictionary of firewall rules and objects
        send by neutron plugin

        Returns: SUCCESS/Failure message with reason.

        """

        return self.delete_pbr_route(context, resource_data)

    def _get_asav_interface_id(self, interface_position):
        """ Prepares the interface id.

        :param interface_position: Position of the interface in the Service VM.

        Returns: physical interface name.

        """

        return 'GigabitEthernet0/' + str(interface_position)

    def configure_pbr_route(self, context, resource_data):
        """ Configure Policy Based routes for the service VM.

        Issues REST call to service VM for configuration of routes.

        :param context: neutron context
        :param resource_data: a dictionary of firewall rules and objects
        send by neutron plugin

        Returns: SUCCESS/Failure message with reason.

        """

        mgmt_ip = resource_data['mgmt_ip']
        source_cidr = resource_data['source_cidrs'][0]
        destination_cidr = resource_data['destination_cidr']
        gateway_ip = resource_data['gateway_ip']
        provider_mac = resource_data.get('provider_mac')

        source_network = str(ipaddr.IPv4Network(source_cidr).ip)
        source_mask = str(ipaddr.IPv4Network(source_cidr).netmask)
        asav_provider_mac = self.get_asav_mac(provider_mac)

        provider_interface_position = self.get_interface_position(
                                                    mgmt_ip, asav_provider_mac)

        interface_id = self._get_asav_interface_id(provider_interface_position)
        permit_traffic_list = ['ip']
        commands = []
        try:
            for protocol in permit_traffic_list:
                commands.append("access-list pbracl%s extended permit %s %s"
                                " %s 0 0" % (
                                    source_cidr.replace('/', '_'), protocol,
                                    source_network, source_mask))
            commands.append("route-map pbrmap%s permit 1" % (
                                    source_cidr.replace('/', '_')))
            commands.append("match ip address pbracl" +
                            source_cidr.replace('/', '_'))
            commands.append("set ip next-hop " + gateway_ip)
            commands.append("interface " + interface_id)
            commands.append("policy-route route-map pbrmap%s" % (
                                    source_cidr.replace('/', '_')))

            result = self.configure_bulk_cli(mgmt_ip, commands)
            if result is not const.STATUS_SUCCESS:
                return result

            # Add interface based default ruote to stitching gw
            dest_interface_name = self._get_device_interface_name(
                                                            destination_cidr)
            adm_distance = int(provider_interface_position) + 2
            command = list()
            command.append("route " + dest_interface_name + " 0 0 " +
                           gateway_ip + " " + str(adm_distance))
            dns_config = self._configure_dns(dest_interface_name)
            command.extend(dns_config)
            result = self.configure_bulk_cli(mgmt_ip, command)

            if result is not const.STATUS_SUCCESS:
                msg = ("Failed to configure ASAv routes. Reason: %r" %
                       result)
                LOG.error(msg)
            else:
                msg = ("Configure ASAv routes.")
                LOG.info(msg)
            return result

        except Exception as err:
            LOG.error(_("Exception while configuring pbr route. "
                        "commands: %s, Reason: %s" % (commands, err)))
            raise Exception(err)

    def _configure_dns(self, dest_interface):
        """ Prepares the command to configure DNS for the specified interface.

        :param dest_interface: Interface name

        Returns: a list of command.

        """

        commands = []
        commands.append("dns domain-lookup %s" % dest_interface)
        return commands

    def delete_pbr_route(self, context, resource_data):
        """ Clears Policy Based routes for the service VM.

        Issues REST call to service VM for deletion of routes.

        :param context: neutron context
        :param resource_data: a dictionary of firewall rules and objects
        send by neutron plugin

        Returns: SUCCESS/Failure message with reason.

        """

        mgmt_ip = resource_data['mgmt_ip']
        source_cidr = resource_data['source_cidrs'][0]
        provider_mac = resource_data['provider_mac']
        try:
            provider_interface_position = self.get_interface_position(
                                                        mgmt_ip, provider_mac)

            commands = []
            interface_id = self._get_asav_interface_id(
                                                provider_interface_position)
            commands.append("interface " + interface_id)
            commands.append("no policy-route route-map pbrmap" +
                            source_cidr.replace('/', '_'))
            commands.append("no route-map pbrmap" + source_cidr.replace(
                '/', '_'))
            commands.append("clear configure access-list pbracl" +
                            source_cidr.replace('/', '_'))
            commands.append("clear configure interface " + interface_id)

            self.configure_bulk_cli(mgmt_ip, commands)
        except Exception as err:
            msg = ("Exception while deleting pbr route. "
                   "commands: %s, Reason: %s" % (commands, err))
            LOG.error(msg)
            return msg
        else:
            return const.STATUS_SUCCESS

    @staticmethod
    def get_asav_mac(mac_addr):
        """ Converts standard MAC address to ASAv format.

        :param mac_addr: MAC address

        Returns: ASAv MAC address.

        """

        if not mac_addr:
            raise Exception('Get asav mac received an empty mac address')
        l = mac_addr.split(':')
        asav_mac = ""
        for i in range(0, len(l), 2):
            asav_mac += (l[i] + l[i+1] + ".")

        return asav_mac[:-1]

    @staticmethod
    def get_asav_macs(mac_list):
        """ Converts standard MAC address to ASAv format.

        :param mac_addr: A list of MAC addresses

        Returns: A tuples of ASAv MAC addresses.

        """
        asav_mac_list = list()
        for mac_addr in mac_list:
            if not mac_addr:
                asav_mac_list.append(None)
                continue
            l = mac_addr.split(':')
            asav_mac = ""
            for i in range(0, len(l), 2):
                asav_mac += (l[i] + l[i+1] + ".")
            asav_mac_list.append(asav_mac[:-1])

        return tuple(asav_mac_list)

""" Firewall as a service driver for handling firewall
service configuration requests.

We initialize service type and service vendor in this class because
agent loads class object only for those driver classes that have service
type and service vendor as class attributes. Also, only this driver
class is exposed to the agent.

"""


class FwaasDriver(FwGenericConfigDriver):
    service_type = const.SERVICE_TYPE
    service_vendor = const.ASAV

    def __init__(self, conf):
        self.conf = conf
        self.register_config_options()
        self.timeout = const.REST_TIMEOUT
        self.rest_api = RestApi(self.timeout)
        self.port = const.ASAV_CONFIGURATION_SERVER_PORT
        self.auth = HTTPBasicAuth(cfg.CONF.ASAV_CONFIG.mgmt_username,
                                  cfg.CONF.ASAV_CONFIG.mgmt_userpass)
        super(FwaasDriver, self).__init__()

    def register_config_options(self):
        """ Registers the config options.

        Returns: None

        """

        self.conf.register_opts(asav_auth_opts, 'ASAV_CONFIG')

    def get_rules(self, firewall, interface):
        """ Prepares ASAv specific firewall rules from the
        standard firewall rules template.

        :param firewall: type - dict
        :param interface: type - string, the interface for which ACLs need
        to get configured.

        Returns: list of dict()

        """

        rules = firewall["firewall_rule_list"]
        asav_rules = list()
        for rule in rules:
            source_port = rule['source_port']
            destination_port = rule['destination_port']
            if rule["destination_ip_address"]:
                if rule["destination_ip_address"] == const.REFRENCE_IPS[
                                                                'WILDCARD']:
                    destinationAddress = dict(
                        kind="AnyIPAddress",
                        value=rule["destination_ip_address"])
                elif iptools.ipv4.validate_cidr(
                        rule["destination_ip_address"]):
                    destinationAddress = dict(
                        kind="IPv4Network",
                        value=rule["destination_ip_address"])
                elif iptools.ipv4.validate_ip(rule["destination_ip_address"]):
                    destinationAddress = dict(
                        kind="IPv4Address",
                        value=rule["destination_ip_address"])

            if rule["source_ip_address"]:
                if rule["source_ip_address"] == const.REFRENCE_IPS['WILDCARD']:
                    sourceAddress = dict(kind="AnyIPAddress",
                                         value=rule["source_ip_address"])
                elif iptools.ipv4.validate_cidr(rule["source_ip_address"]):
                    sourceAddress = dict(kind="IPv4Network",
                                         value=rule["source_ip_address"])
                elif iptools.ipv4.validate_ip(rule["source_ip_address"]):
                    sourceAddress = dict(kind="IPv4Address",
                                         value=rule["source_ip_address"])
            else:
                sourceAddress = dict(kind="AnyIPAddress",
                                     value=const.REFRENCE_IPS['WILDCARD'])

            # Supported protocol: TCP, UDP and ICMP.
            # Agent doesn't do any validation of protocol and relies on plugin
            # or in case of Sungaard on UI to do validation.
            if source_port:
                if ':' in source_port:
                    source_port = '-'.join(source_port.split(':'))
                src_value = rule['protocol'] + "/" + str(source_port)
                sourceService = dict(kind="TcpUdpService",
                                          value=src_value)
            elif not source_port:
                sourceService = dict(kind="NetworkProtocol",
                                     value=rule["protocol"])

            if destination_port:
                if ':' in destination_port:
                    destination_port = '-'.join(destination_port.split(':'))
                dst_value = rule['protocol'] + "/" + str(destination_port)
                destinationService = dict(kind="TcpUdpService",
                                          value=dst_value)
            elif not destination_port:
                destinationService = dict(kind="NetworkProtocol",
                                          value=rule['protocol'])

            if rule["action"] == "allow":
                permit = True
            else:
                permit = False
            asav_access_rule = dict(
                position=rule['position'],
                permit=permit
            )

            try:
                asav_access_rule.update(
                    {'destinationAddress': destinationAddress})
            except NameError:
                pass

            try:
                asav_access_rule.update(
                    {'sourceAddress': sourceAddress})
            except NameError:
                pass

            try:
                asav_access_rule.update({'sourceService': sourceService})
            except NameError:
                pass

            try:
                asav_access_rule.update(
                            {'destinationService': destinationService})
            except NameError:
                pass

            resourceUri = ("/api/access/" + const.PROVIDER_INGRESS_DIRECTION +
                           "/" + interface + "/rules")
            asav_bulk_rule = dict(resourceUri=resourceUri,
                                  method="Post",
                                  data=asav_access_rule)
            asav_rules.append(asav_bulk_rule)

        return asav_rules

    def _get_deny_rule(self, interface):
        """ Prepares a DENY firewall rule for ASAv.

        :param interface: interface name

        Returns: A list of rules.

        """

        asa_rule = dict(
            destinationAddress=dict(kind="AnyIPAddress",
                                    value=const.REFRENCE_IPS['WILDCARD']),
            sourceAddress=dict(kind="AnyIPAddress",
                               value=const.REFRENCE_IPS['WILDCARD']),
            destinationService=dict(kind="NetworkProtocol", value='ip'),
            permit=False)
        resource_uri = ("/api/access/" + const.PROVIDER_INGRESS_DIRECTION +
                        "/" + interface + "/rules")
        asav_bulk_rule = dict(resourceUri=resource_uri,
                              method="Post",
                              data=asa_rule)
        return [asav_bulk_rule]

    def _get_firewall_mgmt_ip(self, firewall):
        """ Retrieves management IP from the firewall resource received

        :param firewall: firewall dictionary containing rules
        and other objects

        Returns: management IP

        """

        description = ast.literal_eval(firewall["description"])
        if not description.get('vm_management_ip'):
            msg = ("Failed to find vm_management_ip.")
            LOG.debug(msg)
            raise Exception(msg)

        if not description.get('service_vendor'):
            msg = ("Failed to find service_vendor.")
            LOG.debug(msg)
            raise Exception(msg)

        msg = ("Found vm_management_ip %s."
               % description['vm_management_ip'])
        LOG.debug(msg)
        return description['vm_management_ip']

    def create_firewall(self, context, firewall, host):
        """ Implements firewall creation

        Issues REST call to service VM for firewall creation

        :param context: Neutron context
        :param firewall: Firewall resource object from neutron fwaas plugin
        :param host: Name of the host machine

        Returns: SUCCESS/Failure message with reason.

        """

        mgmt_ip = self._get_firewall_mgmt_ip(firewall)
        url = "https://" + mgmt_ip + "/api"
        interface = self._get_interface_name(firewall)
        deny_rule = self._check_for_implicit_deny(firewall, interface)
        if deny_rule:
            rules_body = deny_rule
        else:
            rules_body = self.get_rules(firewall, interface)
        data = rules_body
        LOG.info(_("Initiating POST request to configure firewall - %r of "
                   "tenant : %r " % (firewall['id'], firewall['tenant_id'])))
        try:
            result = self.rest_api.post(url, data, self.auth)

            if result is not const.STATUS_SUCCESS:
                msg = ("Failed to configure ASAv Firewall. Reason: %r" %
                       result)
                LOG.error(msg)
            else:
                self.save_config(mgmt_ip, firewall['id'])
                msg = ("Configured ASAv Firewall.")
                LOG.info(msg)
            return result
        except Exception as err:
            msg = ("Failed to configure firewall. Error: %r" % err)
            LOG.error(msg)
            return msg

    def update_firewall(self, context, firewall, host):
        """ Implements firewall updation

        Issues REST call to service VM for firewall updation

        :param context: Neutron context
        :param firewall: Firewall resource object from neutron fwaas plugin
        :param host: Name of the host machine

        Returns: SUCCESS/Failure message with reason.

        """

        # REVISIT(VK) Blind update. But this has lot of dependency to fix.
        try:
            mgmt_ip = self._get_firewall_mgmt_ip(firewall)
            _is_delete_success = self.delete_firewall(mgmt_ip, firewall)
            _is_configure_success = self.configure_firewall(mgmt_ip,
                                                            firewall)
        except Exception as err:
            msg = ("Update firewall request failed. Error: %r." % err)
            LOG.error(msg)
            return msg

        if (_is_delete_success and _is_configure_success) is (
                                                        const.STATUS_SUCCESS):
            return const.STATUS_SUCCESS
        else:
            msg = ("Update firewall request failed. Reason: %r and %r" %
                   (_is_delete_success, _is_configure_success))
            LOG.error(msg)
            return msg

    def delete_firewall(self, context, firewall, host):
        """ Implements firewall deletion

        Issues REST call to service VM for firewall deletion

        :param context: Neutron context
        :param firewall: Firewall resource object from neutron fwaas plugin
        :param host: Name of the host machine

        Returns: SUCCESS/Failure message with reason.

        """

        mgmt_ip = self._get_firewall_mgmt_ip(firewall)
        url = "https://" + mgmt_ip + "/api/cli"
        interface_name = "{0}_access_{1}".format(
            self._get_interface_name(firewall),
            const.PROVIDER_INGRESS_DIRECTION)
        clear_interface_acl = "clear configure access-list %s" % interface_name
        data = dict(commands=[clear_interface_acl, 'wr mem'])
        LOG.info("Initiating DELETE request for firewall : %r. Tenant: %s "
                 "URL: %r" % (firewall['id'], firewall['tenant_id'],
                              url))
        try:
            result = self.rest_api.post(url, data, self.auth)

            if result is not const.STATUS_SUCCESS:
                msg = ("Failed to delete ASAv Firewall. Reason: %r" %
                       result)
                LOG.error(msg)
                if self._safe_to_flag_delete_success(str(result),
                                                     interface_name):
                    LOG.error("Firewall configuration not found for the "
                              "interface. Marking that as delete success, "
                              "for Firewall ID: %r Tenant ID: %r "
                              % (firewall['id'], firewall['tenant_id']))
                    return const.STATUS_SUCCESS
                else:
                    msg = ("Firewall deletion failed and the configuration "
                           "is found to exist in the firewall.")
                    LOG.error(msg)
                    return msg
            else:
                self.save_config(mgmt_ip, firewall['id'])
                msg = ("Deleted ASAv Firewall.")
                LOG.info(msg)
            return result
        except Exception as err:
            msg = ("Exception - %r " % str(err))
            LOG.error(msg)
            return msg

    def _get_interface_name(self, firewall):
        """ Gets the provider interface name.

        :param firewall: Firewall resource object of type dict.

        Returns: interface name

        """

        try:
            provider_cidr = ast.literal_eval(firewall["description"])[
                "provider_cidr"]
        except KeyError:
            LOG.error("Get interface name failed")
            raise
        return 'interface-' + provider_cidr.replace('/', '_')

    def save_config(self, ip, fw_id):
        """ Gets the provider interface name.

        :param ip: Management IP address of the Service VM
        :param fw_id: unique firewall id.

        Returns: SUCCESS/Error message

        """

        commands = list()
        try:
            result = self.configure_bulk_cli(ip, commands)

            if result is not const.STATUS_SUCCESS:
                msg = ("Error saving firewall configuration. "
                       "Reason: %r. Firewall ID: %s" % (fw_id, result))
                LOG.error(msg)
            else:
                msg = ("Configured ASAv Firewall. Firewall ID: %s" % fw_id)
                LOG.info(msg)
            return result
        except Exception as err:
            msg = ("Error saving firewall configuration. Error: %r. "
                   "Firewall ID: %s" % (fw_id, err))
            LOG.error(msg)
            return msg

    def _safe_to_flag_delete_success(self, resp, interface_name):
        """ Checks if the firewall is safe to be assumed deleted.

        :param resp: Response from delete firewall call.
        :param interface_name: Name of the provider interface.

        Returns: True/False

        """

        expected_strings = ['ERROR', 'access-list', interface_name,
                            'does not exist']

        if all(string in resp for string in expected_strings):
            return True
        else:
            return False

    def _check_for_implicit_deny(self, firewall, interface):
        """ Gets a list of deny rules for a particular interface.

        :param firewall: Firewall resource object of type dict.
        :param interface: Name of the provider interface.

        Returns: list of rules.

        """

        rules = firewall["firewall_rule_list"]
        if not rules:
            return self._get_deny_rule(interface)
        elif (not cfg.CONF.ASAV_CONFIG.scan_all_rule and
                rules[0]['description'].lower() == const.IMPLICIT_DENY):
            return self._get_deny_rule(interface)
        elif cfg.CONF.ASAV_CONFIG.scan_all_rule:
            for rule in rules:
                if rule['description'].lower() == const.IMPLICIT_DENY:
                    return self._get_deny_rule(interface)
        return []
