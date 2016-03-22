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

from oslo_log import log as logging

from gbpservice.nfp._i18n import _LE
from gbpservice.nfp.common import constants as nfp_constants
from gbpservice.nfp.common import exceptions
from gbpservice.nfp.orchestrator.openstack import (
    openstack_driver
)

LOG = logging.getLogger(__name__)


class OrchestrationDriverBase(object):
    """Generic Driver class for orchestration of virtual appliances

    Does not support sharing of virtual appliance for different chains
    Does not support hotplugging interface to devices
    Launches the VM with all the management and data ports and a new VM
    is launched for each Network Service Instance
    """
    def __init__(self, supports_device_sharing=False, supports_hotplug=False,
                 max_interfaces=5):
        self.service_vendor = 'general'
        self.supports_device_sharing = supports_device_sharing
        self.supports_hotplug = supports_hotplug
        self.maximum_interfaces = max_interfaces

        # TODO[Magesh]: Try to move the following handlers to
        # NDO manager rather than having here in the driver
        self.identity_handler = openstack_driver.KeystoneClient()
        self.compute_handler_nova = openstack_driver.NovaClient()
        self.network_handler_gbp = openstack_driver.GBPClient()
        self.network_handler_neutron = openstack_driver.NeutronClient()

        # statistics available
        # - instances
        # - management_interfaces
        # - keystone_token_get_failures
        # - image_details_get_failures
        # - port_details_get_failures
        # - instance_launch_failures
        # - instance_details_get_failures
        # - instance_delete_failures
        # - interface_plug_failures
        # - interface_unplug_failures
        self.stats = {}

    def _get_admin_tenant_id(self, token=None):
        try:
            (dummy,
             dummy,
             admin_tenant_name,
             dummy) = self.identity_handler.get_keystone_creds()
            if not token:
                token = self.identity_handler.get_admin_token()
            admin_tenant_id = self.identity_handler.get_tenant_id(
                                                            token,
                                                            admin_tenant_name)
            return admin_tenant_id
        except Exception:
            LOG.error(_LE("Failed to get admin's tenant ID"))
            raise

    def _increment_stats_counter(self, metric, by=1):
        # TODO: create path and delete path have different driver objects.
        # This will not work in case of increment and decrement.
        # So, its no-operation now
        return
        try:
            self.stats.update({metric: self.stats.get(metric, 0) + by})
        except Exception:
            LOG.error(_LE("Statistics failure. Failed to increment '%s' by %d"
                          % (metric, by)))

    def _decrement_stats_counter(self, metric, by=1):
        # TODO: create path and delete path have different driver objects.
        # This will not work in case of increment and decrement.
        # So, its no-operation now
        return
        try:
            self.stats.update({metric: self.stats[metric] - by})
        except Exception:
            LOG.error(_LE("Statistics failure. Failed to decrement '%s' by %d"
                          % (metric, by)))

    def _is_device_sharing_supported(self):
        return self.supports_device_sharing and self.supports_hotplug

    def _create_management_interface(self, device_data):
        try:
            token = (device_data['token']
                     if device_data.get('token')
                     else self.identity_handler.get_admin_token())
        except Exception:
            self._increment_stats_counter('keystone_token_get_failures')
            LOG.error(_LE('Failed to get token for management interface'
                          ' creation'))
            return None

        name = 'mgmt_interface'  # TODO[RPM]: Use proper name
        port_model = None
        if device_data['network_model'] == nfp_constants.GBP_NETWORK:
            mgmt_ptg_id = device_data['management_network_info']['id']
            mgmt_interface = self.network_handler_gbp.create_policy_target(
                                token,
                                self._get_admin_tenant_id(token=token),
                                mgmt_ptg_id,
                                name)
            port_model = nfp_constants.GBP_PORT
        else:
            mgmt_net_id = device_data['management_network_info']['id']
            mgmt_interface = self.network_handler_neutron.create_port(
                                token,
                                self._get_admin_tenant_id(token=token),
                                mgmt_net_id)
            port_model = nfp_constants.NEUTRON_PORT

        return {'id': mgmt_interface['id'],
                'port_model': port_model,
                'port_classification': nfp_constants.MANAGEMENT,
                'port_role': None}

    def _delete_management_interface(self, device_data, interface):
        try:
            token = (device_data['token']
                     if device_data.get('token')
                     else self.identity_handler.get_admin_token())
        except Exception:
            self._increment_stats_counter('keystone_token_get_failures')
            LOG.error(_LE('Failed to get token for management interface'
                          ' deletion'))
            return None

        if interface['port_model'] == nfp_constants.GBP_PORT:
            self.network_handler_gbp.delete_policy_target(token,
                                                          interface['id'])
        else:
            self.network_handler_neutron.delete_port(token, interface['id'])

    def _get_interfaces_for_device_create(self, device_data):
        mgmt_interface = self._create_management_interface(device_data)

        return [mgmt_interface]

    def _delete_interfaces(self, device_data, interfaces):
        for interface in interfaces:
            if interface['port_classification'] == nfp_constants.MANAGEMENT:
                self._delete_management_interface(device_data, interface)

    def _get_port_id(self, interface, token):
        if interface['port_model'] == nfp_constants.GBP_PORT:
            pt = self.network_handler_gbp.get_policy_target(
                                token,
                                interface['id'])
            return pt['port_id']
        else:
            return interface['id']

    def _get_port_details(self, token, port_id):
        port = self.network_handler_neutron.get_port(token, port_id)
        ip = port['port']['fixed_ips'][0]['ip_address']
        mac = port['port']['mac_address']
        subnet_id = port['port']['fixed_ips'][0]['subnet_id']
        subnet = self.network_handler_neutron.get_subnet(token, subnet_id)
        cidr = subnet['subnet']['cidr']
        gateway_ip = subnet['subnet']['gateway_ip']

        return (ip, mac, cidr, gateway_ip)

    def get_network_function_device_sharing_info(self, device_data):
        """ Get filters for NFD sharing

        :param device_data: NFD device
        :type device_data: dict

        :returns: None -- when device sharing is not supported
        :returns: dict -- It has the following scheme
        {
            'filters': {
                'key': 'value',
                ...
            }
        }

        :raises: exceptions.IncompleteData
        """
        if not self._is_device_sharing_supported():
            return None

        if any(key not in device_data
               for key in ['tenant_id',
                           'service_vendor']):
            raise exceptions.IncompleteData()

        return {
                'filters': {
                    'tenant_id': [device_data['tenant_id']],
                    'service_vendor': [device_data['service_vendor']],
                    'status': [nfp_constants.ACTIVE]
                }
        }

    def select_network_function_device(self, devices, device_data):
        """ Select a NFD which is eligible for sharing

        :param devices: NFDs
        :type devices: list
        :param device_data: NFD device
        :type device_data: dict

        :returns: None -- when device sharing is not supported, or
                          when no device is eligible for sharing
        :return: dict -- NFD device which is eligible for sharing

        :raises: exceptions.IncompleteData
        """
        if not self._is_device_sharing_supported():
            return None

        if (
            any(key not in device_data
                for key in ['ports']) or

            type(device_data['ports']) is not list or

            any(key not in port
                for port in device_data['ports']
                for key in ['id',
                            'port_classification',
                            'port_model']) or

            type(devices) is not list or

            any(key not in device
                for device in devices
                for key in ['interfaces_in_use'])
        ):
            raise exceptions.IncompleteData()

        hotplug_ports_count = 1  # for provider interface (default)
        if any(port['port_classification'] == nfp_constants.CONSUMER
               for port in device_data['ports']):
            hotplug_ports_count = 2

        for device in devices:
            if (
                (device['interfaces_in_use'] + hotplug_ports_count) <=
                self.maximum_interfaces
            ):
                return device
        return None

    def create_network_function_device(self, device_data):
        """ Create a NFD

        :param device_data: NFD device
        :type device_data: dict

        :returns: None -- when there is a failure in creating NFD
        :return: dict -- NFD device created

        :raises: exceptions.IncompleteData,
                 exceptions.ComputePolicyNotSupported
        """
        if (
            any(key not in device_data
                for key in ['tenant_id',
                            'service_vendor',
                            'compute_policy',
                            'network_model',
                            'management_network_info',
                            'ports']) or

            any(key not in device_data['management_network_info']
                for key in ['id']) or

            type(device_data['ports']) is not list or

            any(key not in port
                for port in device_data['ports']
                for key in ['id',
                            'port_classification',
                            'port_model'])
        ):
            raise exceptions.IncompleteData()

        if device_data['compute_policy'] != nfp_constants.NOVA_MODE:
            raise exceptions.ComputePolicyNotSupported(
                                compute_policy=device_data['compute_policy'])

        try:
            interfaces = self._get_interfaces_for_device_create(device_data)
        except Exception:
            LOG.exception(_LE('Failed to get interfaces for device creation'))
            return None
        else:
            self._increment_stats_counter('management_interfaces',
                                          by=len(interfaces))

        try:
            token = (device_data['token']
                     if device_data.get('token')
                     else self.identity_handler.get_admin_token())
        except Exception:
            self._increment_stats_counter('keystone_token_get_failures')
            LOG.error(_LE('Failed to get token, for device creation'))
            self._delete_interfaces(device_data, interfaces)
            self._decrement_stats_counter('management_interfaces',
                                          by=len(interfaces))
            return None

        image_name = '%s' % device_data['service_vendor'].lower()
        try:
            image_id = self.compute_handler_nova.get_image_id(
                    token,
                    self._get_admin_tenant_id(token=token),
                    image_name)
        except Exception:
            self._increment_stats_counter('image_details_get_failures')
            LOG.error(_LE('Failed to get image id for device creation.'
                          ' image name: %s'
                          % (image_name)))
            self._delete_interfaces(device_data, interfaces)
            self._decrement_stats_counter('management_interfaces',
                                          by=len(interfaces))
            return None

        flavor = 'm1.medium'
        interfaces_to_attach = []
        try:
            for interface in interfaces:
                port_id = self._get_port_id(interface, token)
                interfaces_to_attach.append({'port': port_id})

            if not self.supports_hotplug:
                for port in device_data['ports']:
                    if port['port_classification'] == nfp_constants.PROVIDER:
                        port_id = self._get_port_id(port, token)
                        interfaces_to_attach.append({'port': port_id})
                for port in device_data['ports']:
                    if port['port_classification'] == nfp_constants.CONSUMER:
                        port_id = self._get_port_id(port, token)
                        interfaces_to_attach.append({'port': port_id})
        except Exception:
            self._increment_stats_counter('port_details_get_failures')
            LOG.error(_LE('Failed to fetch list of interfaces to attach'
                          ' for device creation'))
            self._delete_interfaces(device_data, interfaces)
            self._decrement_stats_counter('management_interfaces',
                                          by=len(interfaces))
            return None

        instance_name = 'instance'  # TODO[RPM]:use proper name
        try:
            instance_id = self.compute_handler_nova.create_instance(
                    token, self._get_admin_tenant_id(token=token),
                    image_id, flavor,
                    interfaces_to_attach, instance_name)
        except Exception:
            self._increment_stats_counter('instance_launch_failures')
            LOG.error(_LE('Failed to create %s instance'
                          % (device_data['compute_policy'])))
            self._delete_interfaces(device_data, interfaces)
            self._decrement_stats_counter('management_interfaces',
                                          by=len(interfaces))
            return None
        else:
            self._increment_stats_counter('instances')

        mgmt_ip_address = None
        try:
            for interface in interfaces:
                if interface['port_classification'] == (
                                                    nfp_constants.MANAGEMENT):
                    port_id = self._get_port_id(interface, token)
                    port = self.network_handler_neutron.get_port(token,
                                                                 port_id)
                    mgmt_ip_address = port['port']['fixed_ips'][0][
                                                                'ip_address']
        except Exception:
            self._increment_stats_counter('port_details_get_failures')
            LOG.error(_LE('Failed to get management port details'))
            try:
                self.compute_handler_nova.delete_instance(
                                            token,
                                            self._get_admin_tenant_id(
                                                                token=token),
                                            device_data['id'])
            except Exception:
                self._increment_stats_counter('instance_delete_failures')
                LOG.error(_LE('Failed to delete %s instance'
                              % (device_data['compute_policy'])))
            self._decrement_stats_counter('instances')
            self._delete_interfaces(device_data, interfaces)
            self._decrement_stats_counter('management_interfaces',
                                          by=len(interfaces))
            return None

        return {'id': instance_id,
                'name': instance_name,
                'mgmt_ip_address': mgmt_ip_address,
                'mgmt_port_id': interfaces[0],
                'max_interfaces': self.maximum_interfaces,
                'interfaces_in_use': len(interfaces_to_attach),
                'description': ''}  # TODO[RPM]: what should be the description

    def delete_network_function_device(self, device_data):
        """ Delete the NFD

        :param device_data: NFD device
        :type device_data: dict

        :returns: None -- Both on success and Failure

        :raises: exceptions.IncompleteData,
                 exceptions.ComputePolicyNotSupported
        """
        if (
            any(key not in device_data
                for key in ['id',
                            'tenant_id',
                            'compute_policy',
                            'mgmt_port_id']) or

            type(device_data['mgmt_port_id']) is not dict or

            any(key not in device_data['mgmt_port_id']
                for key in ['id',
                            'port_classification',
                            'port_model'])
        ):
            raise exceptions.IncompleteData()

        if device_data['compute_policy'] != nfp_constants.NOVA_MODE:
            raise exceptions.ComputePolicyNotSupported(
                                compute_policy=device_data['compute_policy'])

        try:
            token = (device_data['token']
                     if device_data.get('token')
                     else self.identity_handler.get_admin_token())
        except Exception:
            self._increment_stats_counter('keystone_token_get_failures')
            LOG.error(_LE('Failed to get token for device deletion'))
            return None

        try:
            self.compute_handler_nova.delete_instance(
                                            token,
                                            self._get_admin_tenant_id(
                                                                token=token),
                                            device_data['id'])
        except Exception:
            self._increment_stats_counter('instance_delete_failures')
            LOG.error(_LE('Failed to delete %s instance'
                          % (device_data['compute_policy'])))
        else:
            self._decrement_stats_counter('instances')

        try:
            self._delete_interfaces(device_data,
                                    [device_data['mgmt_port_id']])
        except Exception:
            LOG.error(_LE('Failed to delete the management data port(s)'))
        else:
            self._decrement_stats_counter('management_interfaces')

    def get_network_function_device_status(self, device_data):
        """ Get the status of NFD

        :param device_data: NFD device
        :type device_data: dict

        :returns: None -- On failure
        :return: str -- status string

        :raises: exceptions.IncompleteData,
                 exceptions.ComputePolicyNotSupported
        """
        if any(key not in device_data
               for key in ['id',
                           'tenant_id',
                           'compute_policy']):
            raise exceptions.IncompleteData()

        if device_data['compute_policy'] != nfp_constants.NOVA_MODE:
            raise exceptions.ComputePolicyNotSupported(
                                compute_policy=device_data['compute_policy'])

        try:
            token = (device_data['token']
                     if device_data.get('token')
                     else self.identity_handler.get_admin_token())
        except Exception:
            self._increment_stats_counter('keystone_token_get_failures')
            LOG.error(_LE('Failed to get token for get device status'
                          ' operation'))
            return None

        try:
            device = self.compute_handler_nova.get_instance(
                            token,
                            self._get_admin_tenant_id(token=token),
                            device_data['id'])
        except Exception:
            self._increment_stats_counter('instance_details_get_failures')
            LOG.error(_LE('Failed to get %s instance details'
                          % (device_data['compute_policy'])))
            return None  # TODO[RPM]: should we raise an Exception here?

        return device['status']

    def plug_network_function_device_interfaces(self, device_data):
        """ Attach the network interfaces for NFD

        :param device_data: NFD device
        :type device_data: dict

        :returns: bool -- False on failure and True on Success

        :raises: exceptions.IncompleteData,
                 exceptions.ComputePolicyNotSupported,
                 exceptions.HotplugNotSupported
        """
        if not self.supports_hotplug:
            raise exceptions.HotplugNotSupported(vendor=self.service_vendor)

        if (
            any(key not in device_data
                for key in ['id',
                            'tenant_id',
                            'compute_policy',
                            'ports']) or

            type(device_data['ports']) is not list or

            any(key not in port
                for port in device_data['ports']
                for key in ['id',
                            'port_classification',
                            'port_model'])
        ):
            raise exceptions.IncompleteData()

        if device_data['compute_policy'] != nfp_constants.NOVA_MODE:
            raise exceptions.ComputePolicyNotSupported(
                                compute_policy=device_data['compute_policy'])

        try:
            token = (device_data['token']
                     if device_data.get('token')
                     else self.identity_handler.get_admin_token())
        except Exception:
            self._increment_stats_counter('keystone_token_get_failures')
            LOG.error(_LE('Failed to get token for plug interface to device'
                          ' operation'))
            return False  # TODO[RPM]: should we raise an Exception here?

        try:
            for port in device_data['ports']:
                if port['port_classification'] == nfp_constants.PROVIDER:
                    port_id = self._get_port_id(port, token)
                    self.network_handler_neutron.update_port(
                                token, port_id,
                                security_groups=[],
                                port_security_enabled=False)
                    self.compute_handler_nova.attach_interface(
                                token,
                                self._get_admin_tenant_id(token=token),
                                device_data['id'],
                                port_id)
                    break
            for port in device_data['ports']:
                if port['port_classification'] == nfp_constants.CONSUMER:
                    port_id = self._get_port_id(port, token)
                    self.network_handler_neutron.update_port(
                                token, port_id,
                                security_groups=[],
                                port_security_enabled=False)
                    self.compute_handler_nova.attach_interface(
                                token,
                                self._get_admin_tenant_id(token=token),
                                device_data['id'],
                                port_id)
                    break
        except Exception:
            self._increment_stats_counter('interface_plug_failures')
            LOG.error(_LE('Failed to plug interface(s) to the device'))
            return False  # TODO[RPM]: should we raise an Exception here?
        else:
            return True

    def unplug_network_function_device_interfaces(self, device_data):
        """ Detach the network interfaces for NFD

        :param device_data: NFD device
        :type device_data: dict

        :returns: bool -- False on failure and True on Success

        :raises: exceptions.IncompleteData,
                 exceptions.ComputePolicyNotSupported,
                 exceptions.HotplugNotSupported
        """
        if not self.supports_hotplug:
            raise exceptions.HotplugNotSupported(vendor=self.service_vendor)

        if (
            any(key not in device_data
                for key in ['id',
                            'tenant_id',
                            'compute_policy',
                            'ports']) or

            any(key not in port
                for port in device_data['ports']
                for key in ['id',
                            'port_classification',
                            'port_model'])
        ):
            raise exceptions.IncompleteData()

        if device_data['compute_policy'] != nfp_constants.NOVA_MODE:
            raise exceptions.ComputePolicyNotSupported(
                                compute_policy=device_data['compute_policy'])

        try:
            token = (device_data['token']
                     if device_data.get('token')
                     else self.identity_handler.get_admin_token())
        except Exception:
            self._increment_stats_counter('keystone_token_get_failures')
            LOG.error(_LE('Failed to get token for unplug interface from'
                          ' device operation'))
            return False  # TODO[RPM]: should we raise an Exception here?

        try:
            for port in device_data['ports']:
                port_id = self._get_port_id(port, token)
                self.compute_handler_nova.detach_interface(
                            token,
                            self._get_admin_tenant_id(token=token),
                            device_data['id'],
                            port_id)
        except Exception:
            self._increment_stats_counter('interface_unplug_failures')
            LOG.error(_LE('Failed to unplug interface(s) from the device'))
            return False  # TODO[RPM]: should we raise an Exception here?
        else:
            return True

    def get_network_function_device_healthcheck_info(self, device_data):
        """ Get the health check information for NFD

        :param device_data: NFD device
        :type device_data: dict

        :returns: dict -- It has the following scheme
        {
            'info': {
                'version': <int>
            },
            'config': [
                {
                    'resource': 'healthmonitor',
                    'kwargs': {
                        'service_type': <str>,
                        ...
                    }
                }
            ]
        }

        :raises: exceptions.IncompleteData
        """
        if any(key not in device_data
               for key in ['id',
                           'mgmt_ip_address',
                           'service_type']):
            raise exceptions.IncompleteData()

        return {
            'info': {
                'version': 1
            },
            'config': [
                {
                    'resource': 'healthmonitor',
                    'kwargs': {
                        'vmid': device_data['id'],
                        'mgmt_ip': device_data['mgmt_ip_address'],
                        'periodicity': 'initial',
                        'service_type': device_data['service_type'].lower()
                    }
                }
            ]
        }

    def get_network_function_device_config_info(self, device_data):
        """ Get the configuration information for NFD

        Child class should implement this
        """
        pass
