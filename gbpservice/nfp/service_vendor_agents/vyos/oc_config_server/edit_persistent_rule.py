from subprocess import call
import netifaces
import logging
from vyos_dhc import initiate_dhclient
from vyos_session import utils

logger = logging.getLogger(__name__)
utils.init_logger(logger)

INTERFACE_RULE_FILE = "/etc/udev/rules.d/70-persistent-cd.rules"
ADD_RULE = 'SUBSYSTEM=="net", DRIVERS=="?*", ATTR{address}=="%s", NAME="%s"'


class EditPersistentRule(object):

    def __init__(self):
        pass

    def add(self, mac_info):
        provider_rule, stitching_rule, interface_list = self.get_rule(mac_info)
        self.clean_stale_rules(interface_list)
        # line = ADD_RULE % (mac, interface)
        # initiate_dhclient()
        self.delete(mac_info)
        try:
            call("sudo chown vyos: "
                 "/etc/udev/rules.d/70-persistent-cd.rules".split()
                 )
            with open(INTERFACE_RULE_FILE, "a") as myfile:
                myfile.write(provider_rule + "\n")
                myfile.write(stitching_rule + "\n")
        except Exception as err:
            logger.error("Failed to add persistent rule for macs -%r " %
                         mac_info)
            raise Exception(err)
        finally:
            call("sudo chown root:root "
                 "/etc/udev/rules.d/70-persistent-cd.rules".split()
                 )

    def delete(self, mac_info):
        pro_cmd = 'sudo sed -i /%s/d %s' % (mac_info['provider_mac'],
                                            INTERFACE_RULE_FILE)
        stitch_cmd = 'sudo sed -i /%s/d %s' % (mac_info['stitching_mac'],
                                               INTERFACE_RULE_FILE)
        try:
            call(pro_cmd.split())
            call(stitch_cmd.split())
        except Exception as err:
            logger.error("Failed to delete persistent rule for macs -%r " %
                         mac_info)
            raise Exception(err)

    def get_rule(self, mac_info):
        interfaces = netifaces.interfaces()
        provider_rule = ''
        stitching_rule = ''
        interface_list = list()
        for interface in interfaces:
            physical_interface = netifaces.ifaddresses(interface).get(
                netifaces.AF_LINK)
            if not physical_interface:
                continue
            mac_addr = netifaces.ifaddresses(interface)[netifaces.AF_LINK][0][
                'addr']

            if mac_addr == mac_info['provider_mac']:
                interface_list.append(interface)
                provider_rule = ADD_RULE % (mac_addr, interface)
            elif mac_addr == mac_info['stitching_mac']:
                interface_list.append(interface)
                stitching_rule = ADD_RULE % (mac_addr, interface)

        return provider_rule, stitching_rule, interface_list

    def clean_stale_rules(self, interface_list):
        try:
            for interface in interface_list:
                cmd = 'sudo sed -i /%s/d %s' % (
                    interface, INTERFACE_RULE_FILE)
                call(cmd.split())
        except Exception, err:
            logger.error("ERROR deleting stale persistent rule. Interfaces: "
                         "%r . Details: %r" % (interface_list, str(err)))
