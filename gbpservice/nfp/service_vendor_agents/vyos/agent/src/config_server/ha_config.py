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
import logging
import time

import netifaces
from execformat.executor import session
from netifaces import AF_INET, AF_LINK
from operations import configOpts
from vyos_session import utils

logger = logging.getLogger(__name__)
utils.init_logger(logger)


class VYOSHAConfig(configOpts):
    """
    Class to configure HA for VYOS.
    """

    def __init__(self):
        super(VYOSHAConfig, self).__init__()

    def configure_conntrack_sync(self, ha_config):
        """
        :param ha_config:
        :return:
        """
        ha_config = json.loads(ha_config)
        monitoring_info, data_info = self.get_conntrack_request_data(
            ha_config)
        event_queue_size = monitoring_info["event_queue_size"]
        cluster_name = monitoring_info["cluster_name"]
        mcast_group = monitoring_info["mcast_group"]
        sync_queue_size = monitoring_info["sync_queue_size"]
        monitoring_mac = monitoring_info["monitoring_mac"]

        monitoring_interface, monitoring_ip = self._get_interface_name(
            dict(monitoring_mac=monitoring_mac),
            interface_type='monitoring')

        if not monitoring_interface:
            logger.error("Failed to configure conntrack for CLUSTER- %r" %
                         cluster_name)
            raise Exception("Conntrack sync configuration failed. Reason - "
                            "No monitoring interface information found.",
                            400, dict(ha_config=ha_config))

        conntrack_commands = self._set_conntrack(
            cluster_name, event_queue_size, mcast_group,
            monitoring_interface, sync_queue_size)
        interface_vrrp_commands = self.set_vrrp_for_interface(data_info)

        all_commands = conntrack_commands + interface_vrrp_commands

        self._execute_commands(all_commands, ha_config['tenant_id'])
        logger.debug("VRRP configured succesfully - %r " % all_commands)
        return {'status': 200, 'message': 'VRRP configured succesfully'}

    def set_interface_ha(self, interface_config):
        ha_config = json.loads(interface_config)
        try:
            cluster_name = ha_config["cluster_name"]
            vrrp_group = ha_config["vrrp_group"]
            data_macs = ha_config["data_macs"]
            preempt_delay = ha_config["preempt_delay"]
            priority = ha_config["priority"]
            vip = ha_config["vip"]
            tenant_id = ha_config["tenant_id"]
            advertised_interval = ha_config["advertised_interval"]
        except KeyError as err:
            raise Exception("HA configuration for interface failed. Value "
                            "not found. %r" % str(err),
                            400, dict(interface_config=ha_config))
        interface_info = dict(vrrp_group=vrrp_group, data_macs=data_macs,
                              vip=vip, preempt_delay=preempt_delay,
                              priority=priority, cluster_name=cluster_name,
                              advertised_interval=advertised_interval,
                              tenant_id=tenant_id)

        interface_vrrp_commands = self.set_vrrp_for_interface(interface_info)

        self._execute_commands(interface_vrrp_commands, interface_info[
            'tenant_id'])
        logger.debug("VRRP succesfully configured for interfaces.")
        return {'status': 200, 'message': 'VRRP succesfully configured for '
                                          'interfaces'}

    def delete_vrrp(self, vrrp_config):
        """
        :param self:
        :param vrrp_config:
        :return:
        This method makes an assumption that detach of an interface will
        finally clean the vrrp entry. That's why doesn't raise any
        exception, as was observed that even though it succeeds but raises an
        exception. Investigation will continue. Also this methods doesn't
        clean conntrack explicitly, instead it goes with VM delete.
        Exception code will be incorporated once the exception established
        case.
        """
        vrrp_config = json.loads(vrrp_config)
        data_macs = vrrp_config["data_macs"]

        data_interface, data_ip = self._get_interface_name(
            dict(data_mac=data_macs['provider_mac']), interface_type='data')

        provider_vrrp_delete = "interfaces ethernet %s vrrp" % data_interface

        data_interface, data_ip = self._get_interface_name(
            dict(data_mac=data_macs['stitching_mac']), interface_type='data')
        stitching_vrrp_delete = "interfaces ethernet %s vrrp" % data_interface

        session.setup_config_session()

        try:
            self.delete(provider_vrrp_delete.split())
        except Exception as err:
            logger.error("Error deleting provider vrrp %r " % err)

        try:
            self.delete(stitching_vrrp_delete.split())
        except Exception as err:
            logger.error("Error deleting stitching vrrp %r " % err)


        session.commit()
        time.sleep(5)
        session.save()
        session.teardown_config_session()
        logger.debug("VRRP succesfully deleted for interfaces")
        return {'status': 200, 'message': 'VRRP succesfully deleted for '
                                          'interfaces'}

    def set_vrrp_for_interface(self, data_info):
        interface_commands = list()
        direct_call = False
        if isinstance(data_info, str):
            direct_call = True
            data_info = json.loads(data_info)
        data_macs = data_info.get("data_macs", {})
        vips = data_info.get("vip", {})
        vrrp_groups = data_info["vrrp_group"]

        for mac_type, mac in data_macs.iteritems():
            data_mac = dict(data_mac=str(mac))
            vip_type = mac_type.split("_")[0] + "_vip"
            vip_ip = vips.get(vip_type)
            if mac_type == "provider_mac":
                vrrp_group = vrrp_groups["provider_vrrp_group"]
            if mac_type == "stitching_mac":
                vrrp_group = vrrp_groups["stitching_vrrp_group"]

            interface_name, ip = self._get_interface_name(
                data_mac, interface_type='data')

            if not interface_name:
                logger.error("Failed to configure VRRP, as unable to get "
                             "interface name.")
                raise Exception('VRRP config failed.Failed to get interface'
                                ' name to configure vrrp', 400,
                                dict(data_info=data_info))

            common_command = "interfaces ethernet %s vrrp vrrp-group %s " % (
                interface_name, vrrp_group)

            interface_address_set = "interfaces ethernet %s address %s " % (
                interface_name, ip)

            advt_interval_set = common_command + "advertise-interval %s " % (
                data_info["advertised_interval"])

            preempt_set = common_command + "preempt true"
            preempt_delay_set = common_command + "preempt-delay %s" % \
                                                 data_info["preempt_delay"]
            priority_set = common_command + "priority %s" % data_info[
                "priority"]
            rfc_set = common_command + "rfc3768-compatibility"
            sync_group_set = common_command + "sync-group %s " % data_info[
                "cluster_name"]
            virtual_address_set = common_command + "virtual-address %s" % \
                                                   vip_ip

            interface_commands += [interface_address_set, advt_interval_set,
                                   preempt_set, preempt_delay_set,
                                   priority_set, rfc_set, sync_group_set,
                                   virtual_address_set]

        logger.debug("Interface commands - %r ", interface_commands)
        if not direct_call:
            return interface_commands
        else:
            self._execute_commands(interface_commands, data_info.get(
                'tenant_id'))
            return dict(message='Interface configured succesfully')

    @staticmethod
    def _set_conntrack(cluster_name, event_queue_size, mcast_group,
                       monitoring_interface, sync_queue_size):
        peer_link_set = "interfaces ethernet %s description PEER-LINK" % \
                        monitoring_interface
        event_queue_set = "service conntrack-sync event-listen-queue-size " \
                          "%s" % str(event_queue_size)
        cluster_set = "service conntrack-sync failover-mechanism vrrp " \
                      "sync-group " + cluster_name
        interface_set = "service conntrack-sync interface %s" % \
                        monitoring_interface
        mcast_set = "service conntrack-sync mcast-group %s " % mcast_group
        sync_queue_set = "service conntrack-sync sync-queue-size %s " % \
                         str(sync_queue_size)
        commands = [peer_link_set, event_queue_set, cluster_set,
                    interface_set, mcast_set, sync_queue_set]

        logger.debug("Conntrack commands - %r " % commands)
        return commands

    @staticmethod
    def _get_interface_name(ha_config, interface_type=None):
        """
        :param ha_config:
        :param interface_type:
        :return:
        """
        interfaces = netifaces.interfaces()
        for interface in interfaces:
            physical_interface = netifaces.ifaddresses(interface).get(AF_LINK)
            if not physical_interface:
                continue
            if AF_INET not in netifaces.ifaddresses(interface).keys():
                continue
            mac_addr = netifaces.ifaddresses(interface)[AF_LINK][0]['addr']
            ip_addr = netifaces.ifaddresses(interface)[AF_INET][0]['addr']
            netmask = netifaces.ifaddresses(interface)[AF_INET][0]['netmask']
            if mac_addr == ha_config.get('monitoring_mac', None) and \
                    interface_type.lower() == 'monitoring':
                return interface, ip_addr
            elif (mac_addr == ha_config.get('data_mac', None) and
                  interface_type.lower() == 'data'):
                mlen = sum([bin(int(x)).count('1') for x in
                            netmask.split('.')])
                ip_addr += ("/" + str(mlen))
                return interface, ip_addr

        logger.error("interface name none, ha_config: %s" % ha_config)
        return None, None

    def get_conntrack_request_data(self, ha_config):
        try:
            monitoring_mac = ha_config["monitoring_mac"]
            queue_size = ha_config.get("queue_size", 8)
            cluster_name = ha_config["cluster_name"]
            mcast_group = ha_config["mcast_group"]
            sync_queue_size = ha_config.get("sync_queue_size", 1)
            vrrp_group = ha_config["vrrp_group"]
            data_macs = ha_config["data_macs"]
            preempt_delay = ha_config["preempt_delay"]
            priority = ha_config["priority"]
            vip = ha_config["vip"]
            advertised_interval = ha_config["advertised_interval"]
        except KeyError as err:
            raise Exception("Parameters missing for conntrack configuration "
                            "%r" % str(err), 400, {"ha_config": ha_config})

        monitoring_info = dict(monitoring_mac=monitoring_mac,
                               event_queue_size=queue_size,
                               cluster_name=cluster_name,
                               mcast_group=mcast_group,
                               sync_queue_size=sync_queue_size)

        data_info = dict(vrrp_group=vrrp_group, data_macs=data_macs,
                         vip=vip, preempt_delay=preempt_delay,
                         priority=priority, cluster_name=cluster_name,
                         advertised_interval=advertised_interval)

        return monitoring_info, data_info

    def get_interface_data(self, interface_config):
        try:
            data_macs = interface_config["data_macs"]
            advertised_interval = interface_config["advertised_interval"]
            vrrp_group = interface_config["vrrp_group"]
            preempt_delay = interface_config["preempt_delay"]
            priority = interface_config["priority"]
            vip = interface_config["vip"]
        except KeyError:
            pass

        data_info = dict(data_macs=data_macs,
                         advertised_interval=advertised_interval,
                         vrrp_group=vrrp_group, preempt_delay=preempt_delay,
                         priority=priority, vip=vip)

        return data_info

    def _execute_commands(self, all_commands, tenant_id=None):
        session.setup_config_session()
        for command in all_commands:
            try:
                self.set(command.split())
            except:
                logger.error("Failed to configure HA. Tenant - %r" % tenant_id)
                session.teardown_config_session()
                raise Exception("Failed to configure HA for tenant %s" %
                                tenant_id, 400, {"commands": all_commands,
                                                 "failed_command": command})
        try:
            session.commit()
        except:
            logger.error("Failed to commit HA configuration. Tenant - %r"
                         % tenant_id)
            session.discard()
            time.sleep(2)
            session.teardown_config_session()
            raise Exception("Failed to configure HA for tenant %s" % tenant_id,
                            400, {"commands": all_commands,
                                  "failed_command": command})
        time.sleep(5)
        session.save()
        time.sleep(5)
        session.teardown_config_session()
