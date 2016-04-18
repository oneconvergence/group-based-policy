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
import requests

from gbpservice.nfp.configurator.drivers.base import base_driver
from gbpservice.nfp.configurator.lib import vpn_constants as const

from oslo_concurrency import lockutils
from oslo_config import cfg
from oslo_log import log as logging
from oslo_serialization import jsonutils


LOG = logging.getLogger(__name__)

rest_timeout = [
    cfg.IntOpt(
        'VPN.rest_timeout',
        default=30,
        help="rest api timeout")]

cfg.CONF.register_opts(rest_timeout)


class UnknownReasonException(Exception):
    message = "Unsupported rpcreason '%(reason)s' from plugin "


class UnknownResourceException(Exception):
    message = "Unsupported resource '%(resource)s' from plugin "


class InvalidRsrcType(Exception):
    message = "Unsupported rsrctype '%(rsrc_type)s' from agent"


class ResourceErrorState(Exception):
    message = "Resource '%(name)s' : '%(id)s' \
        went to error state, %(message)"


"""
Provides different methods to make ReST calls to the service VM,
to update the configurations
"""


class RestApi(object):

    def __init__(self, vm_mgmt_ip):
        self.vm_mgmt_ip = vm_mgmt_ip
        self.timeout = cfg.CONF.rest_timeout

    def _dict_to_query_str(self, args):
        return '&'.join([str(k) + '=' + str(v) for k, v in args.iteritems()])

    def post(self, api, args):
        """
        Makes ReST call to the service VM to post the configurations.

        :param api: method that need to called inside the service VM to
        update the configurations.
        :prarm args: data that is need to be configured in service VM

        Returns: None
        """
        url = const.request_url % (
            self.vm_mgmt_ip,
            const.CONFIGURATION_SERVER_PORT, api)
        data = jsonutils.dumps(args)

        try:
            resp = requests.post(url, data=data, timeout=self.timeout)
            message = jsonutils.loads(resp.text)
            msg = "POST url %s %d" % (url, resp.status_code)
            LOG.info(msg)
            if resp.status_code == 200 and message.get("status", False):
                msg = "POST Rest API %s - Success" % (url)
                LOG.info(msg)
            else:
                msg = ("POST Rest API %s - Failed with status %s, %s"
                       % (url, resp.status_code,
                          message.get("reason", None)))
                LOG.error(msg)
                raise requests.exceptions.HTTPError(msg)
        except Exception as err:
            msg = ("Post Rest API %s - Failed. Reason: %s"
                   % (url, str(err).capitalize()))
            LOG.error(msg)
            raise requests.exceptions.HTTPError(msg)

    def put(self, api, args):
        """
        Makes ReST call to the service VM to put the configurations.

        :param api: method that need to called inside the service VM to
        update the configurations.
        :prarm args: data that is need to be configured in service VM

        Returns: None
        """
        url = const.request_url % (
            self.vm_mgmt_ip,
            const.CONFIGURATION_SERVER_PORT, api)
        data = jsonutils.dumps(args)

        try:
            resp = requests.put(url, data=data, timeout=self.timeout)
            msg = "PUT url %s %d" % (url, resp.status_code)
            LOG.debug(msg)
            if resp.status_code == 200:
                msg = "REST API PUT %s succeeded." % url
                LOG.debug(msg)
            else:
                msg = ("REST API PUT %s failed with status: %d."
                       % (url, resp.status_code))
                LOG.error(msg)
        except Exception as err:
            msg = ("REST API for PUT %s failed. %s"
                   % (url, str(err).capitalize()))
            LOG.error(msg)

    def delete(self, api, args, data=None):
        """
        Makes ReST call to the service VM to delete the configurations.

        :param api: method that need to called inside the service VM to
        update the configurations.
        :param args: fixed ip of the service VM to make frame the query string.
        :data args: data that is need to be configured in service VM

        Returns: None
        """
        url = const.request_url % (
            self.vm_mgmt_ip,
            const.CONFIGURATION_SERVER_PORT, api)

        if args:
            url += '?' + self._dict_to_query_str(args)

        if data:
            data = jsonutils.dumps(data)
        try:
            resp = requests.delete(url, timeout=self.timeout, data=data)
            message = jsonutils.loads(resp.text)
            msg = "DELETE url %s %d" % (url, resp.status_code)
            LOG.debug(msg)
            if resp.status_code == 200 and message.get("status", False):
                msg = "DELETE Rest API %s - Success" % (url)
                LOG.info(msg)
            else:
                msg = ("DELETE Rest API %s - Failed %s"
                       % (url, message.get("reason", None)))
                LOG.error(msg)
                raise requests.exceptions.HTTPError(msg)
        except Exception as err:
            msg = ("Delete Rest API %s - Failed. Reason: %s"
                   % (url, str(err).capitalize()))
            LOG.error(msg)
            raise requests.exceptions.HTTPError(msg)

    def get(self, api, args):
        """
        Makes ReST call to the service VM to put the configurations.

        :param api: method that need to called inside the service VM to
        update the configurations.
        :prarm args: data that is need to be configured in service VM

        Returns: None
        """
        output = ''

        url = const.request_url % (
            self.vm_mgmt_ip,
            const.CONFIGURATION_SERVER_PORT, api)

        try:
            resp = requests.get(url, params=args, timeout=self.timeout)
            msg = "GET url %s %d" % (url, resp.status_code)
            LOG.debug(msg)
            if resp.status_code == 200:
                msg = "REST API GET %s succeeded." % url
                LOG.debug(msg)
                json_resp = resp.json()
                return json_resp
            else:
                msg = ("REST API GET %s failed with status: %d."
                       % (url, resp.status_code))
                LOG.error(msg)
        except requests.exceptions.Timeout as err:
            msg = ("REST API GET %s timed out. %s."
                   % (url, str(err).capitalize()))
            LOG.error(msg)
        except Exception as err:
            msg = ("REST API for GET %s failed. %s"
                   % (url, str(err).capitalize()))
            LOG.error(msg)

        return output

"""
Provides the methods to validate the vpn service which is about to
be created in order to avoid any conflicts if they exists.
"""


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

    def _error_state(self, context, vpnsvc, message=''):
        """
        Enqueues the status of the service to ERROR.

        :param context: Dictionary which holds all the required data for
        for vpn service.
        :param vpnsvc: vpn service dictionary.
        :param message: the cause for the error.

        Returns: None
        """
        self.agent.update_status(
            context, self._update_service_status(vpnsvc, const.STATE_ERROR))
        raise ResourceErrorState(name='vpn_service', id=vpnsvc['id'],
                                 message=message)

    def _active_state(self, context, vpnsvc):
        """
        Enqueues the status of the service to ACTIVE.

        :param context: Dictionary which holds all the required data for
        for vpn service.
        :param vpnsvc: vpn service dictionary.

        Returns: None
        """
        self.agent.update_status(
            context, self._update_service_status(vpnsvc, const.STATE_ACTIVE))

    def _get_local_cidr(self, vpn_svc):
        svc_desc = vpn_svc['description']
        tokens = svc_desc.split(';')
        local_cidr = tokens[1].split('=')[1]
        return local_cidr

    def validate(self, context, vpnsvc):
        """
        Get the vpn services for this tenant
        Check for overlapping lcidr - (not allowed)

        :param context: Dictionary which holds all the required data for
        for vpn service.
        :param vpnsvc: vpn service dictionary.

        Returns: None
        """
        lcidr = self._get_local_cidr(vpnsvc)
        filters = {'tenant_id': [context['tenant_id']]}
        t_vpnsvcs = self.agent.get_vpn_services(
            context, filters=filters)
        vpnsvc.pop("status", None)

        for svc in t_vpnsvcs:
            del svc['status']
        if vpnsvc in t_vpnsvcs:
            t_vpnsvcs.remove(vpnsvc)
        for svc in t_vpnsvcs:
            t_lcidr = self._get_local_cidr(svc)
            if t_lcidr == lcidr:
                msg = ("Local cidr %s conflicts with existing vpnservice %s"
                       % (lcidr, svc['id']))
                LOG.error(msg)
                self._error_state(
                    context,
                    vpnsvc, msg)
        self._active_state(context, vpnsvc)

"""
VPN generic config driver for handling device configurations requests
"""


class VpnGenericConfigDriver(object):
    """
    Driver class for implementing VPN configuration
    requests from Orchestrator.
    """

    def __init__(self):
        self.timeout = cfg.CONF.rest_timeout

    def configure_routes(self, context, kwargs):
        """
        Configure routes for the service VM.

        Makes a ReST call to the service VM to configure the routes
        :param context: context dictionary of vpn service type
        :param kwargs: dicionary of a specific operation type, which was sent
        from neutron plugin

        Returns: None
        """

        url = const.request_url % (kwargs['vm_mgmt_ip'],
                                   const.CONFIGURATION_SERVER_PORT,
                                   'add-source-route')
        stitching_url = const.request_url % (kwargs['vm_mgmt_ip'],
                                   const.CONFIGURATION_SERVER_PORT,
                                   'add-stitching-route')
        st_data = jsonutils.dumps({'gateway_ip': kwargs['gateway_ip']})
        try:
            resp = requests.post(stitching_url, data=st_data, timeout=self.timeout)
        except requests.exceptions.ConnectionError as err:
            msg = ("Failed to establish connection to service at: "
                   "%r. ERROR: %r" % (kwargs['vm_mgmt_ip'],
                                      str(err).capitalize()))
        active_configured = False
        route_info = []
        for source_cidr in kwargs['source_cidrs']:
            route_info.append({'source_cidr': source_cidr,
                               'gateway_ip': kwargs['gateway_ip']})
        data = jsonutils.dumps(route_info)
        msg = ("Initiating POST request to configure route of "
               "primary service at: %r" % kwargs['vm_mgmt_ip'])
        LOG.info(msg)
        try:
            resp = requests.post(url, data=data, timeout=self.timeout)
        except requests.exceptions.ConnectionError as err:
            msg = ("Failed to establish connection to service at: "
                   "%r. ERROR: %r" % (kwargs['vm_mgmt_ip'],
                                      str(err).capitalize()))
            LOG.error(msg)
            raise Exception(err)
        except requests.exceptions.RequestException as err:
            msg = ("Unexpected ERROR happened  while configuring "
                   "route of service at: %r ERROR: %r" % (
                                                    kwargs['vm_mgmt_ip'],
                                                    str(err).capitalize()))
            LOG.error(msg)
            raise Exception(err)

        if resp.status_code in const.SUCCESS_CODES:
            message = jsonutils.loads(resp.text)
            if message.get("status", False):
                msg = ("Route configured successfully for VYOS"
                       " service at: %r" % kwargs['vm_mgmt_ip'])
                LOG.info(msg)
                active_configured = True
            else:
                msg = ("Configure source route failed on service with"
                       " status %s %s"
                       % (resp.status_code, message.get("reason", None)))
                LOG.error(msg)
                raise Exception(msg)

        msg = ("Route configuration status : %r "
               % (active_configured))
        LOG.info(msg)
        if active_configured:
            return "SUCCESS"

    def clear_routes(self, context, kwargs):
        """
        Clear routes for the service VM.

        Makes a ReST call to the service VM to clear the routes
        :param context: context dictionary of vpn service type
        :param kwargs: dicionary of a specific operation type, which was sent
        from neutron plugin

        Returns: None
        """
        active_configured = False

        stitching_url = const.request_url % (kwargs['vm_mgmt_ip'],
                                   const.CONFIGURATION_SERVER_PORT,
                                   'delete-stitching-route')
        st_data = jsonutils.dumps({'gateway_ip': kwargs['gateway_ip']})
        try:
            resp = requests.post(stitching_url, data=st_data, timeout=self.timeout)
        except requests.exceptions.ConnectionError as err:
            msg = ("Failed to establish connection to service at: "
                   "%r. ERROR: %r" % (kwargs['vm_mgmt_ip'],
                                      str(err).capitalize()))


        url = const.request_url % (kwargs['vm_mgmt_ip'],
                                   const.CONFIGURATION_SERVER_PORT,
                                   'delete-source-route')
        route_info = []
        for source_cidr in kwargs['source_cidrs']:
            route_info.append({'source_cidr': source_cidr})
        data = jsonutils.dumps(route_info)
        msg = ("Initiating DELETE route request to primary service at: %r"
               % kwargs['vm_mgmt_ip'])
        LOG.info(msg)
        try:
            resp = requests.delete(url, data=data, timeout=self.timeout)

        except requests.exceptions.ConnectionError as err:
            msg = ("Failed to establish connection to primary service at: "
                   " %r. ERROR: %r" % (kwargs['vm_mgmt_ip'], err))
            LOG.error(msg)
            raise Exception(err)
        except requests.exceptions.RequestException as err:
            msg = ("Unexpected ERROR happened  while deleting "
                   " route of service at: %r ERROR: %r"
                   % (kwargs['vm_mgmt_ip'], err))
            LOG.error(msg)
            raise Exception(err)

        if resp.status_code in const.SUCCESS_CODES:
            active_configured = True

        msg = ("Route deletion status : %r "
               % (active_configured))
        LOG.info(msg)
        if active_configured:
            return "SUCCESS"

    def _configure_static_ips(self, kwargs):
        """ Configure static IPs for provider and stitching interfaces
        of service VM.

        Issues REST call to service VM for configuration of static IPs.

        :param kwargs: a dictionary of vpn rules and objects
        send by neutron plugin

        Returns: SUCCESS/Failure message with reason.

        """

        rule_info = kwargs.get('rule_info')
        static_ips_info = dict(
                    provider_ip=kwargs.get('provider_ip'),
                    provider_cidr=kwargs.get('provider_cidr'),
                    provider_mac=kwargs.get('provider_mac'),
                    stitching_ip=kwargs.get('stitching_ip'),
                    stitching_cidr=kwargs.get('stitching_cidr'),
                    stitching_mac=kwargs.get('stitching_mac'),
                    provider_interface_position=kwargs.get(
                                            'provider_interface_position'),
                    stitching_interface_position=kwargs.get(
                                            'stitching_interface_position'))
        active_fip = rule_info['active_fip']
        LOG.error(static_ips_info)

        url = const.request_url % (active_fip,
                                   const.CONFIGURATION_SERVER_PORT,
                                   'add_static_ip')
        data = jsonutils.dumps(static_ips_info)
        LOG.error(data)

        msg = ("Initiating POST request to add static IPs for primary "
               "service with SERVICE ID: %r of tenant: %r at: %r" %
               (rule_info['service_id'], rule_info['tenant_id'],
                active_fip))
        LOG.info(msg)
        try:
            resp = requests.post(url, data, timeout=self.timeout)
        except requests.exceptions.ConnectionError as err:
            msg = ("Failed to establish connection to primary service at: "
                   "%r of SERVICE ID: %r of tenant: %r . ERROR: %r" %
                   (active_fip, rule_info['service_id'],
                    rule_info['tenant_id'], str(err).capitalize()))
            LOG.error(msg)
            return msg
        except requests.exceptions.RequestException as err:
            msg = ("Unexpected ERROR happened  while adding "
                   "static IPs for primary service at: %r "
                   "of SERVICE ID: %r of tenant: %r . ERROR: %r" %
                   (active_fip, rule_info['service_id'],
                    rule_info['tenant_id'], str(err).capitalize()))
            LOG.error(msg)
            return msg

        try:
            result = resp.json()
        except ValueError as err:
            msg = ("Unable to parse response, invalid JSON. URL: "
                   "%r. %r" % (url, str(err).capitalize()))
            LOG.error(msg)
            return msg
        if not result['status']:
            msg = ("Error adding static IPs. URL: %r. Reason: %s." %
                   (url, result['reason']))
            LOG.error(msg)
            return msg

        msg = ("Static IPs successfully added for SERVICE ID: %r"
               " of tenant: %r" % (rule_info['service_id'],
                                   rule_info['tenant_id']))
        LOG.info(msg)
        return const.STATUS_SUCCESS

    def configure_interfaces(self, context, kwargs):
        """
        Configure interfaces for the service VM.

        Makes a ReST call to the service VM to configure the interfaces
        :param context: context dictionary of vpn service type
        :param kwargs: dicionary of a specific operation type, which was sent
        from neutron plugin

        Returns: None
        """

        active_configured = False
        try:
            result_static_ips = self._configure_static_ips(kwargs)
        except Exception as err:
            msg = ("Failed to add static IPs. Error: %s" % err)
            LOG.error(msg)
            return msg
        else:
            if result_static_ips != const.STATUS_SUCCESS:
                return result_static_ips
            else:
                msg = ("Added static IPs. Result: %s" % result_static_ips)
                LOG.info(msg)

        rule_info = kwargs['rule_info']

        active_rule_info = dict(
            provider_mac=rule_info['active_provider_mac'],
            stitching_mac=rule_info['active_stitching_mac'])

        active_fip = rule_info['active_fip']

        url = const.request_url % (active_fip,
                                   const.CONFIGURATION_SERVER_PORT, 'add_rule')
        data = jsonutils.dumps(active_rule_info)
        msg = ("Initiating POST request to add persistent rule to primary "
               "service with SERVICE ID: %r of tenant: %r at: %r" % (
                    rule_info['service_id'], rule_info['tenant_id'],
                    active_fip))
        LOG.info(msg)
        try:
            resp = requests.post(url, data, timeout=self.timeout)
        except requests.exceptions.ConnectionError as err:
            msg = ("Failed to establish connection to primary service at: "
                   "%r of SERVICE ID: %r of tenant: %r . ERROR: %r" % (
                                                    active_fip,
                                                    rule_info['service_id'],
                                                    rule_info['tenant_id'],
                                                    str(err).capitalize()))
            LOG.error(msg)
            raise Exception(err)
        except requests.exceptions.RequestException as err:
            msg = ("Unexpected ERROR happened  while adding "
                   "persistent rule of primary service at: %r "
                   "of SERVICE ID: %r of tenant: %r . ERROR: %r" % (
                                                    active_fip,
                                                    rule_info['service_id'],
                                                    rule_info['tenant_id'],
                                                    str(err).capitalize()))
            LOG.error(msg)
            raise Exception(err)

        try:
            result = resp.json()
        except ValueError as err:
            msg = ("Unable to parse response, invalid JSON. URL: "
                   "%r" % (url, str(err).capitalize()))
            LOG.error(msg)
            raise Exception(msg)
        if not result['status']:
            msg = ("Error adding persistent rule. URL: %r" % url)
            LOG.error(msg)
            raise Exception(msg)

        msg = ("Persistent rule successfully added for SERVICE ID: %r"
               " of tenant: %r" % (rule_info['service_id'],
                                   rule_info['tenant_id']))
        LOG.info(msg)
        return "SUCCESS"

    def _clear_static_ips(self, kwargs):
        """ Clear static IPs for provider and stitching
        interfaces of the service VM.

        Issues REST call to service VM for deletion of static IPs.

        :param kwargs: a dictionary of vpn rules and objects
        send by neutron plugin

        Returns: SUCCESS/Failure message with reason.

        """

        rule_info = kwargs.get('rule_info')
        static_ips_info = dict(
                    provider_ip=kwargs.get('provider_ip'),
                    provider_cidr=kwargs.get('provider_cidr'),
                    provider_mac=kwargs.get('provider_mac'),
                    stitching_ip=kwargs.get('stitching_ip'),
                    stitching_cidr=kwargs.get('stitching_cidr'),
                    stitching_mac=kwargs.get('stitching_mac'))
        active_fip = rule_info['active_fip']

        url = const.request_url % (active_fip,
                                   const.CONFIGURATION_SERVER_PORT,
                                   'del_static_ip')
        data = jsonutils.dumps(static_ips_info)

        msg = ("Initiating POST request to remove static IPs for primary "
               "service with SERVICE ID: %r of tenant: %r at: %r" %
               (rule_info['service_id'], rule_info['tenant_id'],
                active_fip))
        LOG.info(msg)
        try:
            resp = requests.delete(url, data=data, timeout=self.timeout)
        except requests.exceptions.ConnectionError as err:
            msg = ("Failed to establish connection to primary service at: "
                   "%r of SERVICE ID: %r of tenant: %r . ERROR: %r" %
                   (active_fip, rule_info['service_id'],
                    rule_info['tenant_id'], str(err).capitalize()))
            LOG.error(msg)
            return msg
        except requests.exceptions.RequestException as err:
            msg = ("Unexpected ERROR happened  while removing "
                   "static IPs for primary service at: %r "
                   "of SERVICE ID: %r of tenant: %r . ERROR: %r" %
                   (active_fip, rule_info['service_id'],
                    rule_info['tenant_id'], str(err).capitalize()))
            LOG.error(msg)
            return msg

        try:
            result = resp.json()
        except ValueError as err:
            msg = ("Unable to parse response, invalid JSON. URL: "
                   "%r. %r" % (url, str(err).capitalize()))
            LOG.error(msg)
            return msg
        if not result['status']:
            msg = ("Error removing static IPs. URL: %r. Reason: %s." %
                   (url, result['reason']))
            LOG.error(msg)
            return msg

        msg = ("Static IPs successfully removed for SERVICE ID: %r"
               " of tenant: %r" % (rule_info['service_id'],
                                   rule_info['tenant_id']))
        LOG.info(msg)
        return const.STATUS_SUCCESS

    def clear_interfaces(self, context, kwargs):
        """
        Clear interfaces for the service VM.

        Makes a ReST call to the service VM to clear the interfaces
        :param context: context dictionary of vpn service type
        :param kwargs: dicionary of a specific operation type, which was sent
        from neutron plugin

        Returns: None
        """
        active_configured = False
        try:
            result_static_ips = self._clear_static_ips(kwargs)
        except Exception as err:
            msg = ("Failed to remove static IPs. Error: %s" % err)
            LOG.error(msg)
            return msg
        else:
            if result_static_ips != const.STATUS_SUCCESS:
                return result_static_ips
            else:
                msg = ("Successfully removed static IPs. "
                       "Result: %s" % result_static_ips)
                LOG.info(msg)

        rule_info = kwargs['rule_info']

        active_rule_info = dict(
            provider_mac=rule_info['provider_mac'],
            stitching_mac=rule_info['stitching_mac'])

        active_fip = rule_info['fip']

        msg = ("Initiating DELETE persistent rule for SERVICE ID: %r of "
               "tenant: %r " %
               (rule_info['service_id'], rule_info['tenant_id']))
        LOG.info(msg)
        url = const.request_url % (active_fip,
                                   const.CONFIGURATION_SERVER_PORT,
                                   'delete_rule')

        try:
            data = jsonutils.dumps(active_rule_info)
            resp = requests.delete(url, data=data, timeout=self.timeout)
        except requests.exceptions.ConnectionError as err:
            msg = ("Failed to establish connection to service at: %r "
                   "of SERVICE ID: %r of tenant: %r . ERROR: %r" % (
                                                    active_fip,
                                                    rule_info['service_id'],
                                                    rule_info['tenant_id'],
                                                    str(err).capitalize()))
            LOG.error(msg)
            raise Exception(err)
        except requests.exceptions.RequestException as err:
            msg = ("Unexpected ERROR happened  while deleting "
                   "persistent rule of service at: %r "
                   "of SERVICE ID: %r of tenant: %r . ERROR: %r" % (
                                                    active_fip,
                                                    rule_info['service_id'],
                                                    rule_info['tenant_id'],
                                                    str(err).capitalize()))
            LOG.error(msg)
            raise Exception(err)

        try:
            result = resp.json()
        except ValueError as err:
            msg = ("Unable to parse response, invalid JSON. URL: "
                   "%r" % (url, str(err).capitalize()))
            LOG.error(msg)
            raise Exception(msg)
        if not result['status'] or resp.status_code not in [200, 201, 202]:
            msg = ("Error deleting persistent rule. URL: %r" % url)
            LOG.error(msg)
            raise Exception(msg)
        msg = ("Persistent rule successfully deleted for SERVICE ID: %r"
               " of tenant: %r " % (rule_info['service_id'],
                                    rule_info['tenant_id']))

        LOG.info(msg)
        return "SUCCESS"

"""
Driver class for implementing VPN IPSEC configuration
requests from VPNaas Plugin.
"""


class VpnaasIpsecDriver(VpnGenericConfigDriver, base_driver.BaseDriver):

    service_type = const.SERVICE_TYPE

    def __init__(self, agent_context):
        self.agent = agent_context
        self.handlers = {
            'vpn_service': {
                'create': self.create_vpn_service},
            'ipsec_site_connection': {
                'create': self.create_ipsec_conn,
                'update': self.update_ipsec_conn,
                'delete': self.delete_ipsec_conn}}
        super(VpnaasIpsecDriver, self).__init__()

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

    def _error_state(self, context, conn, message=''):
        """
        Enqueues the status of the service to ERROR.

        :param context: Dictionary which holds all the required data for
        for vpn service.
        :param conn: ipsec conn dicitonary.
        :param message: the cause for the error.

        Returns: None
        """

        self.agent.update_status(
            context, self._update_conn_status(conn,
                                              const.STATE_ERROR))
        raise ResourceErrorState(id=conn['id'], message=message)

    def _init_state(self, context, conn):
        """
        Enqueues the status of the service to ACTVIE.

        :param context: Dictionary which holds all the required data for
        for vpn service.
        :param conn: ipsec conn dicitonary.

        Returns: None
        """
        msg = "IPSec: Configured successfully- %s " % conn['id']
        LOG.info(msg)
        self.agent.update_status(
            context, self._update_conn_status(conn,
                                              const.STATE_INIT))

        for item in context['service_info']['ipsec_site_conns']:
            if item['id'] == conn['id']:
                item['status'] = const.STATE_INIT

    def _get_stitching_gw_from_desc(self, conn):
        desc = conn['description']
        tokens = desc.split(';')
        stitching_gw = tokens[7].split('=')[1]
        return stitching_gw

    def _get_fip_from_vpnsvc(self, vpn_svc):
        svc_desc = vpn_svc['description']
        tokens = svc_desc.split(';')
        fip = tokens[0].split('=')[1]
        return fip

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

    def _get_stitching_fixed_ip(self, conn):
        desc = conn['description']
        tokens = desc.split(';')
        fixed_ip = tokens[3].split('=')[1]
        return fixed_ip

    def _get_user_access_ip(self, conn):
        desc = conn['description']
        tokens = desc.split(';')
        access_ip = tokens[2].split('=')[1]
        return access_ip

    def _ipsec_conn_correct_enc_algo(self, conn):
        ike_enc_algo = conn['ikepolicy']['encryption_algorithm']
        ipsec_enc_algo = conn['ipsecpolicy']['encryption_algorithm']

        algos = {
            'aes-128': "aes128",
            'aes-256': "aes256",
            'aes-192': "aes256"}

        if ike_enc_algo in algos.keys():
            ike_enc_algo = algos[ike_enc_algo]
        if ipsec_enc_algo in algos.keys():
            ipsec_enc_algo = algos[ipsec_enc_algo]

        conn['ikepolicy']['encryption_algorithm'] = ike_enc_algo
        conn['ipsecpolicy']['encryption_algorithm'] = ipsec_enc_algo

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

    def _ipsec_create_conn(self, context, mgmt_fip, conn):
        """
        Get the context for this ipsec conn and make POST to the service VM.
        :param context: Dictionary which holds all the required data for
        for vpn service.
        :param mgmt_fip: managent floting ip
        :paraM conn: ipsec conn dictionary

        Returns: None
        """

        svc_context = self.agent.get_vpn_servicecontext(
            context, self._get_filters(conn_id=conn['id']))[0]
        tunnel_local_cidr = self.\
            _get_ipsec_tunnel_local_cidr(svc_context)
        conn = svc_context['siteconns'][0]['connection']
        svc_context['siteconns'][0]['connection']['stitching_fixed_ip'] = (
            self._get_stitching_fixed_ip(conn))
        svc_context['siteconns'][0]['connection']['access_ip'] = (
            self._get_user_access_ip(conn))
        msg = "IPSec: Pushing ipsec configuration %s" % conn
        LOG.info(msg)
        conn['tunnel_local_cidr'] = tunnel_local_cidr
        self._ipsec_conn_correct_enc_algo(svc_context['siteconns'][0])
        RestApi(mgmt_fip).post("create-ipsec-site-conn", svc_context)
        self._init_state(context, conn)

    def _ipsec_create_tunnel(self, context, mgmt_fip, conn):
        """
        Get the context for this ipsec conn and make POST to the service VM.
        :param context: Dictionary which holds all the required data for
        for vpn service.
        :param mgmt_fip: managent floting ip
        :paraM conn: ipsec conn dictionary

        Returns: None
        """

        svc_context = self.agent.get_vpn_servicecontext(
            context, self._get_filters(conn_id=conn['id']))[0]

        tunnel_local_cidr = self.\
            _get_ipsec_tunnel_local_cidr(svc_context)

        tunnel = {}
        tunnel['peer_address'] = conn['peer_address']
        tunnel['local_cidr'] = tunnel_local_cidr
        tunnel['peer_cidrs'] = conn['peer_cidrs']

        RestApi(mgmt_fip).post("create-ipsec-site-tunnel", tunnel)
        self._init_state(context, conn)

    def _ipsec_get_tenant_conns(self, context, mgmt_fip, conn,
                                on_delete=False):
        """
        Get the context for this ipsec conn and vpn services.

        :param context: Dictionary which holds all the required data for
        for vpn service.
        :param mgmt_fip: managent floting ip
        :paraM conn: ipsec conn dictionary

        Returns: list of ipsec conns
        """

        filters = {
            'tenant_id': [context['tenant_id']],
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
                self._error_state(context, conn, msg)

        conn_to_remove = None

        for connection in tenant_conns:
            if connection['id'] == conn['id']:
                conn_to_remove = connection
                break
        if conn_to_remove:
            tenant_conns.remove(conn_to_remove)
        if not tenant_conns:
            return tenant_conns

        conn_list = []
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
                if tconn['status'] == (
                                const.STATE_PENDING and tconn in conn_list):
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
                        context, conn, msg)

    def _ipsec_delete_tunnel(self, context, mgmt_fip,
                             conn):
        """
        Make DELETE to the service VM to delete the tunnel.

        :param context: Dictionary which holds all the required data for
        for vpn service.
        :param mgmt_fip: managent floting ip
        :paraM conn: ipsec conn dictionary

        Returns: None
        """

        lcidr = self.\
            _get_ipsec_tunnel_local_cidr_from_vpnsvc(conn)

        tunnel = {}
        tunnel['peer_address'] = conn['peer_address']
        tunnel['local_cidr'] = lcidr
        tunnel['peer_cidrs'] = conn['peer_cidrs']
        try:
            RestApi(mgmt_fip).delete(
                "delete-ipsec-site-tunnel", tunnel)
        except Exception as err:
            msg = ("IPSec: Failed to delete IPSEC tunnel. %s"
                   % str(err).capitalize())
            LOG.error(msg)

    def _ipsec_delete_connection(self, context, mgmt_fip,
                                 conn):
        """
        Make DELETE to the service VM to delete the ipsec conn.

        :param context: Dictionary which holds all the required data for
        for vpn service.
        :param mgmt_fip: managent floting ip
        :paraM conn: ipsec conn dictionary

        Returns: None
        """

        try:
            gateway_ip = self._get_stitching_gw_from_desc(conn)
            LOG.error(gateway_ip)
            url = const.request_url % (mgmt_fip,
                                   const.CONFIGURATION_SERVER_PORT,
                                   'delete-stitching-route')
            data = jsonutils.dumps({'gateway_ip': gateway_ip})
            resp = requests.delete(url, data=data, timeout=self.timeout)
            LOG.error(resp)
            RestApi(mgmt_fip).delete(
                "delete-ipsec-site-conn",
                {'peer_address': conn['peer_address']})
        except Exception as err:
            msg = ("IPSec: Failed to delete IPSEC conn. %s"
                   % str(err).capitalize())
            LOG.error(msg)

    def _ipsec_is_state_changed(self, svc_context, conn, fip):
        """
        Make GET request to the service VM to get the status of the site conn.

        :param svc_context: list of ipsec conn dictionaries
        :paraM conn: ipsec conn dictionary
        :param fip: floting ip of the service VM

        Returns: None
        """

        c_state = None
        lcidr = self.\
            _get_ipsec_tunnel_local_cidr(svc_context)
        if conn['status'] == const.STATE_INIT:
            tunnel = {
                'peer_address': conn['peer_address'],
                'local_cidr': lcidr,
                'peer_cidr': conn['peer_cidrs'][0]}
            output = RestApi(fip).get(
                "get-ipsec-site-tunnel-state",
                tunnel)
            state = output['state']

            if state.upper() == 'UP' and\
               conn['status'] != const.STATE_ACTIVE:
                c_state = const.STATE_ACTIVE
            if state.upper() == 'DOWN' and\
               conn['status'] == const.STATE_ACTIVE:
                c_state = const.STATE_PENDING

        if c_state:
            return c_state, True
        return c_state, False

    def _get_vm_mgmt_ip_from_desc(self, desc):
        svc_desc = desc['description']
        tokens = svc_desc.split(';')
        vm_mgmt_ip = tokens[0].split('=')[1]
        return vm_mgmt_ip

    def create_vpn_service(self, context, kwargs):

        svc = kwargs.get('resource')
        msg = "Validating VPN service %s " % svc
        LOG.info(msg)
        validator = VPNServiceValidator(self.agent)
        validator.validate(context, svc)

    def create_ipsec_conn(self, context, kwargs):
        """
        Implements functions to make update ipsec configuration in service VM.

        :param context: context dictionary of vpn service type
        :param kwargs: dicionary of a specific operation type, which was sent
        from neutron plugin

        Returns: None
        """

        conn = kwargs.get('resource')
        mgmt_fip = self._get_vm_mgmt_ip_from_desc(conn)
        msg = "IPsec: create siteconnection %s" % conn
        LOG.info(msg)
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
        t_lcidr = self._get_ipsec_tunnel_local_cidr_from_vpnsvc(conn)
        if t_lcidr in conn['peer_cidrs']:
            msg = ("IPSec: Tunnel remote cidr %s conflicts "
                   "with local cidr." % t_lcidr)
            LOG.error(msg)
            self._error_state(context, conn, msg)
        if len(conn['peer_cidrs']) != 1:
            msg = ("IPSec: Invalid number of peer CIDR. Should not be"
                   " less than 1.")
            LOG.error(msg)
            self._error_state(context, conn, msg)

        try:
            tenant_conns = self._ipsec_get_tenant_conns(
                context, mgmt_fip, conn)
        except Exception as err:
            msg = ("IPSec: Failed to get tenant conns for IPSEC create. %s"
                   % str(err).capitalize())
            LOG.error(msg)
        try:
            if not tenant_conns:
                self._ipsec_create_conn(context, mgmt_fip, conn)
            else:
                """
                Check if this conn has overlapping peer
                cidr with any other conn for the same
                tenant - we do not support this model.
                """
                self._ipsec_check_overlapping_peer(
                    context, tenant_conns, conn)
                self._ipsec_create_tunnel(context, mgmt_fip, conn)

        except Exception as ex:
            msg = "IPSec: Exception in creating ipsec conn: %s" % ex
            LOG.error(msg)
            self._error_state(context, conn, msg)

    def update_ipsec_conn(self, context, kwargs):
        """
        Implements functions to make update ipsec configuration in service VM.

        :param context: context dictionary of vpn service type
        :param kwargs: dicionary of a specific operation type, which was sent
        from neutron plugin

        Returns: None
        """
        pass

    def delete_ipsec_conn(self, context, kwargs):
        """
        Implements functions to make delete ipsec configuration in service VM.

        :param context: context dictionary of vpn service type
        :param kwargs: dicionary of a specific operation type, which was sent
        from neutron plugin

        Returns: None
        """

        conn = kwargs.get('resource')
        msg = "IPsec: delete siteconnection %s" % conn
        LOG.info(msg)
        mgmt_fip = self._get_vm_mgmt_ip_from_desc(conn)

        tenant_conns = self._ipsec_get_tenant_conns(
            context, mgmt_fip, conn, on_delete=True)
        try:
            if tenant_conns:
                self._ipsec_delete_tunnel(
                    context, mgmt_fip, conn)
            else:
                self._ipsec_delete_connection(
                    context, mgmt_fip, conn)
        except Exception as ex:
            msg = "IPSec: delete ipsec conn failed %s " % ex
            LOG.error(msg)
            self._error_state(context, conn, msg)

    def check_status(self, context, svc_context):
        """
        Implements functions to get the status of the site to site conn.

        :param context: context dictionary of vpn service type
        :param svc_contex: list of ipsec conn dictionaries

        Returns: None
        """
        fip = self._get_fip(svc_context)
        conn = svc_context['siteconns'][0]['connection']

        try:
            state, changed = self._ipsec_is_state_changed(
                svc_context, conn, fip)
        except Exception as err:
            msg = ("Failed to check if IPSEC state is changed. %s"
                   % str(err).capitalize())
            LOG.error(msg)
        if changed:
            self.agent.update_status(
                context, self._update_conn_status(conn,
                                                  state))
        return state

    def vpnservice_updated(self, context, kwargs):
        """
        Demultiplexes the different methods to update the configurations

        :param context: context dictionary of vpn service type
        :param kwargs: dicionary of a specific operation type, which was sent
        from neutron plugin

        Returns: None
        """
        msg = ("Handling VPN service update notification '%s'",
               kwargs.get('reason', ''))
        LOG.info(msg)

        resource = kwargs.get('resource')
        tenant_id = resource['tenant_id']
        # Synchronize the update operation per tenant.
        # Resources under tenant have inter dependencies.

        @lockutils.synchronized(tenant_id)
        def _vpnservice_updated(context, kwargs):
            reason = kwargs.get('reason')
            rsrc = kwargs.get('rsrc_type')

            if rsrc not in self.handlers.keys():
                raise UnknownResourceException(rsrc=rsrc)

            if reason not in self.handlers[rsrc].keys():
                raise UnknownReasonException(reason=reason)

            self.handlers[rsrc][reason](context, kwargs)

        return _vpnservice_updated(context, kwargs)

    def configure_healthmonitor(self, context, kwargs):
        """Overriding BaseDriver's configure_healthmonitor().
           It does netcat to CONFIGURATION_SERVER_PORT  8888.
           Configuration agent runs inside service vm.Once agent is up and
           reachable, service vm is assumed to be active.
           :param context - context
           :param kwargs - kwargs coming from orchestrator

           Returns: SUCCESS/FAILED

        """
        ip = kwargs.get('mgmt_ip')
        port = str(const.CONFIGURATION_SERVER_PORT)
        command = 'nc ' + ip + ' ' + port + ' -z'
        return self._check_vm_health(command)
