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

PALOALTO = 'paloalto'
REST_TIMEOUT = 120
CONFIGURATION_SERVER_PORT_PA = '443'

DEFAULT_PA_HTTP = '80'
DEFAULT_ANY = 'any'
DEFAULT_SERVICE_NAME = 'application-default'

ADD_SECURITY_RULE = "Add security rule"
UPDATE_SECURITY_RULE = "Update security rule"
DELETE_SECURITY_RULE = "Delete security rule"

ADD_PBF_RULE = "Add pbf rule"
DELETE_PBF_RULE = "Delete pbf rule"
PBF_FROM_INTERFACE = "ethernet1/1"
PBF_NEXT_HOP_IP = "ethernet1/2"

ADD_SECURITY_SERVICE = "ADD Security service"
UPDATE_SECURITY_SERVICE = "Update security service"
DELETE_SECURITY_SERVICE = "Delete security service"

ADD_SECURITY_APPLICATION = "ADD Security application"
UPDATE_SECURITY_APPLICATION = "Update security application"
DELETE_SECURITY_APPLICATION = "Delete security application"

APPLY_STATIC_IP = "Apply static ip"

COMMIT = "Commit"

API_USERNAME = "admin"
API_PASSWORD = "admin"
CONFIGURATION_SERVER_PORT = "443"

SECURITY_RULES_URL = "/config/devices/entry/vsys/entry/rulebase/security/rules"
SECURITY_RULE_ENTRY_URL = \
   "/config/devices/entry/vsys/entry/rulebase/security/rules/entry[@name='%s']"
SECURITY_RULE_TEMPALTE = (
                            '<entry name="%s">'
                            '<from>'
                            '<member>%s</member>'
                            '</from>'
                            '<to>'
                            '<member>%s</member>'
                            '</to>'
                            '<action>%s</action>'
                            '<source>'
                            '<member>%s</member>'
                            '</source>'
                            '<destination>'
                            '<member>%s</member>'
                            '</destination>'
                            '<service>'
                            '<member>%s</member>'
                            '</service>'
                            '<application>'
                            '<member>%s</member>'
                            '</application>'
                            '</entry>'
                        )

PBF_RULE_NAME = "pbf"
PBF_RULES_URL = "/config/devices/entry/vsys/entry/rulebase/pbf/rules"
PBF_RULE_ENTRY_URL = \
        "/config/devices/entry/vsys/entry/rulebase/pbf/rules/entry[@name='%s']"
PBF_RULE_TEMPLATE = (
                        '<entry name="%s">'
                        '<from>'
                        '<interface>'
                        '<member>%s</member>'
                        '</interface>'
                        '</from>'
                        '<destination>'
                        '<member>any</member>'
                        '</destination>'
                        '<service>'
                        '<member>any</member>'
                        '</service>'
                        '<action>'
                        '<forward>'
                        '<egress-interface>%s</egress-interface>'
                        '<nexthop>'
                        '<ip-address>%s</ip-address>'
                        '</nexthop>'
                        '</forward>'
                        '</action>'
                        '<source>'
                        '<member>any</member>'
                        '</source>'
                        '</entry>'
                    )


SECURITY_SERVICE_URL = "/config/devices/entry/vsys/entry/service"
SECURITY_SERVICE_ENTRY_URL = \
    "/config/devices/entry/vsys/entry/service/entry[@name='%s']"
SECURITY_SERVICE_TCP_TEMPALTE = (
                                    '<entry name="%s">'
                                    '<protocol>'
                                    '<tcp><port>%s</port></tcp>'
                                    '</protocol>'
                                    '</entry>'
                                )
SECURITY_SERVICE_UDP_TEMPALTE = (
                                    '<entry name="%s">'
                                    '<protocol>'
                                    '<udp><port>%s</port></udp>'
                                    '</protocol>'
                                    '</entry>'
                                )

SECURITY_APPLICATION_URL = "/config/devices/entry/vsys/entry/application"
SECURITY_APPLICATION_ENTRY_URL = \
    "/config/devices/entry/vsys/entry/application/entry[@name='%s']"
SECURITY_APPLICATION_TEMPALTE = (
                                    '<entry name="%s">'
                                    '<default>'
                                    '<ident-by-icmp-type>'
                                    '<type>8</type>'
                                    '<code>0</code>'
                                    '</ident-by-icmp-type>'
                                    '</default>'
                                    '<subcategory>ip-protocol</subcategory>'
                                    '<category>networking</category>'
                                    '<technology>network-protocol</technology>'
                                    '<risk>1</risk>'
                                    '</entry>'
                                )

INTERFACE_CONFIG_URL = "/config/devices/entry/network/interface/ethernet"
INTERFACE_CONFIG_ENTRY_URL = \
        "/config/devices/entry/network/interface/ethernet/entry[@name='%s']"
INTERFACE_CONFIG_TEMPLATE = (
                                '<entry name="%s">'
                                '<layer3>'
                                '<ipv6>'
                                '<neighbor-discovery>'
                                '<router-advertisement>'
                                '<enable>no</enable>'
                                '</router-advertisement>'
                                '</neighbor-discovery>'
                                '</ipv6>'
                                '<ndp-proxy>'
                                '<enabled>no</enabled>'
                                '</ndp-proxy>'
                                '<lldp>'
                                '<enable>no</enable>'
                                '</lldp>'
                                '<ip>'
                                '<entry name="%s"/>'
                                '</ip>'
                                '<interface-management-profile>'
                                'enable_default_services'
                                '</interface-management-profile>'
                                '</layer3>'
                                '</entry>'
                            )
