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

import json

from collections import OrderedDict
from neutron._i18n import _LE
from oslo_log import log as logging

LOG = logging.getLogger(__name__)

PECAN = 'pecan'
CONFIGURATOR = 'configurator'
ORCHESTRATOR = 'orchestrator'
PROXY_AGENT = 'proxy_agent'
CONFIG_ORCHESTRATOR = 'config_orchestrator'
TRANSPORT_LIB = 'transport'

otc_modules = [PECAN, CONFIGURATOR]
utc_modules = [ORCHESTRATOR, PROXY_AGENT, CONFIG_ORCHESTRATOR, TRANSPORT_LIB]


def prepare_log_meta_data(kwargs):
    """Prepares log meta data string in a specific format.

    :param kwargs - kwargs which needs to be added in the meta data

    Returns log_meta_data
    """

    log_info_content = {
        '00_level': (('Level:' + kwargs["Level"])
                     if kwargs.get("Level") else ""),

        '01_event_category': (('EventCategory:' + kwargs["EventCategory"])
                              if kwargs.get("EventCategory") else ""),

        '02_event': (('Event:' + kwargs["Event"])
                     if kwargs.get("Event") else ""),

        '03_tenant_id': (('TenantID:' + kwargs["TenantID"])
                         if kwargs.get("TenantID") else ""),

        '04_service_chain_id': (
                            ('ServiceChainID:' + kwargs['ServiceChainID'])
                            if kwargs.get("ServiceChainID") else ""),

        '05_service_instance_id': (
                                ('ServiceInstanceID:' +
                                 kwargs["ServiceInstanceID"])
                                if kwargs.get("ServiceInstanceID")
                                else ""),

        '06_service_type': (('ServiceType:' + kwargs["ServiceType"])
                            if kwargs.get("ServiceType") else ""),

        '07_service_provider': (
                            ('ServiceProvider:' + kwargs["ServiceProvider"]
                             if kwargs.get("ServiceProvider") else ""))
    }

    try:
        log_info_content = OrderedDict(sorted(log_info_content.items(),
                                              key=lambda t: t[0]))
        log_msg = '['
        for content in log_info_content:
            if log_info_content.get(content):
                log_msg += log_info_content.get(content) + ', '
        log_msg = log_msg[:-2]
        if log_msg:
            log_msg += '] - '

        return log_msg
    except Exception as err:
        LOG.error(_LE("Error while generating LOG. %s."
                      % str(err).capitalize()))
        return ''


def get_kwargs_from_log_meta_data(log_meta_data):
    """ Convert log_meta_data string to dictionary format

        This function will be useful when want to add some more fields
        to the existing log_meta_data string.
        1) convert log_meta_data string to dictionary(kwargs) format using
           this function
        2) append new fields to this dictionary(kwargs) and prepare
           log_meta_data by using preapre_log_meta_data(kwargs) function

    :param log_meta_data - string

    Returns kwargs - dictionary
    """

    kwargs = {}
    if log_meta_data and log_meta_data != '':
        string = log_meta_data.replace(" ", "")[1:-2]
        kwargs = dict(kv.split(":") for kv in string.split(","))
    return kwargs


def get_log_meta_data(request_data, module):
    """Fetch log_meta_data.
    - over the cloud modules will get 'log_meta_data' from
      body['config'][0]['resource_data'].
    - under the cloud modules will get 'log_meta_data' from
      body['info']['context']

    :param request_data - request_data
    :param module - module_name e.g 1) pecan, configurator
                                    2) proxy_agent, config_orchestrator,
                                       orchestrator

    request_data for generic config apis
    request_data = {
            "info": {
                "service_type": "",
                "service_vendor": "",
                "context": {
                    "requester": "",
                    "operation": "",
                    "log_meta_data": ""
                }
            },
            "config": [{
                "resource": "",
                "resource_data": {
                    "key": "value",
                    .
                    .
                    .
                    "log_meta_data":"" <======== log_meta_data comes here
                }
            }]
        }

    request_data for neutron *aaS apis
    request_data = {
            "info": {
                "service_type": "",
                "service_vendor": "",
                "context": {
                    "requester": "",
                    "operation": "",
                    "log_meta_data": ""
                }
            },
            "config": [{
                "resource": "",
                "resource_data": {
                    "neutron_context": {
                        "service_info": {},
                        "log_meta_data": "" <======== log_meta_data comes here
                    }
                    .
                    .
                    "key": "value"
                }
            }]
        }
    """
    log_meta_data = ""
    try:
        if module in otc_modules:
            """Look for meta data assuming it is generic config request"""
            log_meta_data = (request_data['config'][0]
                             ['resource_data'].get("log_meta_data", ""))
            if log_meta_data == "":
                """Look for meta data assuming it is *aaS request"""
                log_meta_data = (request_data['config'][0]['resource_data']
                                 ['neutron_context'].get("log_meta_data", ""))
        elif module in utc_modules:
            log_meta_data = (request_data['info']
                             ['context'].get("log_meta_data", ""))
        else:
            LOG.error("Wrong module name:%s passed " % (module))
    except Exception:
        pass
    return log_meta_data


def make_dict_readable(dictionary, indent=2):
    """Convert a dictionary in pretty print like readable format

    :param dictionary - which is to be converted in pretty print format
    :param indent

    Returns: dictionary in pretty print like format
    """
    return json.dumps(dictionary, indent=indent)
