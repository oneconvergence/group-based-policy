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

import logging
import netifaces
import time

from execformat.executor import session
from netifaces import AF_LINK
from operations import ConfigOpts
from vyos_session.utils import init_logger

logger = logging.getLogger(__name__)
init_logger(logger)

COMMAND = "interfaces ethernet %s address %s/%s"

""" Implements attachment and detachment of fixed IPs to
    hot-plugged interfaces based on IP and MAC binding.

"""


class StaticIp(ConfigOpts):

    def __init__(self):
        self.hotplug_timeout = 25

    def save(self):
        retries = 100
        while retries:
            try:
                session.commit()
                session.save()
                time.sleep(3)
                session.teardown_config_session()
                return
            except Exception:
                time.sleep(0.1)
                retries -= 1

    def discard(self):
        session.discard()
        time.sleep(3)
        session.teardown_config_session()

    def check_if_interface_is_up(self, pip, sip):
        start_time = time.time()
        while time.time() - start_time < self.hotplug_timeout:
            interfaces = netifaces.interfaces()
            if (pip in interfaces and sip in interfaces):
                return True
            time.sleep(2)
        return False

    def _get_interface_name(self, interface_mac):
        interfaces = netifaces.interfaces()

        for interface in interfaces:
            if netifaces.ifaddresses(interface)[AF_LINK][0][
                    'addr'] == interface_mac:
                return interface

    def configure(self, data):
        try:
            session.setup_config_session()
            ip_mac_map = {}
            provider_ip = data['provider_ip']
            provider_mac = data['provider_mac']
            provider_cidr = data['provider_cidr'].split('/')[1]
            provider_interface = self._get_interface_name(provider_mac)

            stitching_ip = data['stitching_ip']
            stitching_mac = data['stitching_mac']
            stitching_cidr = data['stitching_cidr'].split('/')[1]
            stitching_interface = self._get_interface_name(stitching_mac)

            if not self.check_if_interface_is_up(provider_interface,
                                                 stitching_interface):
                msg = ("Interfaces are not hotplugged even after waiting "
                       "for %s seconds." % self.hotplug_timeout)
                raise Exception(msg)

            interfaces = netifaces.interfaces()
            self.provider_ptg_interfaces = list()
            for interface in interfaces:
                physical_interface = netifaces.ifaddresses(
                    interface).get(AF_LINK)
                if not physical_interface:
                    continue
                mac_addr = netifaces.ifaddresses(
                    interface)[AF_LINK][0]['addr']
                if 'eth' in interface:
                    ip_mac_map.update({interface: mac_addr})

            for (interface, mac_addr) in ip_mac_map.iteritems():
                if provider_mac == mac_addr:
                    set_ip = COMMAND % (interface, provider_ip, provider_cidr)
                elif stitching_mac == mac_addr:
                    set_ip = COMMAND % (interface,
                                        stitching_ip, stitching_cidr)
                else:
                    continue
                result = self.set(set_ip.split())
                logger.debug("Result of add static ip is %s." % result)
            self.save()
        except Exception as err:
            msg = ("Failed to set static IP. Error: %s" % err)
            logger.error(msg)
            self.discard()
            raise Exception(err)

    def clear(self, data):
        try:
            session.setup_config_session()
            ip_mac_map = {}
            provider_ip = data['provider_ip']
            provider_mac = data['provider_mac']
            provider_cidr = data['provider_cidr'].split('/')[1]

            stitching_ip = data['stitching_ip']
            stitching_mac = data['stitching_mac']
            stitching_cidr = data['stitching_cidr'].split('/')[1]

            interfaces = netifaces.interfaces()
            self.provider_ptg_interfaces = list()
            for interface in interfaces:
                physical_interface = netifaces.ifaddresses(
                    interface).get(AF_LINK)
                if not physical_interface:
                    continue
                mac_addr = netifaces.ifaddresses(
                    interface)[AF_LINK][0]['addr']
                if 'eth' in interface:
                    ip_mac_map.update({interface: mac_addr})

            for (interface, mac_addr) in ip_mac_map.iteritems():
                if provider_mac == mac_addr:
                    del_ip = COMMAND % (interface, provider_ip, provider_cidr)
                elif stitching_mac == mac_addr:
                    del_ip = COMMAND % (interface,
                                        stitching_ip, stitching_cidr)
                else:
                    continue
                result = self.delete(del_ip.split())
                logger.debug("Result of delete static IP is %s." % result)
            self.save()
        except Exception as err:
            msg = ("Failed to delete static IP. Error: %s." % err)
            logger.error(msg)
            self.discard()
            raise Exception(msg)
