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


def prepare_log_meta_data(nf=None, log_meta_data=None,
                          level=None, event_category=None,
                          event=None, service_type=None,
                          service_provider=None):
    """Prepares log meta data string in a specific format

    :param nf - network function object
    :param log_meta_data - already existing log_meta_data string to restructure
                           it along with other params like level,event etc
    :param level - log level
    :param event_category
    :param event
    :param service_type
    :param service_provider

    Returns log_meta_data
    """

    log_info_content = {
        '00_level': (
            ('Level:' + level)
            if level
            else ''),
        '01_event_category': (
            ('EventCategory:' + event_category)
            if event_category
            else ''),
        '02_event': (
            ('Event:' + event)
            if event
            else '')
    }
    log_info_nf_content = {}
    try:
        if nf:
            log_info_nf_content = {
                '03_tenant_id': (
                    ('TenantID:' + nf['tenant_id'])
                    if nf.get('tenant_id')
                    else ''),
                '04_service_chain_id': (
                    ('ServiceChainID:' +
                     nf['service_chain_id'])
                    if nf.get('service_chain_id')
                    else ''),
                '05_service_chain_instance_id': (
                    ('ServiceInstanceID:' +
                     nf['id'])
                    if nf.get('id')
                    else ''),
                '06_service_type': (
                    ('ServiceType:' + service_type)
                    if service_type
                    else ''),
                '07_service_provider': (
                    ('ServiceProvider:' + service_provider)
                    if service_provider
                    else ''),
            }
        elif log_meta_data and log_meta_data != '':
            """Reorganize the log_meta_data string along with new fields
               like EventCategory, Events, Level etc
               e.g log_meta_dat = '[TenantID:tid, ServiceChainID:scid,
                                ServiceInstanceID:siid, ServiceType:FIREWALL,
                                ServiceProvider:vyos] - '
            """

            string = log_meta_data.replace(" ", "")[1:-2]
            nf = dict(kv.split(":") for kv in string.split(","))

            log_info_nf_content = {
                '03_tenant_id': (
                    ('TenantID:' + nf['TenantID'])
                    if nf.get('TenantID')
                    else ''),
                '04_service_chain_id': (
                    ('ServiceChainID:' +
                     nf['ServiceChainID'])
                    if nf.get('ServiceChainID')
                    else ''),
                '05_service_chain_instance_id': (
                    ('ServiceInstanceID:' +
                     nf['ServiceInstanceID'])
                    if nf.get('ServiceInstanceID')
                    else ''),
                '06_service_type': (
                    ('ServiceType:' + nf['ServiceType'])
                    if nf.get('ServiceType')
                    else ''),
                '07_service_provider': (
                    ('ServiceProvider:' + nf['ServiceProvider'])
                    if nf.get('ServiceProvider')
                    else ''),
            }

        log_info_content.update(log_info_nf_content)
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
