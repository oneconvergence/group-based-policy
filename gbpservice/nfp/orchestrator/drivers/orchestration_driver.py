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

from neutron._i18n import _LE
from neutron._i18n import _LI

from gbpservice.nfp.common import constants as nfp_constants
from gbpservice.nfp.common import exceptions
from gbpservice.nfp.orchestrator.coal.networking import (
    nfp_gbp_network_driver
)
from gbpservice.nfp.orchestrator.coal.networking import (
    nfp_neutron_network_driver
)
from gbpservice.nfp.orchestrator.openstack import openstack_driver

import ast
import operator

from gbpservice.nfp.core import log as nfp_logging
LOG = nfp_logging.getLogger(__name__)


PROXY_PORT_PREFIX = "opflex_proxy:"
ADVANCE_SHARING_PTG_NAME = "Advance_Sharing_PTG"


def _set_network_handler(f):
    def wrapped(self, *args, **kwargs):
        device_data = args[0]
        if device_data.get('service_details'):
            network_mode = device_data['service_details'].get('network_mode')
            if network_mode:
                kwargs['network_handler'] = self.network_handlers[network_mode]
        return f(self, *args, **kwargs)
    return wrapped


class OrchestrationDriver(object):
    """Generic Driver class for orchestration of virtual appliances

    Launches the VM with all the management and data ports and a new VM
    is launched for each Network Service Instance
    """
    def __init__(self, config, supports_device_sharing=True,
                 supports_hotplug=True, max_interfaces=5):
        self.service_vendor = 'general'
        self.supports_device_sharing = supports_device_sharing
        self.supports_hotplug = supports_hotplug
        self.maximum_interfaces = max_interfaces

        # TODO(MAGESH): Try to move the following handlers to
        # NDO manager rather than having here in the driver
        self.identity_handler = openstack_driver.KeystoneClient(config)
        self.compute_handler_nova = openstack_driver.NovaClient(config)
        self.network_handlers = {
            nfp_constants.GBP_MODE:
                nfp_gbp_network_driver.NFPGBPNetworkDriver(config),
            nfp_constants.NEUTRON_MODE:
                nfp_neutron_network_driver.NFPNeutronNetworkDriver(config)
        }
        self.setup_mode = self._get_setup_mode(config)
        self._advance_sharing_network_id = None

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

    def _get_setup_mode(self, config):
        if nfp_constants.APIC_CONFIG_SECTION in config.list_all_sections():
            return {nfp_constants.APIC_MODE: True}
        else:
            return {nfp_constants.NEUTRON_MODE: True}

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

    def _get_token(self, device_data_token):

        try:
            token = (device_data_token
                     if device_data_token
                     else self.identity_handler.get_admin_token())
        except Exception:
            self._increment_stats_counter('keystone_token_get_failures')
            LOG.error(_LE('Failed to get token'))
            return None
        return token

    def _increment_stats_counter(self, metric, by=1):
        # TODO(RPM): create path and delete path have different driver objects.
        # This will not work in case of increment and decrement.
        # So, its no-operation now
        return
        try:
            self.stats.update({metric: self.stats.get(metric, 0) + by})
        except Exception:
            LOG.error(_LE("Statistics failure. Failed to increment"
                          " '%(metric)s' by %(by)d")
                      % {'metric': metric, 'by': by})

    def _decrement_stats_counter(self, metric, by=1):
        # TODO(RPM): create path and delete path have different driver objects.
        # This will not work in case of increment and decrement.
        # So, its no-operation now
        return
        try:
            self.stats.update({metric: self.stats[metric] - by})
        except Exception:
            LOG.error(_LE("Statistics failure. Failed to decrement"
                          " '%(metric)s' by %(by)d")
                      % {'metric': metric, 'by': by})

    def _is_device_sharing_supported(self):
        return self.supports_device_sharing

    def _create_management_interface(self, device_data, network_handler=None):
        token = self._get_token(device_data.get('token'))
        if not token:
            return None

        name = nfp_constants.MANAGEMENT_INTERFACE_NAME
        mgmt_interface = network_handler.create_port(
                token,
                self._get_admin_tenant_id(token=token),
                device_data['management_network_info']['id'],
                name=name)

        return {'id': mgmt_interface['id'],
                'port_model': (nfp_constants.GBP_PORT
                               if device_data['service_details'][
                                                        'network_mode'] ==
                               nfp_constants.GBP_MODE
                               else nfp_constants.NEUTRON_PORT),
                'port_classification': nfp_constants.MANAGEMENT,
                'port_role': None}

    def _delete_interface(self, device_data, interface,
                          network_handler=None):
        token = self._get_token(device_data.get('token'))
        if not token:
            return None

        network_handler.delete_port(token, interface['id'])

    def _get_advance_sharing_network_id(self, admin_tenant_id,
                                        network_handler=None):
        if self._advance_sharing_network_id:
            return self._advance_sharing_network_id
        filters = {'tenant_id': admin_tenant_id,
                   'name': ADVANCE_SHARING_PTG_NAME}
        admin_token = self._get_token(None)
        if not admin_token:
            return None
        sharing_networks = network_handler.get_networks(
            admin_token, filters=filters)
        if not sharing_networks:
            LOG.error(_LE("Found empty network for tenant with Tenant ID: "
                          "%(admin_tenant_id)s for advance sharing"),
                      {'admin_tenant_id': admin_tenant_id})
            raise Exception()
        elif len(sharing_networks) > 1:
            LOG.error(_LE("Found more then one network for sharing with"
                          " Tenant ID: %(admin_tenant_id)s for "
                          "advance sharing"),
                      {'admin_tenant_id': admin_tenant_id})
            raise Exception()
        else:
            self._advance_sharing_network_id = sharing_networks[0]['id']
        return self._advance_sharing_network_id

    def _create_advance_sharing_interfaces(self, device_data,
                                           network_handler=None):
        token = self._get_token(device_data.get('token'))
        if not token:
            return None

        admin_tenant_id = self._get_admin_tenant_id(token=token)
        port_infos = []
        port_model = (nfp_constants.GBP_PORT
                      if device_data['service_details'][
                          'network_mode'] == nfp_constants.GBP_MODE
                      else nfp_constants.NEUTRON_PORT)
        advance_sharing_network_id = self._get_advance_sharing_network_id(
                                                    admin_tenant_id,
                                                    network_handler)
        for i in range(self.maximum_interfaces):
            port = network_handler.create_port(token,
                                               admin_tenant_id,
                                               advance_sharing_network_id)
            port_infos.append({'id': port['id'],
                'port_model': port_model,
                'port_classification': nfp_constants.ADVANCE_SHARING,
                'port_role': None,
                'plugged_in_pt_id': network_handler.get_port_id(token,
                                                                port['id'])})
        return port_infos

    def _get_interfaces_for_device_create(self, device_data,
                                          network_handler=None):
        mgmt_interface = self._create_management_interface(
                device_data,
                network_handler=network_handler)
        return [mgmt_interface]

    def _delete_interfaces(self, device_data, interfaces,
                           network_handler=None):
        for interface in interfaces:
            self._delete_interface(
                    device_data, interface,
                    network_handler=network_handler)

    def _verify_vendor_data(self, image_name, metadata):
        vendor_data = {}
        try:
            for attr in metadata:
                if attr in nfp_constants.METADATA_SUPPORTED_ATTRIBUTES:
                    vendor_data[attr] = ast.literal_eval(metadata[attr])
        except Exception as e:
            LOG.error(_LE('Wrong metadata: %(metadata)s provided for '
                          'image name: %(image_name)s. Error: %(error)s'),
                      {'image_name': image_name, 'metadata': metadata,
                       'error': e})
            return None
        return vendor_data

    def _get_vendor_data(self, device_data, image_name):
        token = self._get_token(device_data.get('token'))
        if not token:
            return None
        try:
            metadata = self.compute_handler_nova.get_image_metadata(
                    token,
                    self._get_admin_tenant_id(token=token),
                    image_name)
        except Exception as e:
            self._increment_stats_counter('image_details_get_failures')
            LOG.error(_LE('Failed to get image metadata for image '
                          'name: %(image_name)s. Error: %(error)s'),
                      {'image_name': image_name, 'error': e})
            return None
        vendor_data = self._verify_vendor_data(image_name, metadata)
        if not vendor_data:
            return None
        return vendor_data

    def _update_self_with_vendor_data(self, vendor_data, attr):
        attr_value = getattr(self, attr)
        if attr in vendor_data:
            setattr(self, attr, vendor_data[attr])
        else:
            LOG.info(_LI("Vendor data specified in image, doesn't contains "
                         "%(attr)s value, proceeding with default value "
                         "%(default)s"),
                     {'attr': attr, 'default': attr_value})

    def _update_vendor_data(self, device_data, token=None):
        try:
            image_name = self._get_image_name(device_data)
            vendor_data = self._get_vendor_data(device_data, image_name)
            LOG.info(_LI("Vendor data, specified in image: %(vendor_data)s"),
                     {'vendor_data': vendor_data})
            if vendor_data:
                self._update_self_with_vendor_data(vendor_data,
                                            nfp_constants.MAXIMUM_INTERFACES)
                self._update_self_with_vendor_data(vendor_data,
                                            nfp_constants.SUPPORTS_SHARING)
                self._update_self_with_vendor_data(vendor_data,
                                            nfp_constants.SUPPORTS_HOTPLUG)
            else:
                LOG.info(_LI("No vendor data specified in image, "
                             "proceeding with default values"))
        except Exception:
            LOG.error(_LE("Error while getting metadata for image name: %s,"
                          " proceeding with default values")
                      % (image_name))

    def _get_image_name(self, device_data):
        if device_data['service_details'].get('image_name'):
            image_name = device_data['service_details']['image_name']
        else:
            LOG.info(_LI("No image name provided in service profile's "
                         "service flavor field, image will be selected "
                         "based on service vendor's name : %s")
                     % (device_data['service_details']['service_vendor']))
            image_name = device_data['service_details']['service_vendor']
            image_name = '%s' % image_name.lower()
        return image_name

    def get_network_function_device_sharing_info(self, device_data):
        """ Get filters for NFD sharing

        :param device_data: NFD data
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

        if (
            any(key not in device_data
                for key in ['tenant_id',
                            'service_details']) or

            type(device_data['service_details']) is not dict or

            any(key not in device_data['service_details']
                for key in ['service_vendor'])
        ):
            raise exceptions.IncompleteData()

        image_name = self._get_image_name(device_data)
        if image_name:
            self._update_vendor_data(device_data,
                                 device_data.get('token'))
        if not self._is_device_sharing_supported():
            return None
        return {
                'filters': {
                    'tenant_id': [device_data['tenant_id']],
                    'service_vendor': [device_data['service_details'][
                                                        'service_vendor']],
                    'status': [nfp_constants.ACTIVE]
                }
        }

    def select_network_function_device(self, devices, device_data):
        """ Select a NFD which is eligible for sharing

        :param devices: NFDs
        :type devices: list
        :param device_data: NFD data
        :type device_data: dict

        :returns: None -- when device sharing is not supported, or
                          when no device is eligible for sharing
        :return: dict -- NFD which is eligible for sharing

        :raises: exceptions.IncompleteData
        """

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

        image_name = self._get_image_name(device_data)
        if image_name:
            self._update_vendor_data(device_data,
                                 device_data.get('token'))
        if not self._is_device_sharing_supported():
            return None

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

    @_set_network_handler
    def create_network_function_device(self, device_data,
                                       network_handler=None):
        """ Create a NFD

        :param device_data: NFD data
        :type device_data: dict

        :returns: None -- when there is a failure in creating NFD
        :return: dict -- NFD created

        :raises: exceptions.IncompleteData,
                 exceptions.ComputePolicyNotSupported
        """
        if (
            any(key not in device_data
                for key in ['service_details',
                            'name',
                            'management_network_info',
                            'ports']) or

            type(device_data['service_details']) is not dict or

            any(key not in device_data['service_details']
                for key in ['service_vendor',
                            'device_type',
                            'network_mode']) or

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

        if (
            device_data['service_details']['device_type'] !=
            nfp_constants.NOVA_MODE
        ):
            raise exceptions.ComputePolicyNotSupported(
                compute_policy=device_data['service_details']['device_type'])

        image_name = self._get_image_name(device_data)
        if image_name:
            self._update_vendor_data(device_data,
                                 device_data.get('token'))
        try:
            interfaces = self._get_interfaces_for_device_create(
                    device_data,
                    network_handler=network_handler
            )
        except Exception as e:
            LOG.exception(_LE('Failed to get interfaces for device creation.'
                              'Error: %(error)s'), {'error', e})
            return None
        else:
            self._increment_stats_counter('management_interfaces',
                                          by=len(interfaces))

        token = self._get_token(device_data.get('token'))
        if not token:
            return None

        if device_data['service_details'].get('image_name'):
            image_name = device_data['service_details']['image_name']
        else:
            LOG.info(_LI("No image name provided in service profile's "
                         "service flavor field, image will be selected "
                         "based on service vendor's name : %s")
                     % (device_data['service_details']['service_vendor']))
            image_name = device_data['service_details']['service_vendor']
            image_name = '%s' % image_name.lower()
        try:
            image_id = self.compute_handler_nova.get_image_id(
                    token,
                    self._get_admin_tenant_id(token=token),
                    image_name)
        except Exception as e:
            self._increment_stats_counter('image_details_get_failures')
            LOG.error(_LE('Failed to get image id for device creation.'
                          ' image name: %(image_name)s. Error: %(error)s'),
                      {'image_name': image_name, 'error': e})
            self._delete_interfaces(device_data, interfaces,
                                    network_handler=network_handler)
            self._decrement_stats_counter('management_interfaces',
                                          by=len(interfaces))
            return None

        if device_data['service_details'].get('flavor'):
            flavor = device_data['service_details']['flavor']
        else:
            LOG.info(_LI("No Device flavor provided in service profile's "
                         "service flavor field, using default "
                         "flavor: m1.medium"))
            flavor = 'm1.medium'

        interfaces_to_attach = []
        advance_sharing_interfaces = []
        try:
            for interface in interfaces:
                port_id = network_handler.get_port_id(token, interface['id'])
                interfaces_to_attach.append({'port': port_id})

            if not self.supports_hotplug:
                if self.setup_mode.get(nfp_constants.NEUTRON_MODE):
                    # TODO(ashu): get neutron mode from conf
                    for port in device_data['ports']:
                        if (port['port_classification'] ==
                                nfp_constants.PROVIDER):
                            if (device_data['service_details'][
                                        'service_type'].lower()
                                in [nfp_constants.FIREWALL.lower()]):
                                network_handler.set_promiscuos_mode(
                                        token, port['id'])
                            port_id = network_handler.get_port_id(
                                                            token, port['id'])
                            interfaces_to_attach.append({'port': port_id})
                    for port in device_data['ports']:
                        if (port['port_classification'] ==
                                nfp_constants.CONSUMER):
                            if (device_data['service_details'][
                                        'service_type'].lower()
                                in [nfp_constants.FIREWALL.lower()]):
                                network_handler.set_promiscuos_mode(
                                        token, port['id'])
                            port_id = network_handler.get_port_id(
                                                            token, port['id'])
                            interfaces_to_attach.append({'port': port_id})
                elif self.setup_mode.get(nfp_constants.APIC_MODE):
                    advance_sharing_interfaces = (
                        self._create_advance_sharing_interfaces(
                            device_data,
                            network_handler))
                    for interface in advance_sharing_interfaces:
                        port_id = network_handler.get_port_id(token,
                                                              interface['id'])
                        interfaces_to_attach.append({'port': port_id})

                    interfaces += advance_sharing_interfaces

        except Exception as e:
            self._increment_stats_counter('port_details_get_failures')
            LOG.error(_LE('Failed to fetch list of interfaces to attach'
                ' for device creation %(error)s'), {'error': e})
            self._delete_interfaces(device_data, interfaces,
                                    network_handler=network_handler)
            self._decrement_stats_counter('management_interfaces',
                                          by=len(interfaces))
            return None

        instance_name = device_data['name']
        try:
            instance_id = self.compute_handler_nova.create_instance(
                    token, self._get_admin_tenant_id(token=token),
                    image_id, flavor,
                    interfaces_to_attach, instance_name)
        except Exception as e:
            self._increment_stats_counter('instance_launch_failures')
            LOG.error(_LE('Failed to create %(device_type)s instance.'
                          'Error: %(error)s'),
                      {'device_type': (
                          device_data['service_details']['device_type']),
                       'error': e})
            self._delete_interfaces(device_data, interfaces,
                                    network_handler=network_handler)
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
                    (mgmt_ip_address,
                     dummy, dummy,
                     dummy) = network_handler.get_port_details(
                                                        token, interface['id'])
        except Exception as e:
            self._increment_stats_counter('port_details_get_failures')
            LOG.error(_LE('Failed to get management port details. '
                          'Error: %(error)s'), {'error': e})
            try:
                self.compute_handler_nova.delete_instance(
                                            token,
                                            self._get_admin_tenant_id(
                                                                token=token),
                                            instance_id)
            except Exception as e:
                self._increment_stats_counter('instance_delete_failures')
                LOG.error(_LE('Failed to delete %(device_type)s instance.'
                              'Error: %(error)s'),
                          {'device_type': (
                              device_data['service_details']['device_type']),
                           'error': e})
            self._decrement_stats_counter('instances')
            self._delete_interfaces(device_data, interfaces,
                                    network_handler=network_handler)
            self._decrement_stats_counter('management_interfaces',
                                          by=len(interfaces))
            return None

        return {'id': instance_id,
                'name': instance_name,
                'mgmt_ip_address': mgmt_ip_address,
                'mgmt_port_id': interfaces[0],
                'max_interfaces': self.maximum_interfaces,
                'interfaces_in_use': len(interfaces_to_attach),
                'advance_sharing_interfaces': advance_sharing_interfaces,
                'description': ''}  # TODO(RPM): what should be the description

    @_set_network_handler
    def delete_network_function_device(self, device_data,
                                       network_handler=None):
        """ Delete the NFD

        :param device_data: NFD
        :type device_data: dict

        :returns: None -- Both on success and Failure

        :raises: exceptions.IncompleteData,
                 exceptions.ComputePolicyNotSupported
        """
        if (
            any(key not in device_data
                for key in ['service_details',
                            'mgmt_port_id']) or

            type(device_data['service_details']) is not dict or

            any(key not in device_data['service_details']
                for key in ['service_vendor',
                            'device_type',
                            'network_mode']) or

            type(device_data['mgmt_port_id']) is not dict or

            any(key not in device_data['mgmt_port_id']
                for key in ['id',
                            'port_classification',
                            'port_model'])
        ):
            raise exceptions.IncompleteData()

        if (
            device_data['service_details']['device_type'] !=
            nfp_constants.NOVA_MODE
        ):
            raise exceptions.ComputePolicyNotSupported(
                compute_policy=device_data['service_details']['device_type'])

        image_name = self._get_image_name(device_data)
        if image_name:
            self._update_vendor_data(device_data,
                                 device_data.get('token'))
        token = self._get_token(device_data.get('token'))
        if not token:
            return None

        if device_data.get('id'):
            # delete the device instance
            #
            # this method will be invoked again
            # once the device instance deletion is completed
            try:
                self.compute_handler_nova.delete_instance(
                                                token,
                                                self._get_admin_tenant_id(
                                                                token=token),
                                                device_data['id'])
            except Exception:
                self._increment_stats_counter('instance_delete_failures')
                LOG.error(_LE('Failed to delete %s instance')
                          % (device_data['service_details']['device_type']))
            else:
                self._decrement_stats_counter('instances')
        else:
            # device instance deletion is done, delete remaining resources
            try:
                interfaces = [device_data['mgmt_port_id']]
                interfaces.extend(device_data['advance_sharing_interfaces'])
                self._delete_interfaces(device_data,
                                        interfaces,
                                 network_handler=network_handler)
            except Exception as e:
                LOG.error(_LE('Failed to delete the management data port(s). '
                              'Error: %(error)s'), {'error': e})
            else:
                self._decrement_stats_counter('management_interfaces')

    def get_network_function_device_status(self, device_data,
                                           ignore_failure=False):
        """ Get the status of NFD

        :param device_data: NFD
        :type device_data: dict

        :returns: None -- On failure
        :return: str -- status string

        :raises: exceptions.IncompleteData,
                 exceptions.ComputePolicyNotSupported
        """
        if (
            any(key not in device_data
                for key in ['id',
                            'service_details']) or

            type(device_data['service_details']) is not dict or

            any(key not in device_data['service_details']
                for key in ['service_vendor',
                            'device_type',
                            'network_mode'])
        ):
            raise exceptions.IncompleteData()

        if (
            device_data['service_details']['device_type'] !=
            nfp_constants.NOVA_MODE
        ):
            raise exceptions.ComputePolicyNotSupported(
                compute_policy=device_data['service_details']['device_type'])

        token = self._get_token(device_data.get('token'))
        if not token:
            return None

        try:
            device = self.compute_handler_nova.get_instance(
                            token,
                            self._get_admin_tenant_id(token=token),
                            device_data['id'])
        except Exception:
            if ignore_failure:
                return None
            self._increment_stats_counter('instance_details_get_failures')
            LOG.error(_LE('Failed to get %s instance details')
                      % (device_data['service_details']['device_type']))
            return None  # TODO(RPM): should we raise an Exception here?

        return device['status']

    @_set_network_handler
    def plug_network_function_device_interfaces(self, device_data,
                                                network_handler=None):
        """ Attach the network interfaces for NFD

        :param device_data: NFD
        :type device_data: dict

        :returns: bool -- False on failure and True on Success

        :raises: exceptions.IncompleteData,
                 exceptions.ComputePolicyNotSupported
        """

        if (
            any(key not in device_data
                for key in ['id',
                            'service_details',
                            'ports']) or

            type(device_data['service_details']) is not dict or

            any(key not in device_data['service_details']
                for key in ['service_vendor',
                            'device_type',
                            'network_mode']) or

            type(device_data['ports']) is not list or

            any(key not in port
                for port in device_data['ports']
                for key in ['id',
                            'port_classification',
                            'port_model'])
        ):
            raise exceptions.IncompleteData()

        if (
            device_data['service_details']['device_type'] !=
            nfp_constants.NOVA_MODE
        ):
            raise exceptions.ComputePolicyNotSupported(
                compute_policy=device_data['service_details']['device_type'])

        token = self._get_token(device_data.get('token'))
        if not token:
            return None

        image_name = self._get_image_name(device_data)
        if image_name:
            self._update_vendor_data(device_data)

        update_ifaces = []
        try:
            if not self.supports_hotplug:
                # configure interfaces instead of hotplug
                if self.setup_mode.get(nfp_constants.APIC_MODE):
                    required_ports = len(device_data['ports'])
                    unused_ifaces = self._get_unused_interfaces(
                                    device_data['advance_sharing_interfaces'],
                                    required_ports)
                    data_port_ids = []

                    for port in device_data['ports']:
                        if (port['port_classification'] ==
                                nfp_constants.PROVIDER):
                            data_port_ids.append(port['id'])
                            break
                    for port in device_data['ports']:
                        if (port['port_classification'] ==
                                nfp_constants.CONSUMER):
                            data_port_ids.append(port['id'])

                    for data_port_id, iface in zip(data_port_ids,
                                                   unused_ifaces):
                        self._update_attached_port_with_data_port(token,
                                                             iface,
                                                             data_port_id,
                                                             network_handler,
                                                             stitch=True)
                        iface['mapped_real_port_id'] = data_port_id
                    update_ifaces = unused_ifaces
                elif self.setup_mode.get(nfp_constants.NEUTRON_MODE):
                    pass
            else:
                for port in device_data['ports']:
                    if port['port_classification'] == nfp_constants.PROVIDER:
                        if (
                            device_data['service_details'][
                                'service_type'].lower()
                            in [nfp_constants.FIREWALL.lower()]
                        ):
                            network_handler.set_promiscuos_mode(token,
                                                                port['id'])
                        port_id = network_handler.get_port_id(token,
                                                              port['id'])
                        self.compute_handler_nova.attach_interface(
                                    token,
                                    self._get_admin_tenant_id(token=token),
                                    device_data['id'],
                                    port_id)
                        break
                for port in device_data['ports']:
                    if port['port_classification'] == nfp_constants.CONSUMER:
                        if (
                            device_data['service_details'][
                                'service_type'].lower()
                            in [nfp_constants.FIREWALL.lower()]
                        ):
                            network_handler.set_promiscuos_mode(token,
                                                                port['id'])
                        port_id = network_handler.get_port_id(token,
                                                              port['id'])
                        self.compute_handler_nova.attach_interface(
                                    token,
                                    self._get_admin_tenant_id(token=token),
                                    device_data['id'],
                                    port_id)
                        break
        except Exception as e:
            self._increment_stats_counter('interface_plug_failures')
            LOG.error(_LE('Failed to plug interface(s) to the device.'
                          'Error: %(error)s'), {'error': e})
            return None, []
        else:
            return True, update_ifaces

    def _update_attached_port_with_data_port(self, token,
                                             unused_interface,
                                             data_port_id,
                                             network_handler=None,
                                             stitch=True):
        if stitch:
            # configure attached interface pt with real port id,
            # to specify fabric/controller to stitch these interfaces
            port_id = network_handler.get_port_id(token, data_port_id)
            description = "%s%s" % (
                        PROXY_PORT_PREFIX,
                        port_id)
            # TODO(ashu): update attached port mac with data port mac.
        else:
            # configure attached interface pt with empty string,
            # for further reuse of these interfaces
            description = ''
        port = {'description': description}
        network_handler.update_port(token, unused_interface['id'], port)

    def _get_unused_interfaces(self, advance_sharing_ifaces, required_ports):
        # sort the interfaces based on interface position
        advance_sharing_ifaces.sort(key=operator.itemgetter(
                                                        'interface_position'))
        unused_interfaces = []
        for iface in advance_sharing_ifaces:
            if not iface['mapped_real_port_id']:
                current_position = iface['interface_position']
                unused_interfaces = advance_sharing_ifaces[
                                        current_position:required_ports]
                break

        return unused_interfaces

    def _get_used_interfaces(self, advance_sharing_ifaces, data_port_ids):
        used_interfaces = []
        for iface in advance_sharing_ifaces:
            if iface['mapped_real_port_id'] in data_port_ids:
                used_interfaces.append(iface)
        return used_interfaces

    def _set_promiscous_mode(self, token, service_type,
                             port_ids, network_handler=None):
        for port_id in port_ids:
            if (service_type.lower() in [nfp_constants.FIREWALL.lower()]):
                network_handler.set_promiscuos_mode(token, port_id)

    def _get_data_port_ids(self, token, ports, service_type,
                           network_handler=None, set_promiscous_mode=False):
        # return data_port_ids in sequential format i.e.
        # provider port_id, then consumer port_id
        data_port_ids = []

        for port in ports:
            if port['port_classification'] == nfp_constants.PROVIDER:
                provider_port_id = network_handler.get_port_id(token,
                                                               port['id'])
                data_port_ids.append(provider_port_id)
                break
        for port in ports:
            if port['port_classification'] == nfp_constants.CONSUMER:
                consumer_port_id = network_handler.get_port_id(token,
                                                               port['id'])
                data_port_ids.append(consumer_port_id)

        if set_promiscous_mode:
            self._set_promiscous_mode(token, service_type, data_port_ids,
                                      network_handler)
        return data_port_ids

    @_set_network_handler
    def unplug_network_function_device_interfaces(self, device_data,
                                                  network_handler=None):
        """ Detach the network interfaces for NFD

        :param device_data: NFD
        :type device_data: dict

        :returns: bool -- False on failure and True on Success

        :raises: exceptions.IncompleteData,
                 exceptions.ComputePolicyNotSupported
        """

        if (
            any(key not in device_data
                for key in ['id',
                            'service_details',
                            'ports']) or

            type(device_data['service_details']) is not dict or

            any(key not in device_data['service_details']
                for key in ['service_vendor',
                            'device_type',
                            'network_mode']) or

            any(key not in port
                for port in device_data['ports']
                for key in ['id',
                            'port_classification',
                            'port_model'])
        ):
            raise exceptions.IncompleteData()

        if (
            device_data['service_details']['device_type'] !=
            nfp_constants.NOVA_MODE
        ):
            raise exceptions.ComputePolicyNotSupported(
                compute_policy=device_data['service_details']['device_type'])

        image_name = self._get_image_name(device_data)
        if image_name:
            self._update_vendor_data(device_data,
                                 device_data.get('token'))

        token = self._get_token(device_data.get('token'))
        if not token:
            return None

        update_ifaces = []
        try:
            if not self.supports_hotplug:
                if self.setup_mode.get(nfp_constants.APIC_MODE):
                    data_port_ids = []
                    for port in device_data['ports']:
                        if (port['port_classification'] ==
                                nfp_constants.PROVIDER):
                            data_port_ids.append(port['id'])
                            break
                    for port in device_data['ports']:
                        if (port['port_classification'] ==
                            nfp_constants.CONSUMER):
                            data_port_ids.append(port['id'])

                    used_ifaces = self._get_used_interfaces(
                                    device_data['advance_sharing_interfaces'],
                                    data_port_ids)

                    for data_port_id, iface in zip(data_port_ids, used_ifaces):
                        self._update_attached_port_with_data_port(token,
                                                             iface,
                                                             data_port_id,
                                                             network_handler,
                                                             stitch=False)
                        iface['mapped_real_port_id'] = ''
                    update_ifaces = used_ifaces
                elif self.setup_mode.get(nfp_constants.NEUTRON_MODE):
                    pass
            else:
                for port in device_data['ports']:
                    port_id = network_handler.get_port_id(token, port['id'])
                    self.compute_handler_nova.detach_interface(
                                token,
                                self._get_admin_tenant_id(token=token),
                                device_data['id'],
                                port_id)

        except Exception as e:
            self._increment_stats_counter('interface_unplug_failures')
            LOG.error(_LE('Failed to unplug interface(s) from the device.'
                          'Error: %(error)s'), {'error': e})
            return None, []
        else:
            return True, update_ifaces

    def get_network_function_device_healthcheck_info(self, device_data):
        """ Get the health check information for NFD

        :param device_data: NFD
        :type device_data: dict

        :returns: dict -- It has the following scheme
        {
            'config': [
                {
                    'resource': 'healthmonitor',
                    'resource_data': {
                        ...
                    }
                }
            ]
        }

        :raises: exceptions.IncompleteData
        """
        if (
            any(key not in device_data
                for key in ['id',
                            'mgmt_ip_address'])
        ):
            raise exceptions.IncompleteData()

        return {
            'config': [
                {
                    'resource': nfp_constants.HEALTHMONITOR_RESOURCE,
                    'resource_data': {
                        'vmid': device_data['id'],
                        'mgmt_ip': device_data['mgmt_ip_address'],
                        'periodicity': 'initial'
                    }
                }
            ]
        }

    @_set_network_handler
    def get_network_function_device_config_info(self, device_data,
                                                network_handler=None):
        """ Get the configuration information for NFD

        :param device_data: NFD
        :type device_data: dict

        :returns: None -- On Failure
        :returns: dict -- It has the following scheme
        {
            'config': [
                {
                    'resource': 'interfaces',
                    'resource_data': {
                        ...
                    }
                },
                {
                    'resource': 'routes',
                    'resource_data': {
                        ...
                    }
                }
            ]
        }

        :raises: exceptions.IncompleteData
        """
        if (
            any(key not in device_data
                for key in ['service_details',
                            'mgmt_ip_address',
                            'ports']) or

            type(device_data['service_details']) is not dict or

            any(key not in device_data['service_details']
                for key in ['service_vendor',
                            'device_type',
                            'network_mode']) or

            type(device_data['ports']) is not list or

            any(key not in port
                for port in device_data['ports']
                for key in ['id',
                            'port_classification',
                            'port_model'])
        ):
            raise exceptions.IncompleteData()

        token = self._get_token(device_data.get('token'))
        if not token:
            return None

        provider_ip = None
        provider_mac = None
        provider_cidr = None
        consumer_ip = None
        consumer_mac = None
        consumer_cidr = None
        consumer_gateway_ip = None

        for port in device_data['ports']:
            if port['port_classification'] == nfp_constants.PROVIDER:
                try:
                    (provider_ip, provider_mac, provider_cidr, dummy) = (
                            network_handler.get_port_details(token, port['id'])
                    )
                except Exception:
                    self._increment_stats_counter('port_details_get_failures')
                    LOG.error(_LE('Failed to get provider port details'
                                  ' for get device config info operation'))
                    return None
            elif port['port_classification'] == nfp_constants.CONSUMER:
                try:
                    (consumer_ip, consumer_mac, consumer_cidr,
                     consumer_gateway_ip) = (
                            network_handler.get_port_details(token, port['id'])
                    )
                except Exception:
                    self._increment_stats_counter('port_details_get_failures')
                    LOG.error(_LE('Failed to get consumer port details'
                                  ' for get device config info operation'))
                    return None

        return {
            'config': [
                {
                    'resource': nfp_constants.INTERFACE_RESOURCE,
                    'resource_data': {
                        'mgmt_ip': device_data['mgmt_ip_address'],
                        'provider_ip': provider_ip,
                        'provider_cidr': provider_cidr,
                        'provider_interface_index': 2,
                        'stitching_ip': consumer_ip,
                        'stitching_cidr': consumer_cidr,
                        'stitching_interface_index': 3,
                        'provider_mac': provider_mac,
                        'stitching_mac': consumer_mac,
                    }
                },
                {
                    'resource': nfp_constants.ROUTES_RESOURCE,
                    'resource_data': {
                        'mgmt_ip': device_data['mgmt_ip_address'],
                        'source_cidrs': ([provider_cidr, consumer_cidr]
                                         if consumer_cidr
                                         else [provider_cidr]),
                        'destination_cidr': consumer_cidr,
                        'gateway_ip': consumer_gateway_ip,
                        'provider_interface_index': 2
                    }
                }
            ]
        }
