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
import json
import logging
import time

import fw_constants
import netifaces
from execformat.executor import session
from netifaces import AF_LINK
from operations import configOpts
from vyos_session import utils

FWN = 'firewall name'
rule = 'rule'
firewall_rules = {
    'protocol': '%s protocol %s',
    'source_ip_address': '%s source address %s',
    'destination_ip_address': '%s destination address %s',
    'source_port': '%s source port %s',
    'destination_port': '%s destination port %s'
}

firewall_action = {'allow': 'accept', 'deny': 'drop'}

logger = logging.getLogger(__name__)
utils.init_logger(logger)


class VyosFWConfigClass(configOpts):

    def __init__(self):
        super(VyosFWConfigClass, self).__init__()
        self.fw_identifier = 'fw'
        self.provider_ptg_interfaces = list()
        self.rules = list()

    def set_up_rule_on_interfaces(self, firewall):
        """
        firewall = {'status': u'PENDING_CREATE', 'name': u'', 'shared': None,
         'firewall_policy_id': u'eeb15ef4-ba80-43ca-8f9c-27fa0f48db20',
        'tenant_id': u'a3d0d8dba0834e1fbff229f5e2b2e440',
        'admin_state_up': True, 'id': u'e9b5ca2f-a721-41b9-be9b-7a6189ddbec5'
        , 'firewall_rule_list': [{'protocol': u'tcp', 'description': u'',
        'source_port': None, 'source_ip_address': None,
        'destination_ip_address': None,
        'firewall_policy_id': u'eeb15ef4-ba80-43ca-8f9c-27fa0f48db20',
         'position': 1L, 'destination_port': '80',
        'id': u'b98296cb-335a-4314-83f9-aa5654f296fa', 'name': u'',
        'tenant_id': u'a3d0d8dba0834e1fbff229f5e2b2e440', 'enabled': True,
        'action': u'allow', 'ip_version': 4L, 'shared': False}],
        'description': u''}

        :param firewall: Firewall object
        """
        sorted_rule_list, self.provider_ptg_interfaces = list(), list()

        firewall = json.loads(firewall)
        fw_rule_list = firewall['firewall_rule_list']
        logger.info("Initiating firewall - %s build. of Tenant: %s" % (
            firewall['id'], firewall['tenant_id']))
        sorted_rule_list = self.sort_rule_list(fw_rule_list, firewall['id'])
        try:
            self.set_provider_interface(firewall)
        except Exception as e:
            msg = ("Firewall - %s configuration failed. Tenant : %s Error "
                   "retrieving PTG's interface %r" %
                   (firewall['id'], firewall['tenant_id'], str(e)))
            logger.error(msg)
            raise Exception(msg, 400, dict(config_success=False))
        else:
            if not self.provider_ptg_interfaces:
                msg = ("No interface was found to configure firewall - %s . "
                       "Tenant: %s" %
                       (firewall['id'], firewall['tenant_id']))
                logger.error(msg)
                raise Exception(msg, 400, dict(config_success=False))

        session.setup_config_session()
        # FIXME (VK): This will log error also when there is no firewall
        # before on the interface. Need to evaluate side effect of this method.
        try:
            self._ensure_clean_interface()
        except:
            pass
        self.rules = list()
        self.add_common_rule()
        try:
            for fw_rule in sorted_rule_list:
                self.create_vyos_fw_rule(fw_rule)
            self.configure_interfaces()
            for _rule in self.rules:
                self.set(_rule.split())
            session.commit()
        except Exception as e:
            msg = ("Firewall - %s configuration failed. Error: %s " %
                   (firewall['id'], str(e)))
            logger.error(msg)
            session.discard()
            session.teardown_config_session()
            raise Exception(msg, 400, dict(config_success=False))
        else:
            msg = "Firewall - %s rules created successfully on %r" % (
                firewall['id'], self.provider_ptg_interfaces)
            logger.info(msg)
            return {'status': 200, 'config_success': True, 'message': msg}
        finally:
            session.save()
            time.sleep(4)
            session.teardown_config_session()

    def add_common_rule(self):
        self.fw_identifier = ('fw' + '_' +
                                 self.provider_ptg_interfaces[0])
        default_action = (FWN + ' ' + self.fw_identifier +
                          ' default-action drop'
                          )
        common_fw_rule_prefix = (FWN + ' ' + self.fw_identifier + ' ' +
                                 rule + ' 10')
        accept_action = (common_fw_rule_prefix + ' action accept')
        established_action = (common_fw_rule_prefix +
                              ' state established enable')
        related_action = (common_fw_rule_prefix +
                          ' state related enable')
        self.rules += [default_action, accept_action, established_action,
                       related_action]

    def create_vyos_fw_rule(self, fw_rule):
        if not fw_rule.get('enabled'):
            return

        position = str(int(fw_rule.get('position', '100')) + 10)
        if position < 1:
            position *= 10
        common_fw_rule_prefix = (FWN + ' ' + self.fw_identifier + ' ' +
                                 rule + ' ' + position)
        self.rules.append(common_fw_rule_prefix)
        self.rules.append(''.join([common_fw_rule_prefix, ' action %s' %
                                   firewall_action[fw_rule['action'.lower()]]])
                          )
        try:
            self.rules.extend(
                [firewall_rules[k] %
                 (common_fw_rule_prefix, fw_rule[k]
                  if k not in ['source_port', 'destination_port']
                  else fw_rule[k].replace(':', '-'))
                 for k, v in fw_rule.iteritems()
                 if fw_rule[k] and k in firewall_rules]
            )

        except Exception as err:
            logger.error("Firewall rule retrieval failed . Error - %s" %
                         str(err))
            raise Exception(err)

    def configure_interfaces(self):
        if fw_constants.intercloud:
            # TODO(Vikash) Its not always the bridge will have same name every
            #  time. Its only for intercloud
            interface_conf = ("interfaces bridge br0 firewall in name " +
                              self.fw_identifier)
            self.rules += [interface_conf]
        else:
            # It would be always 1 for now.
            for interface in self.provider_ptg_interfaces:
                if interface.lower() == 'lo':
                    continue
                interface_conf = ('interfaces ethernet ' + interface + ' ' +
                                  'firewall out name ' + self.fw_identifier)
                self.rules += [interface_conf]

    def reset_firewall(self, firewall):
        fw_data = json.loads(firewall)
        try:
            self.set_provider_interface(fw_data)
        except Exception as err:
            msg = ("Firewall %s reset failed. Error retrieving PTG's "
                   "interface- %r" % (fw_data['id'], str(err)))
            logger.error(msg)
            raise Exception(msg, 400, dict(delete_success=False))
        else:
            if not self.provider_ptg_interfaces:
                msg = ("No interface was found for - %r " % fw_data[
                    'id'])
                logger.error(msg)
                raise Exception(msg, 400, dict(delete_success=False,
                                               message="INTERFACE NOT FOUND"))

        session.setup_config_session()

        if fw_constants.intercloud:
            bridge_rule = ("interfaces bridge br0 firewall in name " +
                           self.fw_identifier)
            try:
                self.delete(bridge_rule.split())
            except Exception as err:
                msg = (" Rule deletion on bridge failed - %s " % str(
                    err))
                logger.error(msg)
                raise Exception(msg, 400, dict(delete_success=False))
        else:
            del_interface_rule = (
                'interfaces ethernet ' + self.provider_ptg_interfaces[0] +
                ' ' + 'firewall')
            try:
                self.delete(del_interface_rule.split())
            except Exception as err:
                session.discard()
                session.teardown_config_session()
                msg = ("Rule deletion on interface %s failed. ERROR: %s " %
                       (self.provider_ptg_interfaces[0], str(err)))
                logger.error(msg)
                raise Exception(msg, 400, dict(delete_success=False))
        try:
            session.commit()
        except Exception as err:
            session.discard()
            session.teardown_config_session()
            msg = ("Rule deletion commit operation failed for firewall - %s. "
                   "Error - %s" % (fw_data['id'], str(err)))
            logger.error(msg)
            raise Exception(msg, 400, dict(delete_success=False))

        # sleep for 2 sec. Got removed in last merge.
        time.sleep(2)
        self.fw_identifier = ('fw' + '_' +
                                 self.provider_ptg_interfaces[0])
        del_firewall = FWN + ' ' + self.fw_identifier
        try:
            self.delete(del_firewall.split())
        except Exception as err:
            session.discard()
            session.teardown_config_session()
            msg = ("Firewall - %s deletion failed on interface: %r .ERROR %s"
                   % (fw_data['id'], self.provider_ptg_interfaces[0],
                      str(err)))
            logger.error(msg)
            raise Exception(msg, 400, dict(delete_success=False))
        else:
            try:
                session.commit()
            except Exception as err:
                session.discard()
                session.teardown_config_session()
                msg = ("Session commit failed for firewall deletion : %s. "
                       "Error - %r " %
                       (fw_data['id'], str(err)))
                logger.error(msg)
                raise Exception(msg, 400, dict(delete_success=False))
            else:
                logger.info("Firewall -%r deleted succesfully" % fw_data[
                    'id'])

        session.save()
        # Can be removed if we don't see any issue.
        time.sleep(1)
        session.teardown_config_session()

        return {'status': 200, 'message': 'Firewall - %s deleted '
                                          'succesfully' % fw_data['id'],
                'delete_success': True}

    def sort_rule_list(self, fw_rule_list, fw_id):
        fw_rule_list_len = len(fw_rule_list)
        rule_list = [-1] * fw_rule_list_len
        for rule in fw_rule_list:
            ind = rule['position'] - 1
            rule_list[ind] = rule

        if -1 in rule_list:
            # raise Exception("Something went wrong")
            rule_list = list()
            logger.warn("Adding only DROP rule as not received any rules for "
                        "firewall %s" % fw_id)
        return rule_list

    def set_provider_interface(self, firewall):
        description = ast.literal_eval(firewall["description"])
        if not description.get('provider_ptg_info'):
            raise
        provider_ptg_info = description["provider_ptg_info"]
        # consumer_ptg_ips = description.get('consumer_ptg_ips', [])
        interfaces = netifaces.interfaces()
        self.provider_ptg_interfaces = list()
        for interface in interfaces:
            # IPV4 support only
            # (Fixme) what in the case of aliasing?
            # TODO (Vikash) Not reqd for L2 , need to revisit for L3
            # vpn tunnel interface for ssl vpn does not have a mac address
            physical_interface = netifaces.ifaddresses(interface).get(AF_LINK)
            if not physical_interface:
                continue
            mac_addr = netifaces.ifaddresses(interface)[AF_LINK][0]['addr']

            if mac_addr in provider_ptg_info:
                self.provider_ptg_interfaces.append(interface)

    def get_out_and_in_rule(self, fw_rule_list):
        in_rule_list = out_rule_list = list()

        for rule in fw_rule_list:
            if rule['direction'] == 'in':
                in_rule_list.append(rule)
            elif rule['direction'] == 'out':
                out_rule_list.append(rule)
            else:
                raise Exception("Not valid direction")

        return in_rule_list, out_rule_list

    def _ensure_clean_interface(self):
        del_interface_rule = (
            'interfaces ethernet ' + self.provider_ptg_interfaces[0] +
            ' ' + 'firewall')
        self.fw_identifier = ('fw' + '_' +
                                 self.provider_ptg_interfaces[0])
        del_firewall = FWN + ' ' + self.fw_identifier
        try:
            self.delete(del_interface_rule.split())
            # delete firewall
            self.delete(del_firewall.split())
        except Exception as err:
            logger.info("Stale firewall rule deletion on interface %s failed. "
                        "This method is called with every firewall create to "
                        "avoid previous stale firewall rule. This message can "
                        "be ignored." % self.provider_ptg_interfaces[0])
            raise Exception(err)

    def run_sshd_on_mgmt_ip(self, mgmt_ip):
        command = "service ssh listen-address %s" % mgmt_ip
        session.setup_config_session()
        self.set(command.split())
        try:
            session.commit()
        except:
            logger.error("Failed to update sshd listen-address to %s" %
                         mgmt_ip)
            session.discard()
            session.teardown_config_session()
            return
        session.save()
        session.teardown_config_session()
