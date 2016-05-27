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

import ast
import requests

from neutron import context
from oslo_log import log as logging
from oslo_serialization import jsonutils

from gbpservice.nfp.configurator.drivers.base import base_driver
from gbpservice.nfp.configurator.lib import fw_constants as const

import sys
import json
import pan.xapi
import pan.commit
import pan.config
import time

LOG = logging.getLogger(__name__)

import sys


""" Firewall generic configuration driver for handling device
configuration requests.

"""
class FwGenericConfigDriver(object):
    """
    Driver class for implementing firewall configuration
    requests from Orchestrator.
    """

    def __init__(self):
        pass

    def _configure_static_ips(self, kwargs):
        """ Configure static IPs for provider and stitching interfaces
        of service VM.

        Issues REST call to service VM for configuration of static IPs.

        :param kwargs: a dictionary of firewall rules and objects
        send by neutron plugin

        Returns: SUCCESS/Failure message with reason.

        """
        return const.STATUS_SUCCESS

    def _clear_static_ips(self, kwargs):
        """ Clear static IPs for provider and stitching
        interfaces of the service VM.

        Issues REST call to service VM for deletion of static IPs.

        :param kwargs: a dictionary of firewall rules and objects
        send by neutron plugin

        Returns: SUCCESS/Failure message with reason.

        """
        return const.STATUS_SUCCESS

    def configure_interfaces(self, context, kwargs):
        """ Configure interfaces for the service VM.

        Calls static IP configuration function and implements
        persistent rule addition in the service VM.
        Issues REST call to service VM for configuration of interfaces.

        :param context: neutron context
        :param kwargs: a dictionary of firewall rules and objects
        send by neutron plugin

        Returns: SUCCESS/Failure message with reason.

        """
        time.sleep(const.PA_AUTOCOMMIT_WAITTIME)
        vm_mgmt_ip = kwargs.get('mgmt_ip') 
        self.check_auto_commit_status(hostname=vm_mgmt_ip)
        
        # apply staic ip to stitching interface
        stitching_interface_index = kwargs.get('stitching_interface_index')
        stitching_interface_name = "ethernet1/%d" % \
                                        (stitching_interface_index-1)
        stitching_ip = kwargs.get('stitching_ip')
        stitching_ip = ("%s/24" % stitching_ip)
        self.apply_static_ip(vm_mgmt_ip, 
                             stitching_interface_name, stitching_ip)

        # apply staic ip to provider interface
        provider_interface_index = kwargs.get('provider_interface_index')
        provider_interface_name = "ethernet1/%d" % \
                                        (provider_interface_index-1)
        provider_ip = kwargs.get('provider_ip')
        self.apply_static_ip(vm_mgmt_ip, 
                             provider_interface_name, provider_ip)

        # commit
        try:
            resp = self.commit(hostname=vm_mgmt_ip)
        except pan.xapi.PanXapiError as err:
            self._print_exception('PanXapiError', err, const.COMMIT)
            raise pan.xapi.PanXapiError(err)
        except pan.config.PanConfigError as err:
            self._print_exception('PanConfigError', err, const.COMMIT)
            raise pan.config.PanConfigError(err)
        except Exception as err:
            self._print_exception('UnexpectedError', err, const.COMMIT, resp)
            raise Exception(err)

        if self.analyze_response("COMMITED the configuration to Service VM",
                 resp, const.COMMIT) == const.STATUS_ERROR:
            return const.STATUS_ERROR

        # wait till commit is finished
        job_id = resp['response']['result']['job'] 
        self.check_commit_status(vm_mgmt_ip, job_id)

        return const.STATUS_SUCCESS

    def apply_static_ip(self, hostname, interface_name, interface_ip):
        LOG.info("Applying static ip '%s' to interface '%s'" % \
                                    (interface_ip, interface_name))
        element = (const.INTERFACE_CONFIG_TEMPLATE % \
                                (interface_name, interface_ip))
        try:
            resp = self.edit_interface(hostname, interface_name, element)
        except pan.xapi.PanXapiError as err:
            self._print_exception('PanXapiError', err,
                                  const.APPLY_STATIC_IP)
            raise pan.xapi.PanXapiError(err)
        except pan.config.PanConfigError as err:
            self._print_exception('PanConfigError', err,
                                  const.APPLY_STATIC_IP)
            raise pan.config.PanConfigError(err)
        except Exception as err:
            self._print_exception('UnexpectedError', err,
                                  const.APPLY_STATIC_IP, resp)
            raise Exception(err)

    def clear_interfaces(self, context, kwargs):
        """ Clear interfaces for the service VM.

        Calls static IP clear function and implements
        persistent rule deletion in the service VM.
        Issues REST call to service VM for deletion of interfaces.

        :param context: neutron context
        :param kwargs: a dictionary of firewall rules and objects
        send by neutron plugin

        Returns: SUCCESS/Failure message with reason.

        """
        return const.STATUS_SUCCESS

    def configure_routes(self, context, kwargs):
        """ Configure routes for the service VM.

        Issues REST call to service VM for configuration of routes.

        :param context: neutron context
        :param kwargs: a dictionary of firewall rules and objects
        send by neutron plugin

        Returns: SUCCESS/Failure message with reason.

        """
        vm_mgmt_ip = kwargs.get('mgmt_ip')

        # add pbf rule
        gateway_ip = kwargs.get('gateway_ip')
        pbf_name = const.PBF_RULE_NAME
        element = self.create_pbf_rule_element(pbf_name=pbf_name,
                        from_interface=const.PBF_FROM_INTERFACE,
                        egress_interface=const.PBF_NEXT_HOP_IP,
                        next_hop_ip=gateway_ip)
        try:
            resp = self.add_pbf(vm_mgmt_ip, element)
        except pan.xapi.PanXapiError as err:
            self._print_exception('PanXapiError', err,
                                  const.ADD_PBF_RULE)
            raise pan.xapi.PanXapiError(err)
        except pan.config.PanConfigError as err:
            self._print_exception('PanConfigError', err,
                                  const.ADD_PBF_RULE)
            raise pan.config.PanConfigError(err)
        except Exception as err:
            self._print_exception('UnexpectedError', err,
                                  const.ADD_PBF_RULE, resp)
            raise Exception(err)
    
        msg = "POSTED pbf rule '%s' to Service VM" % pbf_name
        if self.analyze_response(msg, resp, const.ADD_PBF_RULE)\
                        == const.STATUS_ERROR:
            return const.STATUS_ERROR
    
        # commit
        try:
            resp = self.commit(hostname=vm_mgmt_ip)
        except pan.xapi.PanXapiError as err:
            self._print_exception('PanXapiError', err, const.COMMIT)
            raise pan.xapi.PanXapiError(err)
        except pan.config.PanConfigError as err:
            self._print_exception('PanConfigError', err, const.COMMIT)
            raise pan.config.PanConfigError(err)
        except Exception as err:
            self._print_exception('UnexpectedError', err, const.COMMIT, resp)
            raise Exception(err)

        if self.analyze_response("COMMITED the configuration to Service VM",
                 resp, const.COMMIT) == const.STATUS_ERROR:
            return const.STATUS_ERROR

        # wait till commit is finished
        job_id = resp['response']['result']['job'] 
        self.check_commit_status(vm_mgmt_ip, job_id)

        return const.STATUS_SUCCESS
        
    def clear_routes(self, context, kwargs):
        """ Clear routes for the service VM.

        Issues REST call to service VM for deletion of routes.

        :param context: neutron context
        :param kwargs: a dictionary of firewall rules and objects
        send by neutron plugin

        Returns: SUCCESS/Failure message with reason.

        """
        # delete pbf rule
        vm_mgmt_ip = kwargs.get('mgmt_ip')
        pbf_name = const.PBF_RULE_NAME + "_" + vm_mgmt_ip
        try:
            resp = self.delete_pbf(vm_mgmt_ip, pbf_name)
        except pan.xapi.PanXapiError as err:
            self._print_exception('PanXapiError', err,
                  const.DELETE_PBF_RULE)
            raise pan.xapi.PanXapiError(err)
        except pan.config.PanConfigError as err:
            self._print_exception('PanConfigError', err,
                  const.DELETE_PBF_RULE)
            raise pan.config.PanConfigError(err)
        except Exception as err:
            self._print_exception('UnexpectedError', err,
                                  const.DELETE_PBF_RULE, resp)
            raise Exception(err)
        
        msg = "DELETED pbf rule '%s' to Service VM" % pbf_name
        if self.analyze_response(msg, resp, const.DELETE_PBF_RULE)\
                            == const.STATUS_ERROR:
            return const.STATUS_ERROR
 
        # commit
        try:
            resp = self.commit(hostname=vm_mgmt_ip)
        except pan.xapi.PanXapiError as err:
            self._print_exception('PanXapiError', err, const.COMMIT)
            raise pan.xapi.PanXapiError(err)
        except pan.config.PanConfigError as err:
            self._print_exception('PanConfigError', err, const.COMMIT)
            raise pan.config.PanConfigError(err)
        except Exception as err:
            self._print_exception('UnexpectedError', err, const.COMMIT, resp)
            raise Exception(err)
  
        if self.analyze_response("COMMITED the configuration to Service VM",
                                 resp, const.COMMIT) == const.STATUS_ERROR:
            return const.STATUS_ERROR

        # wait till commit is finished
        job_id = resp['response']['result']['job'] 
        self.check_commit_status(vm_mgmt_ip, job_id)

        return const.STATUS_SUCCESS

    def check_auto_commit_status(self, hostname):
        self.check_commit_status(hostname=hostname, job_id="1")

    def check_commit_status(self, hostname, job_id):
        LOG.info("Checking for commit job status...")
        status = "ACT"
        while status != "FIN": 
            try:
                time.sleep(5)
                xapi = self.build_xapi(hostname)
                cmd = ('show jobs id "%s"' % job_id)
                xapi.op('show jobs id "1"', cmd_xml=True)
                response = self.xml_python(xapi)
                status = response['response']['result']['job']['status']
                LOG.info("Commit status == %s" % status)
            except pan.xapi.PanXapiError as err:
                self._print_exception('PanXapiError', err, const.COMMIT)
                raise pan.xapi.PanXapiError(err)
            except pan.config.PanConfigError as err:
                self._print_exception('PanConfigError', err, const.COMMIT)
                raise pan.config.PanConfigError(err)
            except Exception as err:
                self._print_exception('UnexpectedError', err, const.COMMIT)
                raise Exception(err)
 
    def create_pbf_rule_element(self, pbf_name, from_interface,
                                egress_interface, next_hop_ip):
        string = (const.PBF_RULE_TEMPLATE) % (pbf_name,
                                              from_interface,
                                              egress_interface,
                                              next_hop_ip)
        return string

    def edit_interface(self, hostname, interface_name, element):
        xapi = self.build_xapi(hostname)
        xpath = const.INTERFACE_CONFIG_ENTRY_URL % interface_name
        xapi.edit(xpath=xpath, element=element)
        return self.xml_python(xapi)

    def show_interface(self, hostname, interface_name):
        xapi = self.build_xapi(hostname)
        xpath = const.INTERFACE_CONFIG_ENTRY_URL % interface_name
        xapi.show(xpath=xpath)
        return self.xml_python(xapi)

    def add_pbf(self, hostname, element):
        xapi = self.build_xapi(hostname)
        xpath = const.PBF_RULES_URL 
        xapi.set(xpath=xpath, element=element)
        return self.xml_python(xapi)

    def edit_pbf(self, hostname, pbf_name, element):
        xapi = self.build_xapi(hostname)
        xpath = const.PBF_RULE_ENTRY_URL % pbf_name
        xapi.edit(xpath=xpath, element=element)
        return self.xml_python(xapi)

    def delete_pbf(self, hostname, pbf_name):
        xapi = self.build_xapi(hostname)
        xpath = const.PBF_RULE_ENTRY_URL % pbf_name
        xapi.delete(xpath=xpath)
        return self.xml_python(xapi)

    def show_pbf(self, hostname, pbf_name):
        xapi = self.build_xapi(hostname)
        xpath = const.PBF_RULE_ENTRY_URL % pbf_name
        xapi.show(xpath=xpath)
        return self.xml_python(xapi)

    def commit(self, hostname):
        xapi = self.build_xapi(hostname)
        c = pan.commit.PanCommit(validate=False,
                                 force=False,
                                 commit_all=False,
                                 merge_with_candidate=False)
        cmd = c.cmd()
        kwargs = {
                    'cmd': cmd,
                    'sync': False,
                    'interval': None,
                    'timeout': self.timeout,
                    }
        xapi.commit(**kwargs)
        return self.xml_python(xapi)

    def build_xapi(self, hostname):
        xapi = pan.xapi.PanXapi(timeout=self.timeout,
                                tag=None,
                                use_http=False,
                                use_get=False,
                                api_username=const.API_USERNAME,
                                api_password=const.API_PASSWORD,
                                api_key=None,
                                hostname=hostname,
                                port=None,
                                serial=None,
                                ssl_context=None)
        return xapi

    def xml_python(self, xapi):
        xpath = None
        if xapi.element_root is None:
            return None

        elem = xapi.element_root
        conf = pan.config.PanConfig(config=elem)
        d = conf.python(xpath)
        return d

    def _print_exception(self, exception_type, err,
                         operation, response=None):
        """ Abstract class for printing log messages

        :param exception_type: Name of the exception as a string
        :param err: Either error of type Exception
        :param operation: "Add/Update/Delete/Commit security rule"
        :param response: The dictionary of PaloAlto Firewall response

        """

        if exception_type == 'PanXapiError':
            msg = ("PanXapiError occurred while %s: %s.\n Response: '%s'"
                   % (operation, str(err).capitalize(), str(response)))
            LOG.error(msg)
        elif exception_type == 'PanConfigError':
            msg = ("PanConfigError occurred while %s: %s.\n Response: '%s'"
                   % (operation, str(err).capitalize(), str(response)))
            LOG.error(msg)
        elif exception_type == 'KeyError':
            msg = ("KeyError occurred while %s: %s.\n Response: '%s'"
                   % (operation, str(err).capitalize(), str(response)))
            LOG.error(msg)
        elif exception_type == 'UnexpectedError':
            msg = ("Unexpected error occurred while %s: %s.\n Response: '%s'"
                    % (operation, str(err).capitalize(), str(response)))
            LOG.error(msg)

    def analyze_response(self, msg, response, operation):
        """ Analyze the response from PaloAlto Firewall
    
        :param msg: The msg to log regarding current status
        :param response: The dictionary of PaloAlto Firewall response
        :param operation: "Add/Update/Delete/Commit security rule"

        Returns: SUCCESS/ERROR status 
        """
        
        LOG.info(msg)
        try:
            if response['response']['status'] == 'success':
                s = ("%s %s" % (operation, "succeeded"))
                LOG.info(s)
                return const.STATUS_SUCCESS

            else:
                s = ("%s firewall %s" % (operation, "failed"))
                LOG.info(s)
                LOG.error(str(response))
                return const.STATUS_ERROR
        except KeyError as err:
            LOG.error(err)
            self._print_exception('KeyError', err,
                                  operation, response)
            return const.STATUS_ERROR
        except Exception as err:
            LOG.error(err)
            self._print_exception('UnexpectedError', err,
                                  operation, response)
            return const.STATUS_ERROR


""" Firewall as a service driver for handling firewall
service configuration requests.

We initialize service type in this class because agent loads
class object only for those driver classes that have service type
initialized. Also, only this driver class is exposed to the agent.

"""


class FwaasDriver(FwGenericConfigDriver, base_driver.BaseDriver):
    service_type = const.SERVICE_TYPE
    service_vendor = const.PALOALTO

    def __init__(self, conf):
        self.conf = conf
        self.timeout = const.REST_TIMEOUT
        self.host = self.conf.host
        self.port = const.CONFIGURATION_SERVER_PORT
        self.context = context.get_admin_context_without_session()
        super(FwaasDriver, self).__init__()

    def _get_firewall_attribute(self, firewall):
        """ Retrieves management IP from the firewall resource received

        :param firewall: firewall dictionary containing rules
        and other objects

        Returns: management IP

        """

        description = ast.literal_eval(firewall["description"])
        if not description.get('vm_management_ip'):
            msg = ("Failed to find vm_management_ip.")
            LOG.debug(msg)
            raise

        if not description.get('service_vendor'):
            msg = ("Failed to find service_vendor.")
            LOG.debug(msg)
            raise

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

        Returns: ACTIVE/ERROR status

        """
    
        # get management IP
        msg = ("Processing create firewall request in FWaaS Driver "
               "for Firewall ID: %s." % firewall['id'])
        LOG.info(msg)
        vm_mgmt_ip = self._get_firewall_attribute(firewall)
        msg = ("Initiating SET request for FIREWALL ID: %r Tenant ID:"
               " %r." % (firewall['id'], firewall['tenant_id']))
        LOG.info(msg)

        # add security rule
        service_name = const.DEFAULT_ANY
        application_name = const.DEFAULT_ANY
        for curr_rule in firewall['firewall_rule_list']:
            rule_name = curr_rule['name']
            if curr_rule['protocol'] != 'icmp':
                try:
                    if curr_rule['destination_port']:
                        destination_port = curr_rule['destination_port']
                    else:
                        destination_port = const.DEFAULT_PA_HTTP
                    service_name = self.create_pa_service(vm_mgmt_ip,
                                                curr_rule['protocol'],
                                                destination_port)
                    application_name = const.DEFAULT_ANY
                except Exception as err:
                    raise Exception(err)
            else: 
                try:
                    application_name = self.create_pa_application(vm_mgmt_ip,
                                                    curr_rule['protocol']) 
                    service_name = const.DEFAULT_SERVICE_NAME
                except Exception as err:
                    raise Exception(err)

            element = self.create_security_rule_element(
                        rule_name=rule_name, action=curr_rule['action'],
                        source_member=curr_rule['source_ip_address'],
                        destination_member=curr_rule['destination_ip_address'],
                        service_member=service_name,
                        application_member=application_name)

            try:
                resp = self.add_security_rule(vm_mgmt_ip, element)
            except pan.xapi.PanXapiError as err:
                self._print_exception('PanXapiError', err,
                                      const.ADD_SECURITY_RULE)
                raise pan.xapi.PanXapiError(err)
            except pan.config.PanConfigError as err:
                self._print_exception('PanConfigError', err,
                                      const.ADD_SECURITY_RULE)
                raise pan.config.PanConfigError(err)
            except Exception as err:
                self._print_exception('UnexpectedError', err,
                                      const.ADD_SECURITY_RULE, resp)
                raise Exception(err)
    
            msg = "POSTED security rule '%s' to Service VM" % rule_name
            if self.analyze_response(msg, resp, const.ADD_SECURITY_RULE)\
                                        == const.STATUS_ERROR:
                return const.STATUS_ERROR

        # commit
        try:
            resp = self.commit(hostname=vm_mgmt_ip)
        except pan.xapi.PanXapiError as err:
            self._print_exception('PanXapiError', err, const.COMMIT)
            raise pan.xapi.PanXapiError(err)
        except pan.config.PanConfigError as err:
            self._print_exception('PanConfigError', err, const.COMMIT)
            raise pan.config.PanConfigError(err)
        except Exception as err:
            self._print_exception('UnexpectedError', err, const.COMMIT, resp)
            raise Exception(err)

        if self.analyze_response("COMMITED the configuration to Service VM",
                 resp, const.COMMIT) == const.STATUS_ERROR:
            return const.STATUS_ERROR

        return const.STATUS_ACTIVE

    def update_firewall(self, context, firewall, host):
        """ Implements firewall updation

        Issues REST call to service VM for firewall updation

        :param context: Neutron context
        :param firewall: Firewall resource object from neutron fwaas plugin
        :param host: Name of the host machine

        Returns: UPDATED/ERROR status

        """

        return const.STATUS_UPDATED

    def delete_firewall(self, context, firewall, host):
        """ Implements firewall deletion

        Issues REST call to service VM for firewall deletion

        :param context: Neutron context
        :param firewall: Firewall resource object from neutron fwaas plugin
        :param host: Name of the host machine

        Returns: DELETED/ERROR status 

        """

        vm_mgmt_ip = self._get_firewall_attribute(firewall)
        msg = ("Initiating DELETE request.")
        LOG.info(msg)

        # delete security rule
        for curr_rule in firewall['firewall_rule_list']:
            rule_name = curr_rule['name']

            try:
                resp = self.delete_security_rule(vm_mgmt_ip, rule_name)
            except pan.xapi.PanXapiError as err:
                self._print_exception('PanXapiError', err,
                                      const.DELETE_SECURITY_RULE)
                raise pan.xapi.PanXapiError(err)
            except pan.config.PanConfigError as err:
                self._print_exception('PanConfigError', err,
                                      const.DELETE_SECURITY_RULE)
                raise pan.config.PanConfigError(err)
            except Exception as err:
                self._print_exception('UnexpectedError', err,
                                      const.DELETE_SECURITY_RULE, resp)
                raise Exception(err)

            msg = "DELETED security rule '%s' to Service VM" % rule_name
            if self.analyze_response(msg, resp, const.DELETE_SECURITY_RULE)\
                                            == const.STATUS_ERROR:
                return const.STATUS_ERROR
    
        for curr_rule in firewall['firewall_rule_list']:

            if curr_rule['protocol'] != 'icmp':
                service_name = ("firewall-%s-%s" % (curr_rule['protocol'],
                                            curr_rule['destination_port']))
                try:
                    resp = self.delete_security_service(vm_mgmt_ip,
                                                        service_name)
                except pan.xapi.PanXapiError as err:
                    self._print_exception('PanXapiError', err,
                                          const.DELETE_SECURITY_SERVICE)
                    raise pan.xapi.PanXapiError(err)
                except pan.config.PanConfigError as err:
                    self._print_exception('PanConfigError', err,
                                          const.DELETE_SECURITY_SERVICE)
                    raise pan.config.PanConfigError(err)
                except Exception as err:
                    self._print_exception('UnexpectedError', err,
                                          const.DELETE_SECURITY_SERVICE, resp)
                    raise Exception(err)

                msg = "DELETED security service '%s' to Service VM"\
                                                            % service_name
                if self.analyze_response(msg, resp,
                                         const.DELETE_SECURITY_SERVICE)\
                                            == const.STATUS_ERROR:
                    return const.STATUS_ERROR
            else:
                application_name = 'ping-' + curr_rule['protocol']        
                try:
                    resp = self.delete_security_application(vm_mgmt_ip,
                                                            application_name)
                except pan.xapi.PanXapiError as err:
                    self._print_exception('PanXapiError', err,
                                          const.DELETE_APPLICATION_SERVICE)
                    raise pan.xapi.PanXapiError(err)
                except pan.config.PanConfigError as err:
                    self._print_exception('PanConfigError', err,
                                          const.DELETE_APPLICATION_SERVICE)
                    raise pan.config.PanConfigError(err)
                except Exception as err:
                    self._print_exception('UnexpectedError', err,
                                      const.DELETE_APPLICATION_SERVICE, resp)
                    raise Exception(err)

                msg = "DELETED security application '%s' to Service VM"\
                                                            % application_name
                if self.analyze_response(msg, resp,
                                        const.DELETE_SECURITY_APPLICATION)\
                                         == const.STATUS_ERROR:
                    return const.STATUS_ERROR

        # commit
        try:
            resp = self.commit(hostname=vm_mgmt_ip)
        except pan.xapi.PanXapiError as err:
            self._print_exception('PanXapiError', err, const.COMMIT)
            raise pan.xapi.PanXapiError(err)
        except pan.config.PanConfigError as err:
            self._print_exception('PanConfigError', err, const.COMMIT)
            raise pan.config.PanConfigError(err)
        except Exception as err:
            self._print_exception('UnexpectedError', err, const.COMMIT, resp)
            raise Exception(err)
  
        if self.analyze_response("COMMITED the configuration to Service VM",
                                 resp, const.COMMIT) == const.STATUS_ERROR:
            return const.STATUS_ERROR

        return const.STATUS_DELETED

    def create_security_rule_element(self, rule_name,
                                           from_member='any',
                                           to_member='any',
                                           action='allow',
                                           source_member='any',
                                           destination_member='any',
                                           service_member='any',
                                           application_member='any'):
        string = ((const.SECURITY_RULE_TEMPALTE) % (rule_name,
                            from_member, to_member, action,
                            source_member, destination_member,
                            service_member, application_member))
        LOG.info("CREATE create_security_rule_element: %s" % string)
        return string

    def create_pa_service(self, vm_mgmt_ip, protocol,
                          port):
        service_name = 'firewall-' + protocol + '-' + port 
        LOG.info("SERVICE NAME: %s" % service_name)
        service_element = self.create_service_element(
                                    service_name=service_name,
                                    protocol=protocol, port=port)
        try:
            resp = self.add_security_service(vm_mgmt_ip, service_element)
        except pan.xapi.PanXapiError as err:
            self._print_exception('PanXapiError', err,
                                  const.ADD_SECURITY_SERVICE)
            raise pan.xapi.PanXapiError(err)
        except pan.config.PanConfigError as err:
            self._print_exception('PanConfigError', err,
                                  const.ADD_SECURITY_SERVICE)
            raise pan.config.PanConfigError(err)
        except Exception as err:
            self._print_exception('UnexpectedError', err,
                                  const.ADD_SECURITY_SERVICE, resp)
            raise Exception(err)
    
        msg = "POSTED service '%s' to Service VM" % service_name
        LOG.info(msg)
        return service_name
            
    def create_pa_application(self, vm_mgmt_ip, protocol):
        application_name =  'ping-' + protocol
        application_element = self.create_application_element(
                                        application_name=application_name)
        try:
            resp = self.add_security_application(vm_mgmt_ip, application_element)
        except pan.xapi.PanXapiError as err:
            self._print_exception('PanXapiError', err,
                                  const.ADD_SECURITY_APPLICATION)
            raise pan.xapi.PanXapiError(err)
        except pan.config.PanConfigError as err:
            self._print_exception('PanConfigError', err,
                                  const.ADD_SECURITY_APPLICATION)
            raise pan.config.PanConfigError(err)
        except Exception as err:
            self._print_exception('UnexpectedError', err,
                                  const.ADD_SECURITY_APPLICATION, resp)
            raise Exception(err)
    
        msg = "POSTED application '%s' to Service VM" % application_name
        LOG.info(msg)
        return application_name

    def create_service_element(self, service_name,
                                     protocol='tcp',
                                     port='80'):
        if protocol == 'tcp':
            string = ((const.SECURITY_SERVICE_TCP_TEMPALTE) % (service_name,
                                                               port))
        elif protocol == 'udp':
            string = ((const.SECURITY_SERVICE_UDP_TEMPALTE) % (service_name,
                                                               port))
        return string

    def create_application_element(self, application_name):
        string = ((const.SECURITY_APPLICATION_TEMPALTE) % (application_name))
        return string

    def add_security_service(self, hostname, element):
        xapi = self.build_xapi(hostname)
        xpath = const.SECURITY_SERVICE_URL
        xapi.set(xpath=xpath, element=element)
        return self.xml_python(xapi)

    def add_security_application(self, hostname, element):
        xapi = self.build_xapi(hostname)
        xpath = const.SECURITY_APPLICATION_URL
        xapi.set(xpath=xpath, element=element)
        return self.xml_python(xapi)

    def delete_security_service(self, hostname, service_name):
        xapi = self.build_xapi(hostname)
        xpath = const.SECURITY_SERVICE_ENTRY_URL % service_name
        xapi.delete(xpath=xpath)
        return self.xml_python(xapi)

    def delete_security_application(self, hostname, application_name):
        xapi = self.build_xapi(hostname)
        xpath = const.SECURITY_APPLICATION_ENTRY_URL % application_name
        xapi.delete(xpath=xpath)
        return self.xml_python(xapi)

    def add_security_rule(self, hostname, element):
        xapi = self.build_xapi(hostname)
        xpath = const.SECURITY_RULES_URL
        xapi.set(xpath=xpath, element=element)
        return self.xml_python(xapi)

    def edit_security_rule(self, hostname, rule_name, element):
        xapi = self.build_xapi(hostname)
        xpath = const.SECURITY_RULE_ENTRY_URL % rule_name
        xapi.edit(xpath=xpath, element=element)
        return self.xml_python(xapi)

    def delete_security_rule(self, hostname, rule_name):
        xapi = self.build_xapi(hostname)
        xpath = const.SECURITY_RULE_ENTRY_URL % rule_name
        xapi.delete(xpath=xpath)
        return self.xml_python(xapi)

    def show_security_rule(self, hostname, rule_name):
        xapi = self.build_xapi(hostname)
        xpath = const.SECURITY_RULE_ENTRY_URL % rule_name
        xapi.show(xpath=xpath)
        return self.xml_python(xapi)

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
        port = str(const.CONFIGURATION_SERVER_PORT_PA)
        #command = 'ping -c20 ' + ip
        command = 'nc ' + ip + ' ' + port + ' -z'
        return self._check_vm_health(command)

