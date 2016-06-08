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
import ipaddr
import requests

from oslo_concurrency import lockutils
from oslo_config import cfg
from oslo_serialization import jsonutils

from requests.auth import HTTPBasicAuth

from socket import inet_ntoa
from struct import pack

from gbpservice.nfp.configurator.drivers.base import base_driver
from gbpservice.nfp.configurator.drivers.vpn.asav import (
    asav_vpn_constants as const)
from gbpservice.nfp.configurator.lib import constants as common_const
from gbpservice.nfp.configurator.lib import vpn_constants as vpn_const
from gbpservice.nfp.core import log as nfp_logging

from neutron_lib import exceptions

LOG = nfp_logging.getLogger(__name__)


class UnknownReasonException(exceptions.NeutronException):
    message = "Unsupported rpcreason '%(reason)s' from plugin "


class UnknownResourceException(exceptions.NeutronException):
    message = "Unsupported resource '%(resource)s' from plugin "


class ResourceErrorState(exceptions.NeutronException):
    message = "Resource '%(name)s' : '%(id)s' \
        went to error state, check log"

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
            msg = ("Initiating a POST call to URL: %r "
                   "with data: %r." % (url, data))
            LOG.info(msg)
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
        if resp.status_code not in common_const.SUCCESS_CODES:
            msg = ("Successfully issued a POST call. However, the result "
                   "of the POST API is negative. URL: %r. Response code: %s."
                   "Result: %r." % (url, resp.status_code, result))
            LOG.error(msg)
            return msg
        msg = ("Successfully issued a POST call and the result of "
               "the API operation is positive. URL: %r. Result: %r. "
               "Status Code: %r." % (url, result, resp.status_code))
        LOG.info(msg)
        return (
            common_const.STATUS_SUCCESS
            if not response_data_expected
            else dict(GET_RESPONSE=result))

    def get(self, url, auth_header):

        try:
            resp = requests.get(url, headers=self.content_header,
                                verify=False, auth=auth_header,
                                timeout=self.timeout)
        except requests.exceptions.SSLError as err:
            msg = ("REST API GET request failed for ASAv. "
                   "URL: %r,  Error: %r" % (
                       url, str(err).capitalize()))
            LOG.error(msg)
            return resp
        except Exception as err:
            msg = ("Failed to issue GET call "
                   "to service. URL: %r, Error: %r" %
                   (url, str(err).capitalize()))
            LOG.error(msg)
            return resp

        try:
            result = resp.json()
        except ValueError as err:
            msg = ("Unable to parse response, invalid JSON. URL: "
                   "%r. %r" % (url, str(err).capitalize()))
            LOG.error(msg)
            return resp
        if resp.status_code not in common_const.SUCCESS_CODES:
            msg = ("Successfully issued a GET call. However, the result "
                   "of the GET API is negative. URL: %r. Response code: %s."
                   "Result: %r." % (url, resp.status_code, result))
            LOG.error(msg)
            return resp
        msg = ("Successfully issued a GET call and the result of "
               "the API operation is positive. URL: %r. Result: %r. "
               "Status Code: %r." % (url, result, resp.status_code))
        LOG.info(msg)
        return resp


class VPNServiceValidator(object):
    def __init__(self, agent):
        self.agent = agent

    def _update_service_status(self, vpnsvc, status):
        """
        Driver will call this API to report
        status of VPN service.
        """
        msg = ("Driver informing status: %s."
               % status)
        LOG.debug(msg)
        vpnsvc_status = [{
            'id': vpnsvc['id'],
            'status': status,
            'updated_pending_status':True}]
        return vpnsvc_status

    def _error_state(self, context, vpnsvc):
        self.agent.update_status(
            context, self._update_service_status(vpnsvc,
                                                 vpn_const.STATE_ERROR))
        raise ResourceErrorState(name='vpn_service', id=vpnsvc['id'])

    def _active_state(self, context, vpnsvc):
        self.agent.update_status(
            context, self._update_service_status(vpnsvc,
                                                 vpn_const.STATE_ACTIVE))

    def _get_local_cidr(self, vpn_svc):
        svc_desc = vpn_svc['description']
        tokens = svc_desc.split(';')
        local_cidr = tokens[1].split('=')[1]
        return local_cidr

    def validate(self, context, vpnsvc):
        lcidr = self._get_local_cidr(vpnsvc)
        """
        Get the vpn services for this tenant
        Check for overlapping lcidr - not allowed
        """
        filters = {'tenant_id': [context['tenant_id']]}
        t_vpnsvcs = self.agent.get_vpn_services(
            context, filters=filters)
        t_vpnsvcs.remove(vpnsvc)
        for svc in t_vpnsvcs:
            t_lcidr = self._get_local_cidr(svc)
            if t_lcidr == lcidr:
                self._error_state(
                    context,
                    vpnsvc)

        self._active_state(context, vpnsvc)

""" vpn generic configuration driver for handling device
configuration requests.

"""


class VPNGenericConfigDriver(base_driver.BaseDriver):

    def __init__(self):
        pass

    def generic_configure_bulk_cli(self, mgmt_ip, commands,
                                   response_data_expected=False):
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
        url = const.REQUEST_URL % (mgmt_ip, resource_uri)

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
        result = self.generic_configure_bulk_cli(mgmt_ip, commands,
                                                 response_data_expected=True)

        if (type(result) is dict) and result.get('GET_RESPONSE'):
            data = ''.join(result['GET_RESPONSE']['response']).split(
                'GigabitEthernet0/')
            for item in data:
                if mac in item:
                    return item[0]
        msg = ("Failed to retrieve interface position. Response: %r." % result)
        raise Exception(msg)

    def _get_device_interface_name(self, cidr):
        """ Prepares the interface name.

        :param cidr: CIDR of the interface

        Returns: interface name.

        """

        return 'interface-' + cidr.replace('/', '_')

    def configure_interfaces(self, context, resource_data):
        """ Configures interfaces for the service VM.

        :param context: neutron context
        :param resource_data: a dictionary of vpn rules and objects
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
            msg = ("Failed to configure interfaces. Error: %r." % err)
            LOG.error(msg)
            raise Exception(msg)

        commands = list()
        try:
            provider_mask = str(ipaddr.IPv4Network(provider_cidr).netmask)
            stitching_mask = str(ipaddr.IPv4Network(stitching_cidr).netmask)

            provider_intf_name = self._get_device_interface_name(provider_cidr)
            stitching_intf_name = self._get_device_interface_name(
                stitching_cidr)

            security_level = self.conf.ASAV_CONFIG.security_level
            commands = self._get_interface_commands(
                provider_intf_name, str(provider_interface_position),
                provider_ip, provider_mask, security_level,
                mac_address=provider_macs)
            result = self.generic_configure_bulk_cli(mgmt_ip, commands)
            if result is not common_const.STATUS_SUCCESS:
                return result

            commands = self._get_interface_commands(
                stitching_intf_name, str(stitching_interface_position),
                stitching_ip, stitching_mask, security_level,
                mac_address=stitching_macs)
            result = self.generic_configure_bulk_cli(mgmt_ip, commands)
            if result is not common_const.STATUS_SUCCESS:
                msg = ("Failed to configure ASAv interfaces. Reason: %r" %
                       result)
                LOG.error(msg)
            else:
                msg = ("Configure ASAv interfaces.")
                LOG.info(msg)
            return result
        except Exception as err:
            msg = ("Exception while configuring interface. "
                   "Reason: %s" % err)
            LOG.error(msg)
            raise Exception(err)

    def clear_interfaces(self, context, resource_data):
        """ Clears interfaces of the service VM.

        :param context: neutron context
        :param resource_data: a dictionary of vpn rules and objects
        send by neutron plugin

        Returns: SUCCESS/Failure message with reason.

        """

        try:
            mgmt_ip = resource_data['mgmt_ip']
            provider_mac = resource_data['provider_mac']
            asav_provider_mac = self.get_asav_mac(provider_mac)

            provider_interface_position = self.get_interface_position(
                                                    mgmt_ip, asav_provider_mac)
            stitching_interface_position = str(int(
                                            provider_interface_position) + 1)

            commands = []
            provider_interface_id = self._get_asav_interface_id(
                                                provider_interface_position)
            stitching_interface_id = self._get_asav_interface_id(
                                                stitching_interface_position)
            commands.append("clear configure interface " +
                            provider_interface_id)
            commands.append("clear configure interface " +
                            stitching_interface_id)
            result = self.generic_configure_bulk_cli(mgmt_ip, commands)

            if result is not common_const.STATUS_SUCCESS:
                msg = ("Failed to clear ASAv interfaces. Reason: %r" %
                       result)
                LOG.error(msg)
            else:
                msg = ("Cleared ASAv interfaces.")
                LOG.info(msg)
            return result
        except Exception as err:
            msg = ("Exception while clearing interface config. "
                   "Reason: %s" % err)
            LOG.error(msg)
            raise Exception(err)

    def configure_routes(self, context, resource_data):
        """ Configure routes for the service VM.

        Issues REST call to service VM for configuration of routes.

        :param context: neutron context
        :param resource_data: a dictionary of vpn rules and objects
        send by neutron plugin

        Returns: SUCCESS/Failure message with reason.

        """

        return self.configure_pbr_route(context, resource_data)

    def clear_routes(self, context, resource_data):
        """ Clear routes for the service VM.

        Issues REST call to service VM for deletion of routes.

        :param context: neutron context
        :param resource_data: a dictionary of vpn rules and objects
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
        :param resource_data: a dictionary of vpn rules and objects
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

            result = self.generic_configure_bulk_cli(mgmt_ip, commands)
            if result is not common_const.STATUS_SUCCESS:
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
            result = self.generic_configure_bulk_cli(mgmt_ip, command)

            if result is not common_const.STATUS_SUCCESS:
                msg = ("Failed to configure ASAv routes. Reason: %r" %
                       result)
                LOG.error(msg)
            else:
                msg = ("Configure ASAv routes.")
                LOG.info(msg)
            return result

        except Exception as err:
            msg = ("Exception while configuring pbr route. "
                   "Reason: %s" % err)
            LOG.error(msg)
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
        :param resource_data: a dictionary of vpn rules and objects
        send by neutron plugin

        Returns: SUCCESS/Failure message with reason.

        """

        mgmt_ip = resource_data['mgmt_ip']
        source_cidr = resource_data['source_cidrs'][0]
        provider_mac = resource_data['provider_mac']
        try:
            asav_provider_mac = self.get_asav_mac(provider_mac)
            provider_interface_position = self.get_interface_position(
                                                    mgmt_ip, asav_provider_mac)

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

            self.generic_configure_bulk_cli(mgmt_ip, commands)
        except Exception as err:
            msg = ("Exception while deleting pbr route. "
                   "Reason: %s" % err)
            LOG.error(msg)
            return msg
        else:
            return common_const.STATUS_SUCCESS

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
            asav_mac += (l[i] + l[i + 1] + ".")

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
                asav_mac += (l[i] + l[i + 1] + ".")
            asav_mac_list.append(asav_mac[:-1])

        return tuple(asav_mac_list)


class VPNaasDriver(VPNGenericConfigDriver):
    """
    vpn as a service driver for handling vpn
    service configuration requests.

    We initialize service type and service vendor in this class because
    agent loads class object only for those driver classes that have service
    type and service vendor as class attributes. Also, only this driver
    class is exposed to the agent.

    """
    service_type = vpn_const.SERVICE_TYPE
    service_vendor = const.SERVICE_VENDOR
    # history
    #   1.0 Initial version
    RPC_API_VERSION = '1.0'

    def __init__(self, conf):
        self.conf = conf
        self.port = const.CONFIGURATION_SERVER_PORT
        self.register_config_options()
        self.timeout = const.REST_TIMEOUT
        self.rest_api = RestApi(self.timeout)
        self.handlers = {
            'vpn_service': {
                'create': self.create_vpn_service},
            'ipsec_site_connection': {
                'create': self.create_ipsec_conn,
                'update': self.update_ipsec_conn,
                'delete': self.delete_ipsec_conn}}
        self.auth = HTTPBasicAuth(self.conf.ASAV_CONFIG.mgmt_username,
                                  self.conf.ASAV_CONFIG.mgmt_userpass)
        super(VPNaasDriver, self).__init__()

    def register_config_options(self):
        """ Registers the config options.

        Returns: None

        """

        self.conf.register_opts(asav_auth_opts, 'ASAV_CONFIG')

    def vpnservice_updated(self, context, resource_data):
        """Handle VPNaaS service driver change notifications."""
        msg = "Handling VPN service update notification '%s'" % (
                                            resource_data.get('reason', ''))
        LOG.debug(msg)

        resource = resource_data.get('resource')
        tenant_id = resource['tenant_id']
        # Synchronize the update operation per tenant.
        # Resources under tenant have inter dependencies.

        @lockutils.synchronized(tenant_id)
        def _vpnservice_updated(context, resource_data):
            reason = resource_data.get('reason')
            rsrc = resource_data.get('rsrc_type')

            if rsrc not in self.handlers.keys():
                raise UnknownResourceException(resource=rsrc)
            if reason not in self.handlers[rsrc].keys():
                raise UnknownReasonException(reason=reason)

            self.handlers[rsrc][reason](context, resource_data)
        return _vpnservice_updated(context, resource_data)

    def _update_conn_status(self, conn, status):
        """
        Driver will call this API to report
        status of a connection - only if there is any change.
        :param conn: ipsec conn dicitonary
        :param status: status of the service.

        Returns: updated status dictionary
        """
        msg = ("Driver informing connection status "
               "changed to %s" % status)
        LOG.debug(msg)
        vpnsvc_status = [{
            'id': conn['vpnservice_id'],
            'status':'ACTIVE',
            'updated_pending_status':False,
            'ipsec_site_connections':{
                conn['id']: {
                    'status': status,
                    'updated_pending_status': True}}}]
        return vpnsvc_status

    def _error_state(self, context, conn):
        self.agent.update_status(
                context, self._update_conn_status(conn,
                                                  vpn_const.STATE_ERROR))
        raise ResourceErrorState(
            name='ipsec-site-conn',
            id=conn['id'])

    def _init_state(self, context, conn):
        self.agent.update_status(
                context, self._update_conn_status(conn,
                                                  vpn_const.STATE_INIT))

    def _get_fip_from_vpnsvc(self, vpn_svc):
        svc_desc = vpn_svc['description']
        tokens = svc_desc.split(';')
        fip = tokens[0].split('=')[1]
        return fip

    def _get_external_intf_name(self, vpn_svc):
        svc_desc = vpn_svc['description']
        tokens = svc_desc.split(';')
        stitching_cidr = tokens[5].split('=')[1]
        return "interface-" + stitching_cidr.replace('/', '_')

    def _get_fip(self, svc_context):
        return self._get_fip_from_vpnsvc(svc_context['service'])

    def _get_ipsec_tunnel_local_cidr_from_vpnsvc(self, vpn_svc):
        svc_desc = vpn_svc['description']
        tokens = svc_desc.split(';')
        tunnel_local_cidr = tokens[1].split('=')[1]
        return tunnel_local_cidr

    def _get_ipsec_tunnel_local_cidr(self, svc_context):
        # Provider PTG is local cidr for the tunnel
        # - which is passed in svc description as of now
        return self.\
            _get_ipsec_tunnel_local_cidr_from_vpnsvc(
                svc_context['service'])

    def _ipsec_get_tenant_conns(self, context, conn, on_delete=False):
        filters = {
            'tenant_id': [context['tenant_id']],
            # 'vpnservice_id': [conn['vpnservice_id']],
            'peer_address': [conn['peer_address']]}
        tenant_conns = self.agent.get_ipsec_conns(
            context, filters)
        if not tenant_conns:
            if not on_delete:
                # Something went wrong - atleast the current
                # connection should be there
                msg = "No tenant conns for filters (%s)" % (str(filters))
                LOG.error(msg)
                # Move conn into err state
                self._error_state(context, conn)

        if conn in tenant_conns:
            tenant_conns.remove(conn)
        if not tenant_conns:
            return tenant_conns

        conn_list = []
        # get fip from connn description
        mgmt_fip = self._get_fip_from_vpnsvc(conn)
        svc_ids = [conn['vpnservice_id'] for conn in tenant_conns]
        vpnservices = self.agent.get_vpn_services(context, ids=svc_ids)
        copy_svc = copy.deepcopy(vpnservices)
        # if service's fip matches new service's fip then both services
        # lie on same instance, in this case we should only create tunnel
        for vpn in copy_svc:
            if mgmt_fip in vpn['description']:
                continue
            else:
                vpnservices.remove(vpn)
        # we have all the vpnservices matching on this fip
        for vpn in vpnservices:
            matching_conn = [conn for conn in tenant_conns
                             if conn['vpnservice_id'] == vpn['id']]
            conn_list.extend(matching_conn)
        if not on_delete:
            # Remove the conns which are in pending_create
            # state. It might be possible that more than one
            # conns could get created in database before the rpc
            # method of dev driver is invoked.
            # We have to separate first conn creation from rest.
            copy_conns = copy.deepcopy(conn_list)
            for tconn in copy_conns:
                if tconn['status'] == vpn_const.STATE_PENDING:
                    conn_list.remove(tconn)

        return conn_list

    def _ipsec_check_overlapping_peer(self, context,
                                      tenant_conns, conn):
        pcidrs = conn['peer_cidrs']
        for t_conn in tenant_conns:
            t_pcidrs = t_conn['peer_cidrs']
            if conn['vpnservice_id'] != t_conn['vpnservice_id']:
                continue

            for pcidr in pcidrs:
                if pcidr in t_pcidrs:
                    msg = "Overlapping peer cidr (%s)" % (pcidr)
                    LOG.error(msg)
                    self._error_state(
                        context, conn)

    def create_vpn_service(self, context, resource_data):
        svc = resource_data.get('resource')
        validator = VPNServiceValidator(self.agent)
        validator.validate(context, svc)

    def create_ipsec_conn(self, context, resource_data):
        conn = resource_data.get('resource')
        """
        Following conditions -
        0) Conn with more than one peer_address
        is not allowed. This is because vyos has
        conns and tunnels inside conn. But openstack
        doesnt have tunnels. So conn will itslef need
        to be mapped to tunnel.
        a) Already conns exist for this tenant
            . In this case just add a tunnel
                . For same peer
                . Add peer for different peer
        b) First conn, create complete ipsec profile
        """
        if len(conn['peer_cidrs']) < 1:
            msg = "Invalid #of peer_cidrs can not be less than one"
            LOG.error(msg)
            self._error_state(context, conn)

        tenant_conns = self._ipsec_get_tenant_conns(
            context, conn)
        try:
            if not tenant_conns:
                self._ipsec_create_conn(context, conn)
            else:
                self._ipsec_create_conn(context, conn, same_peer=True)
        except Exception as ex:
            msg = "Configuring ipsec site conn failed Reason: %s" % ex
            LOG.error(msg)
            self._error_state(context, conn)

    def delete_ipsec_conn(self, context, resource_data):
        conn = resource_data.get('resource')
        tenant_conns = self._ipsec_get_tenant_conns(
            context, conn, on_delete=True)
        if tenant_conns:
            self._ipsec_delete_connection(
                context, conn, same_peer=True)
        else:
            self._ipsec_delete_connection(
                context, conn)

    def update_ipsec_conn(self, context, resource_data):
        # Talk to service manager and get floating ip
        # (with tenant_id & svc_type as criteria)
        # Might have to send some commands to
        # update ipsec_conn params
        # Can IPSEC policy params / IKE policy params
        # be changed with connection intact ?
        # Need to figure out which all params can be
        # changed based on what vyos vm will support
        # Maintain this resource ? will be useful in case of update ?
        pass

    def _ipsec_create_tunnel(self, context, conn):
        svc_context = self.agent.get_vpn_servicecontext(
            context, self._get_filters(conn_id=conn['id']))[0]

        fip = self._get_fip(svc_context)
        tunnel_local_cidr = self.\
            _get_ipsec_tunnel_local_cidr(svc_context)

        siteconn = svc_context['siteconns'][0]['connection']
        access_list = []
        for peer_cidr in siteconn['peer_cidrs']:
            rules = self._configure_access_list(fip, tunnel_local_cidr,
                                                peer_cidr, conn['id'])
            access_list.extend(rules)
        self._configure_bulk_cli(fip, access_list)
        self._init_state(context, conn)

    def _ipsec_delete_tunnel(self, context,
                             vpnsvc, conn):
        fip = self._get_fip_from_vpnsvc(vpnsvc)
        tunnel_local_cidr = self._get_ipsec_tunnel_local_cidr_from_vpnsvc(
                                                                    vpnsvc)
        access_list = []
        for peer_cidr in conn['peer_cidrs']:
            rules = self._configure_access_list(fip, tunnel_local_cidr,
                                                peer_cidr, conn['id'],
                                                delete=True)
            access_list.extend(rules)
        self._configure_bulk_cli(fip, access_list)

    def _ipsec_delete_connection(self, context,
                                 conn, same_peer=False):

        commands = []
        fip = self._get_fip_from_vpnsvc(conn)
        tfset_name = conn['ikepolicy_id']
        self.external_intf_name = self._get_external_intf_name(conn)
        ipsecpolicy = {'id': conn['ipsecpolicy_id']}
        siteconn = {'peer_address': conn['peer_address']}
        tunnel_local_cidr = self._get_ipsec_tunnel_local_cidr_from_vpnsvc(conn)
        access_list = []
        for peer_cidr in conn['peer_cidrs']:
            rules = self._configure_access_list(fip, tunnel_local_cidr,
                                                peer_cidr, conn['id'],
                                                delete=True)
            access_list.extend(rules)
        ipsec = self._configure_ipsec(
            fip, tfset_name, ipsecpolicy, conn, delete=True)
        commands.extend(ipsec)
        if not same_peer:
            tunnelgroup = self._configure_tunnel_group(fip, siteconn,
                                                       delete=True)
            commands.extend(tunnelgroup)
        commands.extend(access_list)
        '''commands.append("clear conf crypto ipsec ikev1 transform-set %s" %
                            tfset_name)
        commands.append("sysopt connection permit-vpn")
        commands.append("no crypto ikev1 enable %s" % self.external_intf_name)
        commands.append("no sysopt connection permit-vpn")'''
        try:
            self._configure_bulk_cli(fip, commands)
        except Exception as e:
            msg = "Delete ipsec conn failed. Reason: %s" % e
            LOG.warn(msg)

    def check_status(self, context, svc_context):
        pass

    def _get_filters(self, tenant_id=None, vpnservice_id=None, conn_id=None,
                     peer_address=None):
        filters = {}
        if tenant_id:
            filters['tenant_id'] = tenant_id
        if vpnservice_id:
            filters['vpnservice_id'] = vpnservice_id
        if conn_id:
            filters['siteconn_id'] = conn_id
        if peer_address:
            filters['peer_address'] = peer_address
        return filters

    def _ipsec_create_conn(self, context, conn, same_peer=False):
        svc_context = self.agent.get_vpn_servicecontext(
            context, self._get_filters(conn_id=conn['id']))[0]

        fip = self._get_fip(svc_context)
        tunnel_local_cidr = self.\
            _get_ipsec_tunnel_local_cidr(svc_context)
        ikepolicy = svc_context['siteconns'][0]['ikepolicy']
        ipsecpolicy = svc_context['siteconns'][0]['ipsecpolicy']
        siteconn = svc_context['siteconns'][0]['connection']
        self.external_intf_name = self._get_external_intf_name(
                                                        svc_context['service'])
        # TODO(kedar) shall this be in try-except?
        ikepolicy_rest = self._configure_ikeconfig(fip, ikepolicy)
        access_list = []
        for peer_cidr in siteconn['peer_cidrs']:
            rules = self._configure_access_list(fip, tunnel_local_cidr,
                                                peer_cidr, conn['id'])
            access_list.extend(rules)

        ipsec = self._configure_ipsec(
            fip, ikepolicy['id'], ipsecpolicy, siteconn=siteconn)
        # execute rest apis
        commands = []
        # commands.append("route %s %s 255.255.255.255 %s 1"
        # %(self.external_intf_name,
        #                    siteconn['peer_address'], stitching_gw))
        commands.append("sysopt connection permit-vpn")
        commands.extend(ikepolicy_rest)
        commands.append("no sysopt connection permit-vpn")
        commands.extend(access_list)
        if not same_peer:
            tunnelgroup = self._configure_tunnel_group(fip, siteconn)
            commands.extend(tunnelgroup)
        commands.extend(ipsec)
        try:
            self._configure_bulk_cli(fip, commands)
            self._init_state(context, conn)
        except Exception as ex:
            rollback = []
            access_list = []
            msg = "Configuring ipsec failed, rolling back.: %s" % ex
            LOG.error(msg)
            try:
                for peer_cidr in siteconn['peer_cidrs']:
                    rules = self._configure_access_list(fip, tunnel_local_cidr,
                                                        peer_cidr, conn['id'],
                                                        delete=True)
                    access_list.extend(rules)
                ikepolicy_rest = self._configure_ikeconfig(fip,
                                                           ikepolicy,
                                                           delete=True)
                tunnelgroup = self._configure_tunnel_group(fip,
                                                           siteconn,
                                                           delete=True)
                ipsec = self._configure_ipsec(
                    fip, ikepolicy['id'], ipsecpolicy, siteconn, delete=True)
                rollback.extend(ipsec)
                rollback.extend(tunnelgroup)
                rollback.extend(access_list)
                # rollback.append("clear conf crypto ipsec ikev1
                # transform-set %s" % ikepolicy['id'])
                # rollback.append("sysopt connection permit-vpn")
                # rollback.append("no crypto ikev1 enable %s" %
                # self.external_intf_name)
                # rollback.append("no sysopt connection permit-vpn")
                self._configure_bulk_cli(fip, rollback)
            except Exception as ex:
                msg = "Rollback ipsec failed. Reason: %s" % ex
                LOG.warn(msg)
            self._error_state(context, conn)

    def _get_ike_policies(self, mgmt_ip):
        uri = "/api/vpn/ikev1policy"
        url = const.REQUEST_URL % (mgmt_ip, uri)
        resp = self.rest_api.get(url, self.auth)
        return resp.json()

    def _correct_encryption_algo(self, algo):
        algos = {
            'aes-128': "esp-aes",
            'aes-256': "esp-aes-256",
            'aes-192': "esp-aes-192",
            '3des': "esp-3des",
            'des': "esp-des"}
        return algos[algo]

    def _correct_auth_algo(self, algo):
        algos = {'sha1': 'esp-sha-hmac',
                 'md5': 'esp-md5-hmac'}
        return algos[algo]

    def _configure_ikeconfig(self, fip, ikepolicy_req, delete=False):
        dhgroup = {'group2': 'group 2',
                   'group5': 'group 5',
                   'group14': 'group 14'}
        resp = self._get_ike_policies(fip)
        commands = []
        policies = None
        used_seq = []
        if resp.get('items'):
            policies = resp['items']
            used_seq = [policy['priority'] for policy in policies]
        if not used_seq:
            seq_no = 1
        else:
            for i in xrange(1, max(used_seq) + 2):
                if i not in used_seq:
                    seq_no = i
                    break

        commands.append("crypto ikev1 policy %s" % str(seq_no))
        commands.append("authentication pre-share")
        if ikepolicy_req['encryption_algorithm'] == 'aes-128':
            asav_encryption_algorithm = 'aes'
        else:
            asav_encryption_algorithm = ikepolicy_req['encryption_algorithm']
        commands.append("encryption %s" % asav_encryption_algorithm)
        auth_algorithm = None
        if ikepolicy_req['auth_algorithm'] == 'sha1':
            auth_algorithm = 'sha'
        else:
            auth_algorithm = ikepolicy_req['auth_algorithm']
        commands.append("hash %s" % auth_algorithm)
        commands.append(dhgroup[ikepolicy_req['pfs']])
        if not delete:
            commands.append("crypto ikev1 enable %s" % self.external_intf_name)
            encrypt_algo = self._correct_encryption_algo(
                                    ikepolicy_req['encryption_algorithm'])
            auth_algo = self._correct_auth_algo(
                                    ikepolicy_req['auth_algorithm'])
            commands.append("crypto ipsec ikev1 transform-set %s %s %s" % (
                ikepolicy_req['id'], encrypt_algo, auth_algo))
        if delete:
            commands = ["no " + command for command in commands]
        return commands

    def _calculate_netmask(self, mask):
            bits = 0xffffffff ^ (1 << 32 - int(mask)) - 1
            return inet_ntoa(pack('>I', bits))

    def _configure_access_list(self, fip, local_cidr, peer_cidr, conn_id,
                               delete=False):
        access_list = []
        name = conn_id.split('-')[0] + "-" + local_cidr.replace('/', '_')
        try:
            local = local_cidr.split('/')
            peer = peer_cidr.split('/')
            net_rule = (local[0] + ' ' + self._calculate_netmask(local[1]) +
                        ' ' + peer[0] + ' ' + self._calculate_netmask(peer[1]))
            for protocol in ["ip"]:
                rule = ("access-list %s extended permit %s %s"
                        % (name, protocol, net_rule))
                if delete:
                    rule = "no " + rule
                access_list.append(rule)
        except Exception as e:
            msg = "Can not configure access list. Reason:%s" % e
            LOG.error(msg)
            raise e
        return access_list

    def _configure_ipsec(self, fip, tfset_name,
                         ipsecpolicy=None, siteconn=None,
                         delete=False):
        name = ipsecpolicy['id']
        commands = []
        if delete:
            seq = self.get_delete_seqno(fip, siteconn['peer_address'])
            # seq = 1
            if seq:
                command = ["clear config crypto map %s %s" % (name, seq)]
                commands.extend(command)
            return commands

        access_list = (siteconn['id'].split('-')[0] + "-" +
                       self._get_ipsec_tunnel_local_cidr_from_vpnsvc(
                          siteconn).replace('/', '_'))
        sequence = self._get_unique_sequenceno(fip)
        prefix = "crypto map %s %s " % (name, sequence)
        commands.append(prefix + "match address %s" % access_list)
        commands.append(prefix + "set peer " + siteconn['peer_address'])
        commands.append(prefix + "set pfs " + ipsecpolicy['pfs'])
        commands.append((prefix +
                        "set security-association lifetime seconds " +
                         str(ipsecpolicy['lifetime']['value'])))
        commands.append(prefix + "set ikev1 transform-set " + tfset_name)
        commands.append("crypto map %s interface %s" % (
                                                name,
                                                self.external_intf_name))
        return commands

    def _configure_tunnel_group(self, fip, ipsec_conn, delete=False):
        commands = []
        if delete:
            commands = ["clear conf tunnel-group %s" % (
                        ipsec_conn['peer_address'])]
            return commands
        commands.append("tunnel-group %s type ipsec-l2l" % (
                        ipsec_conn['peer_address']))
        commands.append("tunnel-group %s ipsec-attributes" % (
                        ipsec_conn['peer_address']))
        commands.append("ikev1 pre-shared-key %s" % ipsec_conn['psk'])
        return commands

    def _configure_bulk_cli(self, mgmt_ip, commands):
        resource_uri = "/api/cli"
        url = const.REQUEST_URL % (mgmt_ip, resource_uri)
        commands.append("write memory")
        data = {"commands": commands}
        msg = "sending commands = %s" % commands
        LOG.debug(msg)
        self.rest_api.post(url, data, self.auth)

    def _get_unique_sequenceno(self, mgmt_ip):
        uri = "/api/vpn/cryptomaps/%s/entries" % self.external_intf_name
        url = const.REQUEST_URL % (mgmt_ip, uri)
        resp = self.rest_api.get(url, self.auth)
        if resp.status_code == 404:
            resp = {}
        used_seq = []
        resp = resp.json()
        if resp.get('items'):
            used_seq = [item['sequence'] for item in resp['items']]
        if not used_seq:
            return 1
        for i in xrange(1, max(used_seq) + 2):
            if i not in used_seq:
                return i

    def get_delete_seqno(self, mgmt_ip, peer, peer_cidr=None):
        uri = "/api/vpn/cryptomaps/%s/entries" % self.external_intf_name
        url = const.REQUEST_URL % (mgmt_ip, uri)
        resp = self.rest_api.get(url, self.auth)
        if resp.status_code == 404 or not resp:
            return 1
        resp = resp.json()
        if resp.get('items'):
            for item in resp.get('items'):
                # if (peer in item['peer'] and
                #     item['matchingTrafficSelector']['objectId'] == (
                #                             (peer_cidr.replace('/', '_')):
                if peer in item['peer']:
                    return item['sequence']
