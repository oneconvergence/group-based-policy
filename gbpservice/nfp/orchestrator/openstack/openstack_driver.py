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

from gbpclient.v2_0 import client as gbp_client
from keystoneclient.v2_0 import client as identity_client
from keystoneclient.v3 import client as keyclientv3
from neutronclient.v2_0 import client as neutron_client
from novaclient import client as nova_client

from gbpservice.nfp.core import log as nfp_logging
LOG = nfp_logging.getLogger(__name__)


class OpenstackApi(object):
    """Initializes common attributes for openstack client drivers."""

    def __init__(self, config, username=None,
                 password=None, tenant_name=None):
        self.nova_version = '2'
        self.config = config
        self.identity_service = ("%s://%s:%d/%s/" %
                                 (config.keystone_authtoken.auth_protocol,
                                  config.keystone_authtoken.auth_host,
                                  config.keystone_authtoken.auth_port,
                                  config.keystone_authtoken.auth_version))
        self.network_service = ("%s://%s:%d/" %
                                (config.keystone_authtoken.auth_protocol,
                                 config.keystone_authtoken.auth_host,
                                 config.bind_port))
        self.username = username or config.keystone_authtoken.admin_user
        self.password = password or config.keystone_authtoken.admin_password
        self.tenant_name = (tenant_name or
                            config.keystone_authtoken.admin_tenant_name)
        self.token = None


class KeystoneClient(OpenstackApi):
    """ Keystone Client Apis for orchestrator. """

    def get_keystone_creds(self):
        keystone_conf = self.config.keystone_authtoken
        user = keystone_conf.admin_user
        pw = keystone_conf.admin_password
        tenant = keystone_conf.admin_tenant_name
        auth_url = self.identity_service

        return user, pw, tenant, auth_url

    def get_admin_token(self):
        try:
            admin_token = self.get_scoped_keystone_token(
                self.config.keystone_authtoken.admin_user,
                self.config.keystone_authtoken.admin_password,
                self.config.keystone_authtoken.admin_tenant_name)
        except Exception as ex:
            err = ("Failed to obtain user token. Error: %s" % ex)
            LOG.error(err)
            raise Exception(err)

        return admin_token

    def get_scoped_keystone_token(self, user, password, tenant_name,
                                  tenant_id=None):
        """ Get a scoped token from Openstack Keystone service.

        A scoped token is bound to the specific tenant.

        :param user: User name
        :param password: Password
        :param tenantName: Tenant name

        :return: A scoped token or None if unable to get
        """
        if not (tenant_name or tenant_id):
            err = "Tenant Not specified for getting a scoped token"
            LOG.error(err)
            raise Exception(err)

        keystone = identity_client.Client(
            username=user,
            password=password,
            tenant_name=tenant_name,
            tenant_id=tenant_id,
            auth_url=self.identity_service)
        try:
            scoped_token = keystone.auth_token
        except Exception as err:
            err = ("Failed to get scoped token from"
                   " Openstack Keystone service"
                   " KeyError :: %s" % (err))
            self.config.keystone_authtoken.auth_port,
            LOG.error(err)
            raise Exception(err)
        else:
            return scoped_token

    def get_tenant_id(self, token, tenant_name):
        """ Get the tenant UUID associated to tenant name

        :param token: A scoped token
        :param tenant: Tenant name

        :return: Tenant UUID
        """
        try:
            keystone = identity_client.Client(token=token,
                                              auth_url=self.identity_service)
            tenant = keystone.tenants.find(name=tenant_name)
            return tenant.id
        except Exception as ex:
            err = ("Failed to read tenant UUID from"
                   " tenant_name %s."
                   " Error :: %s" % (tenant_name, ex))
            LOG.error(err)
            raise Exception(err)
        err = 'No tenant with name "%s" found in keystone db' % tenant_name
        LOG.error(err)
        raise Exception(err)

    def _get_v2_keystone_admin_client(self):
        """ Returns keystone v2 client with admin credentials
            Using this client one can perform CRUD operations over
            keystone resources.
        """
        keystone_conf = self.config.keystone_authtoken

        v2client = identity_client.Client(
            username=keystone_conf.admin_user,
            password=keystone_conf.admin_password,
            tenant_name=keystone_conf.admin_tenant_name,
            tenant_id=None,
            auth_url=self.identity_service)

        return v2client

    def _get_v3_keystone_admin_client(self):
        """ Returns keystone v3 client with admin credentials
            Using this client one can perform CRUD operations over
            keystone resources.
        """
        keystone_conf = self.config.keystone_authtoken
        v3_auth_url = ('%s://%s:%s/%s/' % (
            keystone_conf.auth_protocol, keystone_conf.auth_host,
            keystone_conf.auth_port, self.config.heat_driver.keystone_version))
        v3client = keyclientv3.Client(
            username=keystone_conf.admin_user,
            password=keystone_conf.admin_password,
            domain_name="default",
            auth_url=v3_auth_url)
        return v3client


class NovaClient(OpenstackApi):
    """ Nova Client Api driver. """

    def get_image_id(self, token, tenant_id, image_name):
        """ Get the image UUID associated to image name

        :param token: A scoped token
        :param tenant_id: Tenant UUID
        :param image_name: Image name

        :return: Image UUID
        """
        try:
            nova = nova_client.Client(self.nova_version, auth_token=token,
                                      tenant_id=tenant_id,
                                      auth_url=self.identity_service)
            image = nova.images.find(name=image_name)
            return image.id
        except Exception as ex:
            err = ("Failed to get image id from image name %s: %s" % (
                image_name, ex))
            LOG.error(err)
            raise Exception(err)

    def get_image_metadata(self, token, tenant_id, image_name):
        """ Get the image UUID associated to image name

        :param token: A scoped token
        :param tenant_id: Tenant UUID
        :param image_name: Image name

        :return: Image UUID
        """
        try:
            nova = nova_client.Client(self.nova_version, auth_token=token,
                                      tenant_id=tenant_id,
                                      auth_url=self.identity_service)
            image = nova.images.find(name=image_name)
            return image.metadata
        except Exception as ex:
            err = ("Failed to get image metadata from image name %s: %s" % (
                image_name, ex))
            LOG.error(err)
            raise Exception(err)

    def get_flavor_id(self, token, tenant_id, flavor_name):
        """ Get the flavor UUID associated to flavor name

        :param token: A scoped token
        :param tenant_id: Tenant UUID
        :param flavor_name: Flavor name

        :return: Flavor UUID or None if not found
        """
        try:
            nova = nova_client.Client(self.nova_version, auth_token=token,
                                      tenant_id=tenant_id,
                                      auth_url=self.identity_service)
            flavor = nova.flavors.find(name=flavor_name)
            return flavor.id
        except Exception as ex:
            err = ("Failed to get flavor id from flavor name %s: %s" % (
                flavor_name, ex))
            LOG.error(err)
            raise Exception(err)

    def get_instance(self, token, tenant_id, instance_id):
        """ Get instance details

        :param token: A scoped_token
        :param tenant_id: Tenant UUID
        :param instance_id: Instance UUID

        :return: Instance details

        """
        try:
            nova = nova_client.Client(self.nova_version, auth_token=token,
                                      tenant_id=tenant_id,
                                      auth_url=self.identity_service)
            instance = nova.servers.get(instance_id)
            if instance:
                return instance.to_dict()
            raise Exception("No instance with id %s found in db for tenant %s"
                            % (instance_id, tenant_id))
        except Exception as ex:
            err = ("Failed to read instance information from"
                   " Openstack Nova service's response"
                   " KeyError :: %s" % (ex))
            LOG.error(err)
            raise Exception(err)

    def get_keypair(self, token, tenant_id, keypair_name):
        """ Get Nova keypair details

        :param token: A scoped_token
        :param tenant_id: Tenant UUID
        :param keypair_name: Nova keypair name

        :return: Nova keypair details

        """
        tenant_id = str(tenant_id)
        try:
            nova = nova_client.Client(self.nova_version, auth_token=token,
                                      tenant_id=tenant_id,
                                      auth_url=self.identity_service)
            keypair = nova.keypairs.find(name=keypair_name)
            return keypair.to_dict()
        except Exception as ex:
            err = ("Failed to read keypair information from"
                   " Openstack Nova service's response."
                   " %s" % ex)
            LOG.error(err)
            raise Exception(err)

    def attach_interface(self, token, tenant_id, instance_id, port_id):
        """ Attaches a port to already created instance
        :param token: A scoped token
        :param tenant_id: Tenant UUID
        :param instance_id: UUID of the instance
        :param port_id: Port UUID
        """
        try:
            nova = nova_client.Client(self.nova_version, auth_token=token,
                                      tenant_id=tenant_id,
                                      auth_url=self.identity_service)
            instance = nova.servers.interface_attach(instance_id, port_id,
                                                     None, None)
            return instance
        except Exception as ex:
            err = ("Failed to attach interface %s to instance"
                   " %s  %s" % (port_id, instance_id, ex))
            LOG.error(err)
            raise Exception(err)

    def detach_interface(self, token, tenant_id, instance_id, port_id):
        """ Detaches a port to already created instance
        :param token: A scoped token
        :param tenant_id: Tenant UUID
        :param instance_id: UUID of the instance
        :param port_id: Port UUID
        """
        try:
            nova = nova_client.Client(self.nova_version, auth_token=token,
                                      tenant_id=tenant_id,
                                      auth_url=self.identity_service)
            instance = nova.servers.interface_detach(instance_id, port_id)
            return instance
        except Exception as ex:
            err = ("Failed to detach interface %s from instance"
                   " %s  %s" % (port_id, instance_id, ex))
            LOG.error(err)
            raise Exception(err)

    def delete_instance(self, token, tenant_id, instance_id):
        """ Delete the instance

        :param token: A scoped token
        :param tenant_id: Tenant UUID
        :param instance_id: Instance UUID

        """
        try:
            nova = nova_client.Client(self.nova_version, auth_token=token,
                                      tenant_id=tenant_id,
                                      auth_url=self.identity_service)
            nova.servers.delete(instance_id)
        except Exception as ex:
            err = ("Failed to delete instance"
                   " %s  %s" % (instance_id, ex))
            LOG.error(err)
            raise Exception(err)

    def get_instances(self, token, filters=None):
        """ List instances

        :param token: A scoped_token
        :param filters: Parameters for list filter
        example for filter: {}, tenant_id is mandatory

        :return: instance List

        """
        if (
            not filters or
            type(filters) != dict or
            'tenant_id' not in filters
        ):
            err = ("Failed to process get_instances,"
                   " filters(type: dict) with tenant_id is mandatory")
            LOG.error(err)
            raise Exception(err)

        tenant_id = filters.get('tenant_id')
        try:
            nova = nova_client.Client(self.nova_version, auth_token=token,
                                      tenant_id=tenant_id,
                                      auth_url=self.identity_service)
            instances = nova.servers.list(search_opts=filters)
            data = [instance.to_dict() for instance in instances]
            return data
        except Exception as ex:
            err = ("Failed to list instances under tenant"
                   " %s  %s" % (tenant_id, ex))
            LOG.error(err)
            raise Exception(err)

    def create_instance(self, token, tenant_id, image_id, flavor,
                        nw_port_id_list, name, secgroup_name=None,
                        metadata=None, files=None, config_drive=False,
                        userdata=None, key_name='', different_hosts=None,
                        volume_support=False, volume_size="2"):
        """ Launch a VM with given details

        :param token: A scoped token
        :param tenant_id: Tenant UUID
        :param image_id: Image UUID
        :param flavor: Flavor name
        :param nw_port_id_list: Network UUID and port UUID list
        :param name: Service istance name
        :param secgroup_name: Nova security group name
        :param metadata: metadata key-value pairs
        :param files: List of files to be copied.
        :example files: [{"dst": <detination_path_string>,
                          "src": <file_contents>}]
        :param userdata: user data file name
        :param key_name: Nova keypair name
        :param different_hosts: Different host filter (List)
        :param volume_support: volume support to launch instance
        :param volume_size: cinder volume size in GB
        :return: VM instance UUID

        """
        kwargs = dict()
        if volume_support:
            block_device_mapping_v2 = [
                {
                    "boot_index": "1",
                    "uuid": image_id,
                    "source_type": "image",
                    "volume_size": volume_size,
                    "destination_type": "volume",
                    "delete_on_termination": True
                }
            ]
            kwargs.update(block_device_mapping_v2=block_device_mapping_v2)

        if different_hosts:
            kwargs.update(scheduler_hints={"different_host": different_hosts})
        if key_name != '':
            kwargs.update(key_name=key_name)
        if config_drive is True:
            kwargs.update(config_drive=True)
        if userdata is not None and type(userdata) is str:
            kwargs.update(userdata=userdata)
        if metadata is not None and type(metadata) is dict and metadata != {}:
            kwargs.update(meta=metadata)
        if files is not None and type(files) is list and files != []:
            kwargs.update(files=files)
        if nw_port_id_list:
            nics = [{"port-id": entry.get("port"), "net-id": entry.get("uuid"),
                     "v4-fixed-ip": entry.get("fixed_ip")}
                    for entry in nw_port_id_list]
            kwargs.update(nics=nics)
        if secgroup_name:
            kwargs.update(security_groups=[secgroup_name])

        try:
            nova = nova_client.Client(self.nova_version, auth_token=token,
                                      tenant_id=tenant_id,
                                      auth_url=self.identity_service)
            flavor = nova.flavors.find(name=flavor)
            instance = nova.servers.create(name, nova.images.get(image_id),
                                           flavor, **kwargs)
            data = instance.to_dict()
            return data['id']
        except Exception as ex:
            err = ("Failed to create instance under tenant"
                   " %s  %s" % (tenant_id, ex))
            LOG.error(err)
            raise Exception(err)


class NeutronClient(OpenstackApi):
    """ Neutron Client Api Driver. """

    def get_floating_ip(self, token, floatingip_id):
        """ Get floatingip details

        :param token: A scoped_token
        :param floatingip_id: Port UUID

        :return: floatingip details

        """
        try:
            neutron = neutron_client.Client(token=token,
                                            endpoint_url=self.network_service)
            return neutron.show_floatingip(floatingip_id)['floatingip']
        except Exception as ex:
            err = ("Failed to read floatingip from"
                   " Openstack Neutron service's response"
                   " KeyError :: %s" % (ex))
            LOG.error(err)
            raise Exception(err)

    def get_floating_ips(self, token, tenant_id=None, port_id=None):
        """ Get list of floatingips, associated with port if passed"""
        try:
            neutron = neutron_client.Client(token=token,
                                            endpoint_url=self.network_service)
            if port_id:
                return neutron.list_floatingips(port_id=port_id)['floatingips']
            else:
                return neutron.list_floatingips()['floatingips']
        except Exception as ex:
            err = ("Failed to read floatingips from"
                   " Openstack Neutron service's response"
                   " KeyError :: %s" % (ex))
            LOG.error(err)
            raise Exception(err)

    def get_port(self, token, port_id):
        """ Get port details

        :param token: A scoped_token
        :param port_id: Port UUID

        :return: Port details

        """
        try:
            neutron = neutron_client.Client(token=token,
                                            endpoint_url=self.network_service)
            return neutron.show_port(port_id)
        except Exception as ex:
            err = ("Failed to read port information"
                   " Exception :: %s" % (ex))
            LOG.error(err)
            raise Exception(err)

    def get_ports(self, token, filters=None):
        """ List Ports

        :param token: A scoped_token
        :param filters: Parameters for list filter
        example for filter: ?tenant_id=%s&id=%s

        :return: Port List

        """
        try:
            neutron = neutron_client.Client(token=token,
                                            endpoint_url=self.network_service)
            ports = neutron.list_ports(**filters).get('ports', [])
            return ports
        except Exception as ex:
            err = ("Failed to read port list from"
                   " Openstack Neutron service's response"
                   " KeyError :: %s" % (ex))
            LOG.error(err)
            raise Exception(err)

    def get_subnets(self, token, filters=None):
        """ List subnets

        :param token: A scoped_token
        :param filters: Parameters for list filter
        example for filter: ?tenant_id=%s&id=%s

        :return: Subnet List

        """
        try:
            neutron = neutron_client.Client(token=token,
                                            endpoint_url=self.network_service)
            subnets = neutron.list_subnets(**filters).get('subnets', [])
            return subnets
        except Exception as ex:
            err = ("Failed to read subnet list from"
                   " Openstack Neutron service's response"
                   " KeyError :: %s" % (ex))
            LOG.error(err)
            raise Exception(err)

    def get_subnet(self, token, subnet_id):
        """ Get subnet details
        :param token: A scoped_token
        :param subnet_id: Subnet UUID
        :return: Subnet details
        """
        try:
            neutron = neutron_client.Client(token=token,
                                            endpoint_url=self.network_service)
            return neutron.show_subnet(subnet_id)
        except Exception as ex:
            err = ("Failed to read subnet from"
                   " Openstack Neutron service's response"
                   " KeyError :: %s" % (ex))
            LOG.error(err)
            raise Exception(err)

    def delete_floatingip(self, token, floatingip_id):
        """ Delete the floatingip
        :param token: A scoped token
        :param tenant_id: Tenant UUID
        :param floatingip_id: Floatingip UUID
        """
        try:
            neutron = neutron_client.Client(token=token,
                                            endpoint_url=self.network_service)
            return neutron.delete_floatingip(floatingip_id)
        except Exception as ex:
            err = ("Failed to delete floatingip from"
                   " Openstack Neutron service's response"
                   " KeyError :: %s" % (ex))
            LOG.error(err)
            raise Exception(err)

    def update_port(self, token, port_id, **kwargs):
        """
        :param token:
        :param port_id:
        :param kwargs: name=<>, allowed_address_pairs={'ip_address': <>,
                       'mac_address': <>}
        :return:
        """
        try:
            neutron = neutron_client.Client(token=token,
                                            endpoint_url=self.network_service)
            port_info = dict(port={})
            port_info['port'].update(kwargs)
            return neutron.update_port(port_id, body=port_info)
        except Exception as ex:
            err = ("Failed to update port info"
                   " Error :: %s" % (ex))
            LOG.error(err)
            raise Exception(err)

    def get_floating_ips_for_ports(self, token, **kwargs):
        """
        :param self:
        :param token:
        :param kwargs:
        :return:
        """
        data = {'floatingips': []}
        try:
            neutron = neutron_client.Client(token=token,
                                            endpoint_url=self.network_service)
            data = neutron.list_floatingips(port_id=[kwargs[key]
                                                     for key in kwargs])
            return data
        except Exception as ex:
            raise Exception(ex)

    def _update_floatingip(self, token, floatingip_id, data):
        """ Update the floatingip
        :param token: A scoped token
        :param floatingip_id: Floatingip UUID
        :param data: data to update
        """
        try:
            neutron = neutron_client.Client(token=token,
                                            endpoint_url=self.network_service)
            return neutron.update_floatingip(floatingip_id, body=data)
        except Exception as ex:
            err = ("Failed to update floatingip from"
                   " Openstack Neutron service's response"
                   " KeyError :: %s" % (ex))
            LOG.error(err)
            raise Exception(err)

    def disassociate_floating_ip(self, token, floatingip_id):
        """
        :param self:
        :param token:
        :param floatingip_id:
        :return:
        """
        info = {
            "floatingip": {
                "port_id": None}
        }
        self._update_floatingip(token, floatingip_id, info)
        LOG.debug("Successfully disassociated floatingip %s"
                  % floatingip_id)

    def associate_floating_ip(self, token, floatingip_id, port_id):
        """
        :param self:
        :param token:
        :param floatingip_id:
        :return:
        """

        info = {
            "floatingip": {
                "port_id": port_id}
        }

        self._update_floatingip(token, floatingip_id, info)
        LOG.debug("Successfully associated floatingip %s"
                  % floatingip_id)

    def list_ports(self, token, port_ids=None, **kwargs):
        """
        :param token:
        :param port_ids:
        :param kwargs:
        :return:
        """
        try:
            neutron = neutron_client.Client(token=token,
                                            endpoint_url=self.network_service)
            port_ids = port_ids if port_ids is not None else []
            ports = neutron.list_ports(id=port_ids).get('ports', [])
            return ports
        except Exception as ex:
            err = ("Failed to list ports %s" % ex)
            LOG.error(err)
            raise Exception(err)

    def list_subnets(self, token, subnet_ids=None, **kwargs):
        """
        :param token:
        :param subnet_ids:
        :param kwargs:
        :return:
        """
        try:
            neutron = neutron_client.Client(token=token,
                                            endpoint_url=self.network_service)
            subnet_ids = subnet_ids if subnet_ids is not None else []
            subnets = neutron.list_subnets(id=subnet_ids).get('subnets', [])
            return subnets
        except Exception as ex:
            err = ("Failed to list subnets %s" % ex)
            LOG.error(err)
            raise Exception(err)

    def create_port(self, token, tenant_id, net_id, attrs=None):

        attr = {
            'port': {
                # 'tenant_id': tenant_id,
                'network_id': net_id
            }
        }

        if attrs:
            attr['port'].update(attrs)

        try:
            neutron = neutron_client.Client(token=token,
                                            endpoint_url=self.network_service)
            return neutron.create_port(body=attr)['port']
        except Exception as ex:
            raise Exception("Port creation failed in network: %r of tenant: %r"
                            " Error: %s" % (net_id, tenant_id, ex))

    def delete_port(self, token, port_id):
        """
        :param token:
        :param port_id:
        :return:
        """
        try:
            neutron = neutron_client.Client(token=token,
                                            endpoint_url=self.network_service)
            return neutron.delete_port(port_id)
        except Exception as ex:
            err = ("Failed to delete port %s"
                   " Exception :: %s" % (port_id, ex))
            LOG.error(err)
            raise Exception(err)

    def get_pools(self, token, filters=None):
        """ List Pools

        :param token: A scoped_token
        :param filters: Parameters for list filter
        example for filter: ?tenant_id=%s&id=%s

        :return: Pool List

        """
        try:
            neutron = neutron_client.Client(token=token,
                                            endpoint_url=self.network_service)
            pools = neutron.list_pools(**filters).get('pools', [])
            return pools
        except Exception as ex:
            err = ("Failed to read pool list from"
                   " Openstack Neutron service's response"
                   " KeyError :: %s" % (ex))
            LOG.error(err)
            raise Exception(err)

    def get_vip(self, token, vip_id):
        """ Get vip details

        :param token: A scoped_token
        :param vip_id: Port UUID

        :return: VIP details

        """
        try:
            neutron = neutron_client.Client(token=token,
                                            endpoint_url=self.network_service)
            return neutron.show_vip(vip_id)
        except Exception as ex:
            err = ("Failed to read vip information"
                   " Exception :: %s" % (ex))
            LOG.error(err)
            raise Exception(err)

    def update_router(self, token, router_id, **kwargs):
        """
        :param token:
        :param router_id:
        :param kwargs: name=<>, routes=[
                                       {
                                            "nexthop": "10.1.0.10",
                                            "destination": "40.0.1.0/24"
                                       },....
                                    ]
        :return:
        """
        try:
            neutron = neutron_client.Client(token=token,
                                            endpoint_url=self.network_service)
            router_info = dict(router={})
            router_info['router'].update(kwargs)
            return neutron.update_router(router_id, body=router_info)
        except Exception as ex:
            err = ("Failed to update router info"
                   " Error :: %s" % (ex))
            LOG.error(err)
            raise Exception(err)

    def create_floatingip(self, token, floating_net_id, port_id):
        """
        {
            "floatingip": {
            "floating_network_id": "376da547-b977-4cfe-9cba-275c80debf57",
            "port_id": "ce705c24-c1ef-408a-bda3-7bbd946164ab"
            }
        }
        """
        attrs = {"floatingip": {
                    "floating_network_id": floating_net_id,
                    "port_id": port_id
                    }
                 }
        try:
            neutron = neutron_client.Client(token=token,
                                            endpoint_url=self.network_service)
            return neutron.create_floatingip(body=attrs)['floatingip']
        except Exception as ex:
            err = ("Failed to create floatingip %s" % ex)
            LOG.error(err)
            raise Exception(err)

    def add_router_interface(self, token, router_id, interface_info):
        """
        :param token:
        :param router_id:
        :param interface_info: interface_info = {'subnet_id': <>}
                            or interface_info = {'port_id': <>}
        """
        try:
            neutron = neutron_client.Client(token=token,
                                            endpoint_url=self.network_service)
            return neutron.add_interface_router(router_id, body=interface_info)
        except Exception as ex:
            err = ("Failed to add router interface, router: %s, interface: %s"
                   " Error :: %s" % (router_id, interface_info, ex))
            LOG.error(err)
            raise Exception(err)

    def remove_router_interface(self, token, router_id, interface_info):
        """
        :param token:
        :param router_id:
        :param interface_info: interface_info = {'subnet_id': <>}
                            or interface_info = {'port_id': <>}
        """
        try:
            neutron = neutron_client.Client(token=token,
                                            endpoint_url=self.network_service)
            return neutron.remove_interface_router(router_id,
                                                   body=interface_info)
        except Exception as ex:
            err = ("Failed to remove router interface, router: %s, interface: "
                   "%s Error :: %s" % (router_id, interface_info, ex))
            LOG.error(err)
            raise Exception(err)

    def add_router_gateway(self, token, router_id, ext_net_id):
        """
        :param token:
        :param router_id:
        :param ext_net_id:
        """
        gw_info = {'network_id': ext_net_id}
        try:
            neutron = neutron_client.Client(token=token,
                                            endpoint_url=self.network_service)
            return neutron.add_gateway_router(router_id, body=gw_info)
        except Exception as ex:
            err = ("Failed to set router gateway, router: %s, gw_info: %s"
                   " Error :: %s" % (router_id, gw_info, ex))
            LOG.error(err)
            raise Exception(err)

    def remove_router_gateway(self, token, router_id):
        """
        :param token:
        :param router_id:
        """
        try:
            neutron = neutron_client.Client(token=token,
                                            endpoint_url=self.network_service)
            return neutron.remove_gateway_router(router_id)
        except Exception as ex:
            err = ("Failed to remove router gateway, router: %s,"
                   " Error :: %s" % (router_id, ex))
            LOG.error(err)
            raise Exception(err)

    def get_router(self, token, router_id):
        """ Get router details
        :param token: A scoped_token
        :param router_id: router UUID
        :return: router details
        """
        try:
            neutron = neutron_client.Client(token=token,
                                            endpoint_url=self.network_service)
            return neutron.show_router(router_id)
        except Exception as ex:
            err = ("Failed to read router from"
                   " Openstack Neutron service's response"
                   " KeyError :: %s" % (ex))
            LOG.error(err)
            raise Exception(err)

    def create_network(self, token, tenant_id, attrs=None):

        attr = {
            'network': {
                'tenant_id': tenant_id,
            }
        }
        if attrs:
            attr['network'].update(attrs)

        try:
            neutron = neutron_client.Client(token=token,
                                            endpoint_url=self.network_service)
            return neutron.create_network(body=attr)['network']
        except Exception as ex:
            raise Exception("network creation failed in network: %r of tenant:"
                            " %r Error: %s" % (tenant_id, ex))

    def get_networks(self, token, filters=None):
        """ List nets

        :param token: A scoped_token
        :param filters: Parameters for list filter
        example for filter: ?tenant_id=%s&id=%s

        :return: network List

        """
        try:
            neutron = neutron_client.Client(token=token,
                                            endpoint_url=self.network_service)
            nets = neutron.list_networks(**filters).get('networks', [])
            return nets
        except Exception as ex:
            err = ("Failed to read network list from"
                   " Openstack Neutron service's response"
                   " KeyError :: %s" % (ex))
            LOG.error(err)
            raise Exception(err)


    def create_subnet(self, token, tenant_id, attrs=None):

        attr = {
            'subnet': {
                'tenant_id': tenant_id,
            }
        }
        if attrs:
            attr['subnet'].update(attrs)

        try:
            neutron = neutron_client.Client(token=token,
                                            endpoint_url=self.network_service)
            return neutron.create_subnet(body=attr)['subnet']
        except Exception as ex:
            raise Exception("subnet creation failed for tenant: %r"
                            " Error: %s" % (tenant_id, ex))


class GBPClient(OpenstackApi):
    """ GBP Client Api Driver. """

    def get_policy_target_groups(self, token, filters=None):
        """ List Policy Target Groups

        :param token: A scoped_token
        :param filters: Parameters for list filter
        example for filter: ?tenant_id=%s&id=%s

        :return: PTG List

        """
        try:
            gbp = gbp_client.Client(token=token,
                                    endpoint_url=self.network_service)
            return gbp.list_policy_target_groups(
                **filters)['policy_target_groups']
        except Exception as ex:
            err = ("Failed to read PTG list from"
                   " Openstack Neutron service's response."
                   " KeyError :: %s" % (ex))
            LOG.error(err)
            raise Exception(err)

    def get_policy_target_group(self, token, ptg_id, filters=None):
        """
        :param token: A scoped token
        :param ptg_id: PTG
        :param filters: Optional
        :return:
        """
        try:
            gbp = gbp_client.Client(token=token,
                                    endpoint_url=self.network_service)
            filters = filters if filters is not None else {}
            return gbp.show_policy_target_group(
                ptg_id, **filters)['policy_target_group']
        except Exception as ex:
            err = ("Failed to read PTG list from"
                   " Openstack Neutron service's response."
                   " KeyError :: %s" % (ex))
            LOG.error(err)
            raise Exception(err)

    def update_policy_target_group(self, token, ptg_id,
                                   policy_target_group_info):
        """ Updates a GBP Policy Target Group

        :param token: A scoped token
        :param ptg_id: PTG UUID
        :param policy_target_group_info: PTG info dict
        :return: PTG dict
        """
        try:
            gbp = gbp_client.Client(token=token,
                                    endpoint_url=self.network_service)
            return gbp.update_policy_target_group(
                ptg_id,
                body=policy_target_group_info)['policy_target_group']
        except Exception as ex:
            err = ("Failed to update policy target group. Error :: %s" % (ex))
            LOG.error(err)
            raise Exception(err)

    def create_policy_target(self, token, tenant_id,
                             policy_target_group_id, name, port_id=None):
        """ Creates a GBP Policy Target

        :param token: A scoped token
        :param tenant_id: Tenant UUID
        :param policy_target_group_id: PTG UUID
        :param name: PT name
        :return: PT dict
        """
        policy_target_info = {
            "policy_target": {
                "policy_target_group_id": policy_target_group_id,
                "tenant_id": tenant_id,
            }
        }
        if name:
            policy_target_info['policy_target'].update({'name': name})
        if port_id:
            policy_target_info["policy_target"]["port_id"] = port_id

        try:
            gbp = gbp_client.Client(token=token,
                                    endpoint_url=self.network_service)
            return gbp.create_policy_target(
                body=policy_target_info)['policy_target']

        except Exception as ex:
            err = ("Failed to read policy target information from"
                   " Openstack Neutron service's response."
                   " KeyError :: %s" % (ex))
            LOG.error(err)
            raise Exception(err)

    def delete_policy_target(self, token, policy_target_id):
        """ Delete the GBP policy_target
        :param token: A scoped token
        :param policy_target_id: PT UUID
        """
        try:
            gbp = gbp_client.Client(token=token,
                                    endpoint_url=self.network_service)
            return gbp.delete_policy_target(policy_target_id)

        except Exception as ex:
            err = ("Failed to delete policy target information from"
                   " Openstack Neutron service's response."
                   " KeyError :: %s" % (ex))
            LOG.error(err)
            raise Exception(err)

    def delete_policy_target_group(self, token, policy_target_group_id):
        """ Delete the GBP policy_target group
        :param token: A scoped token
        :param policy_target_id: PTG UUID
        """
        try:
            gbp = gbp_client.Client(token=token,
                                    endpoint_url=self.network_service)
            return gbp.delete_policy_target_group(policy_target_group_id)
        except Exception as ex:
            err = ("Failed to delete policy target group from"
                   " Openstack."
                   " Error :: %s" % (ex))
            LOG.error(err)
            raise Exception(err)

    def update_policy_target(self, token, policy_target_id, updated_pt):
        """ Update the Policy Target
        :param token: A scoped token
        :param policy_target_id: PT UUID
        :param updated_pt: New PT dict
        {\"policy_target\": {\"description\": \"test123\"}}
        """

        policy_target_info = {
            "policy_target": updated_pt
        }

        try:
            gbp = gbp_client.Client(token=token,
                                    endpoint_url=self.network_service)
            return gbp.update_policy_target(
                policy_target_id, body=policy_target_info)['policy_target']
        except Exception as ex:
            err = ("Failed to read updated PT information"
                   ". PT  %s."
                   " KeyError :: %s" % (policy_target_id, ex))
            LOG.error(err)
            raise Exception(err)

    def create_policy_target_group(self, token, tenant_id, name,
                                   l2_policy_id=None):
        """ Creates a GBP Policy Target Group

        :param token: A scoped token
        :param tenant_id: Tenant UUID
        :param name: PTG name
        :return: PTG dict
        """

        policy_target_group_info = {
            "policy_target_group": {
                "tenant_id": tenant_id,
                "name": name,
            }
        }

        if l2_policy_id:
            policy_target_group_info["policy_target_group"].update(
                {"l2_policy_id": l2_policy_id})

        try:
            gbp = gbp_client.Client(token=token,
                                    endpoint_url=self.network_service)
            return gbp.create_policy_target_group(
                body=policy_target_group_info)['policy_target_group']
        except Exception as ex:
            err = ("Failed to create policy target group. %s"
                   " Error :: %s" % (policy_target_group_info, ex))
            LOG.error(err)
            raise Exception(err)

    def create_l2_policy(self, token, tenant_id, name, l3_policy_id=None):

        l2_policy_info = {
            "l2_policy": {
                "tenant_id": tenant_id,
                "name": name
            }
        }
        if l3_policy_id:
            l2_policy_info["l2_policy"].update({'l3_policy_id': l3_policy_id})

        try:
            gbp = gbp_client.Client(token=token,
                                    endpoint_url=self.network_service)
            return gbp.create_l2_policy(body=l2_policy_info)['l2_policy']
        except Exception as ex:
            err = ("Failed to create l2 policy under tenant"
                   " %s. Error :: %s" % (tenant_id, ex))
            LOG.error(err)
            raise Exception(err)

    def delete_l2_policy(self, token, l2policy_id):
        """
        :param token:
        :param l2policy_id:
        :return:
        """
        try:
            gbp = gbp_client.Client(token=token,
                                    endpoint_url=self.network_service)
            return gbp.delete_l2_policy(l2policy_id)
        except Exception as ex:
            err = ("Failed to delete l2 policy %s. Reason %s" %
                   (l2policy_id, ex))
            LOG.error(err)
            raise Exception(err)

    # NOTE: The plural form in the function name is needed in that way
    # to construct the function generically
    def get_l2_policys(self, token, filters=None):
        """ List L2 policies

        :param token: A scoped_token
        :param filters: Parameters for list filter
        example for filter: {}

        :return: L2 policies List

        """
        try:
            gbp = gbp_client.Client(token=token,
                                    endpoint_url=self.network_service)
            filters = filters if filters is not None else {}
            return gbp.list_l2_policies(**filters)['l2_policies']
        except Exception as ex:
            err = ("Failed to list l2 policies. Reason %s" % ex)
            LOG.error(err)
            raise Exception(err)

    def get_l2_policy(self, token, policy_id, filters=None):
        """ List L2 policies

        :param token: A scoped_token
        :param policy_id: l2 policy id
        :param filters: Parameters for list filter
        example for filter: {}

        :return: L2 policies List

        """
        try:
            gbp = gbp_client.Client(token=token,
                                    endpoint_url=self.network_service)
            filters = filters if filters is not None else {}
            return gbp.show_l2_policy(
                policy_id, **filters)['l2_policy']
        except Exception as ex:
            err = ("Failed to read l2 policy list from"
                   " Openstack Neutron service's response."
                   " KeyError :: %s" % (ex))
            LOG.error(err)
            raise Exception(err)

    def create_network_service_policy(self, token,
                                      network_service_policy_info):

        try:
            gbp = gbp_client.Client(token=token,
                                    endpoint_url=self.network_service)
            return gbp.create_network_service_policy(
                    body=network_service_policy_info)['network_service_policy']
        except Exception as ex:
            err = ("Failed to create network service policy "
                   "Error :: %s" % (ex))
            LOG.error(err)
            raise Exception(err)

    def get_network_service_policies(self, token, filters=None):
        """ List network service policies

        :param token: A scoped_token
        :param filters: Parameters for list filter
        example for filter: {}

        :return: network service policy List

        """
        try:
            gbp = gbp_client.Client(token=token,
                                    endpoint_url=self.network_service)
            filters = filters if filters is not None else {}
            return gbp.list_network_service_policies(**filters)[
                                                    'network_service_policies']
        except Exception as ex:
            err = ("Failed to list network service policies. Reason %s" % ex)
            LOG.error(err)
            raise Exception(err)

    def get_external_policies(self, token, filters=None):
        """ List external policies

        :param token: A scoped_token
        :param filters: Parameters for list filter
        example for filter: {}

        :return: external policy List

        """
        try:
            gbp = gbp_client.Client(token=token,
                                    endpoint_url=self.network_service)
            filters = filters if filters is not None else {}
            return gbp.list_external_policies(**filters)['external_policies']
        except Exception as ex:
            err = ("Failed to list external policies. Reason %s" % ex)
            LOG.error(err)
            raise Exception(err)

    def get_policy_rule_sets(self, token, filters=None):
        """ List policy rule sets

        :param token: A scoped_token
        :param filters: Parameters for list filter
        example for filter: {}

        :return: policy rule set List

        """
        try:
            gbp = gbp_client.Client(token=token,
                                    endpoint_url=self.network_service)
            filters = filters if filters is not None else {}
            return gbp.list_policy_rule_sets(**filters)['policy_rule_sets']
        except Exception as ex:
            err = ("Failed to list policy rule sets. Reason %s" % ex)
            LOG.error(err)
            raise Exception(err)

    def get_policy_actions(self, token, filters=None):
        """ List policy actions

        :param token: A scoped_token
        :param filters: Parameters for list filter
        example for filter: {}

        :return: policy actions List

        """
        try:
            gbp = gbp_client.Client(token=token,
                                    endpoint_url=self.network_service)
            filters = filters if filters is not None else {}
            return gbp.list_policy_actions(**filters)['policy_actions']
        except Exception as ex:
            err = ("Failed to list policy actions. Reason %s" % ex)
            LOG.error(err)
            raise Exception(err)

    def get_policy_rules(self, token, filters=None):
        """ List policy rules

        :param token: A scoped_token
        :param filters: Parameters for list filter
        example for filter: {}

        :return: policy rules List

        """
        try:
            gbp = gbp_client.Client(token=token,
                                    endpoint_url=self.network_service)
            filters = filters if filters is not None else {}
            return gbp.list_policy_rules(**filters)['policy_rules']
        except Exception as ex:
            err = ("Failed to list policy rules. Reason %s" % ex)
            LOG.error(err)
            raise Exception(err)

    def create_l3_policy(self, token, l3_policy_info):  # tenant_id, name):

        try:
            gbp = gbp_client.Client(token=token,
                                    endpoint_url=self.network_service)
            return gbp.create_l3_policy(body=l3_policy_info)['l3_policy']
        except Exception as ex:
            err = ("Failed to create l3 policy under tenant"
                   " %s. Error :: %s"
                   % (l3_policy_info['l3_policy']['tenant_id'], ex))
            LOG.error(err)
            raise Exception(err)

    def get_l3_policy(self, token, policy_id, filters=None):
        """ List L3 policies

        :param token: A scoped_token
        :param filters: Parameters for list filter
        example for filter: {}

        :return: L3 policies List

        """
        try:
            gbp = gbp_client.Client(token=token,
                                    endpoint_url=self.network_service)
            filters = filters if filters is not None else {}
            return gbp.show_l3_policy(
                policy_id, **filters)['l3_policy']
        except Exception as ex:
            err = ("Failed to read l3 policy list from"
                   " Openstack Neutron service's response."
                   " KeyError :: %s" % (ex))
            LOG.error(err)
            raise Exception(err)

    def get_l3_policies(self, token, filters=None):
        """ List L3 policies

        :param token: A scoped_token
        :param filters: Parameters for list filter
        example for filter: {}

        :return: L2 policies List

        """
        try:
            gbp = gbp_client.Client(token=token,
                                    endpoint_url=self.network_service)
            filters = filters if filters is not None else {}
            return gbp.list_l3_policies(**filters)['l3_policies']
        except Exception as ex:
            err = ("Failed to list l3 policies. Reason %s" % ex)
            LOG.error(err)
            raise Exception(err)

    def get_policy_targets(self, token, filters=None):
        """ List Policy Targets

        :param token: A scoped_token
        :param filters: Parameters for list filter
        example for filter: {}

        :return: PT List

        """
        try:
            gbp = gbp_client.Client(token=token,
                                    endpoint_url=self.network_service)
            filters = filters if filters is not None else {}
            return gbp.list_policy_targets(**filters)['policy_targets']
        except Exception as ex:
            err = ("Failed to read PT list."
                   " Error :: %s" % (ex))
            LOG.error(err)
            raise Exception(err)

    def list_pt(self, token, filters=None):
        filters = filters if filters is not None else {}
        return self.get_policy_targets(token, filters=filters)

    def get_policy_target(self, token, pt_id, filters=None):
        try:
            gbp = gbp_client.Client(token=token,
                                    endpoint_url=self.network_service)
            filters = filters if filters is not None else {}
            return gbp.show_policy_target(pt_id,
                                          **filters)['policy_target']
        except Exception as ex:
            err = ("Failed to read PT information"
                   ". PT  %s."
                   " Error :: %s" % (pt_id, ex))
            LOG.error(err)
            raise Exception(err)

    def get_service_profile(self, token, service_profile_id):
        gbp = gbp_client.Client(token=token,
                                endpoint_url=self.network_service)
        return gbp.show_service_profile(service_profile_id)['service_profile']

    def get_servicechain_node(self, token, node_id):
        gbp = gbp_client.Client(token=token,
                                endpoint_url=self.network_service)
        return gbp.show_servicechain_node(node_id)['servicechain_node']

    def get_servicechain_instance(self, token, instance_id):
        gbp = gbp_client.Client(token=token,
                                endpoint_url=self.network_service)
        return gbp.show_servicechain_instance(instance_id)[
                                                    'servicechain_instance']
