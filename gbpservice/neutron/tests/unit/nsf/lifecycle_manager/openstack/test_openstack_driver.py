import mock
import unittest

from keystoneclient.v2_0 import client as identity_client
from neutronclient.v2_0 import client as neutron_client
from gbpclient.v2_0 import client as gbp_client
from gbpservice.neutron.nsf.lifecycle_manager.openstack import openstack_driver
from novaclient import client as nova_client

import sample_data


@mock.patch.object(identity_client, "Client")
class TestKeystoneClient(sample_data.SampleData):
    def __init__(self, *args, **kwargs):
        super(TestKeystoneClient, self).__init__(*args, **kwargs)
        self.keystone_obj = openstack_driver.KeystoneClient()

    def test_get_keystone_creds(self, mock_obj):
        retval = self.keystone_obj.get_keystone_creds()
        creds = ('neutron',
                 'neutron_pass',
                 'services',
                 'http://localhost:5000/v2.0/')
        self.assertEqual(retval, creds)

    def test_get_admin_token(self, mock_obj):
        instance = mock_obj.return_value
        instance.auth_token = True
        # import pdb; pdb.set_trace()
        retval = self.keystone_obj.get_admin_token()
        print retval
        self.assertEqual(retval, True)
        mock_obj.assert_called_once_with(auth_url=self.AUTH_URL,
                                         password='neutron_pass',
                                         tenant_id=None,
                                         tenant_name='services',
                                         username='neutron')

    def test_get_scoped_keystone_token(self, mock_obj):
        instance = mock_obj.return_value
        instance.auth_token = True
        retval = self.keystone_obj.get_scoped_keystone_token(self.USERNAME,
                                                             self.PASSWORD,
                                                             self.TENANT_NAME,
                                                             self.TENANT_ID)
        print retval
        self.assertEqual(retval, True)
        mock_obj.assert_called_once_with(auth_url=self.AUTH_URL,
                                         password=self.PASSWORD,
                                         tenant_id=self.TENANT_ID,
                                         tenant_name=self.TENANT_NAME,
                                         username=self.USERNAME)

    def test_get_tenant_id(self, mock_obj):
        instance = mock_obj.return_value
        instance.tenants.find().id = True
        retval = self.keystone_obj.get_tenant_id(self.AUTH_TOKEN,
                                                 "service")
        print retval
        self.assertEqual(retval, True)
        mock_obj.assert_called_once_with(auth_url=self.AUTH_URL,
                                         token=self.AUTH_TOKEN)


@mock.patch.object(nova_client, "Client")
class TestNovaClient(sample_data.SampleData):
    def __init__(self, *args, **kwargs):
        super(TestNovaClient, self).__init__(*args, **kwargs)
        self.nova_obj = openstack_driver.NovaClient()

    def test_get_image_id(self, mock_obj):
        instance = mock_obj.return_value
        instance.images.find().id = True
        retval = self.nova_obj.get_image_id(self.AUTH_TOKEN,
                                            self.TENANT_ID,
                                            self.IMAGE_NAME)
        self.assertEqual(retval, True)
        mock_obj.assert_called_once_with('2', auth_token=self.AUTH_TOKEN,
                                         tenant_id=self.TENANT_ID,
                                         auth_url=self.AUTH_URL)

    def test_get_flavor_id(self, mock_obj):
        instance = mock_obj.return_value
        instance.flavors.find().id = True
        retval = self.nova_obj.get_flavor_id(self.AUTH_TOKEN,
                                             self.TENANT_ID,
                                             self.FLAVOR_NAME)
        self.assertEqual(retval, True)

    def test_get_instance(self, mock_obj):
        instance = mock_obj.return_value
        obj = instance.servers.get(self.INSTANCE_ID).to_dict()
        retval = self.nova_obj.get_instance(self.AUTH_TOKEN,
                                            self.TENANT_ID,
                                            self.INSTANCE_ID)
        print retval
        self.assertEqual(retval, obj)
        mock_obj.assert_called_once_with('2', auth_token=self.AUTH_TOKEN,
                                         tenant_id=self.TENANT_ID,
                                         auth_url=self.AUTH_URL)

    def test_get_keypair(self, mock_obj):
        instance = mock_obj.return_value
        obj = instance.keypairs.find(name="keypair_name").to_dict()
        retval = self.nova_obj.get_keypair(self.AUTH_TOKEN,
                                           self.TENANT_ID,
                                           "keypair_name")
        print retval
        self.assertEqual(retval, obj)
        mock_obj.assert_called_once_with('2', auth_token=self.AUTH_TOKEN,
                                         tenant_id=self.TENANT_ID,
                                         auth_url=self.AUTH_URL)

    def test_attach_interface(self, mock_obj):
        instance = mock_obj.return_value
        with mock.patch.object(instance.servers, "interface_attach") as mock_obj1:
            mock_obj1.return_value = True
            retval = self.nova_obj.attach_interface(self.AUTH_TOKEN,
                                                    self.TENANT_ID,
                                                    self.INSTANCE_ID,
                                                    "port_id")
            print retval
            self.assertEqual(retval, True)
            mock_obj.assert_called_once_with('2', auth_token=self.AUTH_TOKEN,
                                             tenant_id=self.TENANT_ID,
                                             auth_url=self.AUTH_URL)

    def test_detach_interface(self, mock_obj):
        instance = mock_obj.return_value
        with mock.patch.object(instance.servers, "interface_detach") as mock_obj1:
            mock_obj1.return_value = True
            retval = self.nova_obj.detach_interface(self.AUTH_TOKEN,
                                                    self.TENANT_ID,
                                                    self.INSTANCE_ID,
                                                    "port_id")

            print retval
            self.assertEqual(retval, True)
            mock_obj.assert_called_once_with('2', auth_token=self.AUTH_TOKEN,
                                             tenant_id=self.TENANT_ID,
                                             auth_url=self.AUTH_URL)

    def test_delete_instance(self, mock_obj):
        instance = mock_obj.return_value
        with mock.patch.object(instance.servers, "delete") as mock_obj1:
            mock_obj1.return_value = True
            retval = self.nova_obj.delete_instance(self.AUTH_TOKEN,
                                                   self.TENANT_ID,
                                                   self.INSTANCE_ID)

            print retval
            self.assertIsNone(retval)
            mock_obj.assert_called_once_with('2', auth_token=self.AUTH_TOKEN,
                                             tenant_id=self.TENANT_ID,
                                             auth_url=self.AUTH_URL)

    def test_get_instances(self, mock_obj):
        instance = mock_obj.return_value
        obj = instance.servers.list("instance_test").to_dict()
        retval = self.nova_obj.get_instances(self.AUTH_TOKEN,
                                             {'tenant_id': self.TENANT_ID})
        print retval
        # self.assertEqual(retval, obj)
        self.assertIsNotNone(retval)
        mock_obj.assert_called_once_with('2', auth_token=self.AUTH_TOKEN,
                                         tenant_id=self.TENANT_ID,
                                         auth_url=self.AUTH_URL)

    def test_create_instance(self, mock_obj):
        instance = mock_obj.return_value
        obj = instance.flavors.find(self.FLAVOR_NAME)
        with mock.patch.object(instance.servers, "create") as mock_obj1:
            instance = mock_obj1.return_value
            obj1 = instance.to_dict()['id']
            retval = self.nova_obj.create_instance(self.AUTH_TOKEN,
                                                   self.TENANT_ID,
                                                   self.IMAGE_ID,
                                                   self.FLAVOR_NAME,
                                                   None,
                                                   "name",
                                                   "secgroup_name",
                                                   "metadata={}",
                                                   "files=[]",
                                                   "config_drive=False",
                                                   "userdata=None",
                                                   "key_name=''",
                                                   "different_hosts=None",
                                                   "volume_support=False",
                                                   "volume_size='2'")

            print retval
            self.assertEqual(retval, obj1)
            mock_obj.assert_called_once_with('2', auth_token=self.AUTH_TOKEN,
                                             tenant_id=self.TENANT_ID,
                                             auth_url=self.AUTH_URL)


@mock.patch.object(neutron_client, "Client")
class TestNeutronClient(sample_data.SampleData):
    def __init__(self, *args, **kwargs):
        super(TestNeutronClient, self).__init__(*args, **kwargs)
        self.neutron_obj = openstack_driver.NeutronClient()

    def test_get_floating_ip(self, mock_obj):
        instance = mock_obj.return_value
        obj = instance.show_floatingip('floatingip_id')['floatingip']
        retval = self.neutron_obj.get_floating_ip(
            self.AUTH_TOKEN, 'floatingip_id')
        print retval
        self.assertEqual(retval, obj)
        mock_obj.assert_called_once_with(token=self.AUTH_TOKEN,
                                         endpoint_url=self.ENDPOINT_URL)

    def test_get_floating_ips(self, mock_obj):
        instance = mock_obj.return_value
        obj = instance.list_floatingips()['floatingips']
        # retval = self.neutron_obj.get_floating_ips(self.AUTH_TOKEN)
        retval = self.neutron_obj.get_floating_ips(self.AUTH_TOKEN,
                                                   self.TENANT_ID,
                                                   self.PORT_ID)
        print retval
        self.assertEqual(retval, obj)
        mock_obj.assert_called_once_with(token=self.AUTH_TOKEN,
                                         endpoint_url=self.ENDPOINT_URL)

    def test_get_port(self, mock_obj):
        instance = mock_obj.return_value
        obj = instance.show_port(self.PORT_ID)
        retval = self.neutron_obj.get_port(self.AUTH_TOKEN,
                                           self.PORT_ID)
        print retval
        self.assertEqual(retval, obj)
        mock_obj.assert_called_once_with(token=self.AUTH_TOKEN,
                                         endpoint_url=self.ENDPOINT_URL)

    def test_get_ports(self, mock_obj):
        instance = mock_obj.return_value
        obj = instance.list_ports().get('ports', [])
        retval = self.neutron_obj.get_ports(self.AUTH_TOKEN,
                                            {})
        print retval
        self.assertEqual(retval, obj)
        mock_obj.assert_called_once_with(token=self.AUTH_TOKEN,
                                         endpoint_url=self.ENDPOINT_URL)

    def test_get_subnet(self, mock_obj):
        instance = mock_obj.return_value
        obj = instance.show_subnet('subnet_id')
        retval = self.neutron_obj.get_subnet(self.AUTH_TOKEN,
                                             'subnet_id')
        print retval
        self.assertEqual(retval, obj)
        mock_obj.assert_called_once_with(token=self.AUTH_TOKEN,
                                         endpoint_url=self.ENDPOINT_URL)

    def test_delete_floatingip(self, mock_obj):
        instance = mock_obj.return_value
        obj = instance.delete_floatingip('floatingip_id')
        retval = self.neutron_obj.delete_floatingip(self.AUTH_TOKEN,
                                                    'floatingip_id')
        print retval
        self.assertEqual(retval, obj)
        mock_obj.assert_called_once_with(token=self.AUTH_TOKEN,
                                         endpoint_url=self.ENDPOINT_URL)

    def test_update_port(self, mock_obj):
        instance = mock_obj.return_value
        obj = instance.update_port('port_id', body='port_info')
        retval = self.neutron_obj.update_port(self.AUTH_TOKEN,
                                              'port_id')
        print retval
        self.assertEqual(retval, obj)
        mock_obj.assert_called_once_with(token=self.AUTH_TOKEN,
                                         endpoint_url=self.ENDPOINT_URL)

    def test_get_floating_ips_for_ports(self, mock_obj):
        instance = mock_obj.return_value
        obj = instance.list_floatingips('port_id')
        retval = self.neutron_obj.get_floating_ips_for_ports(
            self.AUTH_TOKEN)
        print retval
        self.assertEqual(retval, obj)
        mock_obj.assert_called_once_with(token=self.AUTH_TOKEN,
                                         endpoint_url=self.ENDPOINT_URL)

    def test_disassociate_floating_ip(self, mock_obj):
        instance = mock_obj.return_value
        obj = instance.update_floatingip('floatingip_id', body='data')
        retval = self.neutron_obj.disassociate_floating_ip(self.AUTH_TOKEN,
                                                           'floatingip_id')
        print retval
        # self.assertEqual(retval, obj)
        self.assertIsNone(retval)
        mock_obj.assert_called_once_with(token=self.AUTH_TOKEN,
                                         endpoint_url=self.ENDPOINT_URL)

    def test_associate_floating_ip(self, mock_obj):
        instance = mock_obj.return_value
        obj = instance.update_floatingip('floatingip_id', body='data')
        retval = self.neutron_obj.associate_floating_ip(self.AUTH_TOKEN,
                                                        'floatingip_id',
                                                        'port_id')
        print retval
        # self.assertEqual(retval, obj)
        self.assertIsNone(retval)
        mock_obj.assert_called_once_with(token=self.AUTH_TOKEN,
                                         endpoint_url=self.ENDPOINT_URL)

    def test_list_ports(self, mock_obj):
        instance = mock_obj.return_value
        obj = instance.list_ports(id='port_ids').get('ports', [])
        retval = self.neutron_obj.list_ports(self.AUTH_TOKEN,
                                             'port_ids=[]')
        print retval
        self.assertEqual(retval, obj)
        mock_obj.assert_called_once_with(token=self.AUTH_TOKEN,
                                         endpoint_url=self.ENDPOINT_URL)

    def test_list_subnets(self, mock_obj):
        instance = mock_obj.return_value
        obj = instance.list_subnets(id='subnet_ids').get('subnets', [])
        retval = self.neutron_obj.list_subnets(self.AUTH_TOKEN,
                                               'subnet_ids=[]')
        print retval
        self.assertEqual(retval, obj)
        mock_obj.assert_called_once_with(token=self.AUTH_TOKEN,
                                         endpoint_url=self.ENDPOINT_URL)

    def test_create_port(self, mock_obj):
        instance = mock_obj.return_value
        obj = instance.create_port(body='attr')['port']
        retval = self.neutron_obj.create_port(self.AUTH_TOKEN,
                                              self.TENANT_ID,
                                              'net_id')
        print retval
        self.assertEqual(retval, obj)
        mock_obj.assert_called_once_with(token=self.AUTH_TOKEN,
                                         endpoint_url=self.ENDPOINT_URL)

    def test_delete_port(self, mock_obj):
        instance = mock_obj.return_value
        obj = instance.delete_port('port_id')
        retval = self.neutron_obj.delete_port(self.AUTH_TOKEN,
                                              'port_id')
        print retval
        self.assertEqual(retval, obj)
        mock_obj.assert_called_once_with(token=self.AUTH_TOKEN,
                                         endpoint_url=self.ENDPOINT_URL)


@mock.patch.object(gbp_client, "Client")
class TestGBPClient(sample_data.SampleData):
    def __init__(self, *args, **kwargs):
        super(TestGBPClient, self).__init__(*args, **kwargs)
        self.gbp_obj = openstack_driver.GBPClient()

    def test_get_policy_target_groups(self, mock_obj):
        instance = mock_obj.return_value
        obj = instance.list_policy_target_groups()['policy_target_groups']
        retval = self.gbp_obj.get_policy_target_groups(self.AUTH_TOKEN, {})
        print retval
        self.assertEqual(retval, obj)
        mock_obj.assert_called_once_with(token=self.AUTH_TOKEN,
                                         endpoint_url=self.ENDPOINT_URL)

    def test_get_policy_target_group(self, mock_obj):
        instance = mock_obj.return_value
        obj = instance.show_policy_target_group(
            'ptg_id', {})['policy_target_group']
        retval = self.gbp_obj.get_policy_target_group(self.AUTH_TOKEN,
                                                      'ptg_id', {})
        print retval
        self.assertEqual(retval, obj)
        mock_obj.assert_called_once_with(token=self.AUTH_TOKEN,
                                         endpoint_url=self.ENDPOINT_URL)

    def test_update_policy_target_group(self, mock_obj):
        instance = mock_obj.return_value
        obj = instance.update_policy_target_group(
            body='policy_target_group_info')['policy_target_group']
        retval = self.gbp_obj.update_policy_target_group(self.AUTH_TOKEN,
                                                         'ptg_id',
                                                         'policy_target_group_info')
        print retval
        self.assertEqual(retval, obj)
        mock_obj.assert_called_once_with(token=self.AUTH_TOKEN,
                                         endpoint_url=self.ENDPOINT_URL)

    def test_update_policy_target(self, mock_obj):
        instance = mock_obj.return_value
        obj = instance.update_policy_target('policy_target_id',
                                            body='policy_target_info')['policy_target']
        retval = self.gbp_obj.update_policy_target(self.AUTH_TOKEN,
                                                   'policy_target_id',
                                                   'updated_pt')
        print retval
        self.assertEqual(retval, obj)
        mock_obj.assert_called_once_with(token=self.AUTH_TOKEN,
                                         endpoint_url=self.ENDPOINT_URL)

    def test_create_policy_target(self, mock_obj):
        instance = mock_obj.return_value
        obj = instance.create_policy_target(
            body='policy_target_info')['policy_target']
        retval = self.gbp_obj.create_policy_target(self.AUTH_TOKEN,
                                                   self.TENANT_ID,
                                                   'policy_target_group_id',
                                                   'name', port_id=None)
        print retval
        self.assertEqual(retval, obj)
        mock_obj.assert_called_once_with(token=self.AUTH_TOKEN,
                                         endpoint_url=self.ENDPOINT_URL)

    def test_create_policy_target_group(self, mock_obj):
        instance = mock_obj.return_value
        obj = instance.create_policy_target_group(
            body='policy_target_group_info')['policy_target_group']
        retval = self.gbp_obj.create_policy_target_group(
            self.AUTH_TOKEN,
            self.TENANT_ID,
            'name',
            l2_policy_id=None)
        print retval
        self.assertEqual(retval, obj)
        mock_obj.assert_called_once_with(token=self.AUTH_TOKEN,
                                         endpoint_url=self.ENDPOINT_URL)

    def test_delete_policy_target(self, mock_obj):
        instance = mock_obj.return_value
        obj = instance.delete_policy_target('policy_target_id')
        retval = self.gbp_obj.delete_policy_target(self.AUTH_TOKEN,
                                                   'policy_target_id')
        print retval
        self.assertEqual(retval, obj)
        mock_obj.assert_called_once_with(token=self.AUTH_TOKEN,
                                         endpoint_url=self.ENDPOINT_URL)

    def test_delete_policy_target_group(self, mock_obj):
        instance = mock_obj.return_value
        obj = instance.delete_policy_target_group('policy_target_id')
        retval = self.gbp_obj.delete_policy_target_group(self.AUTH_TOKEN,
                                                         'policy_target_group_id')
        print retval
        self.assertEqual(retval, obj)
        mock_obj.assert_called_once_with(token=self.AUTH_TOKEN,
                                         endpoint_url=self.ENDPOINT_URL)

    def test_create_l2_policy(self, mock_obj):
        instance = mock_obj.return_value
        obj = instance.create_l2_policy(body=
                                        'l2_policy_info')['l2_policy']
        retval = self.gbp_obj.create_l2_policy(self.AUTH_TOKEN,
                                               self.TENANT_ID,
                                               'name',
                                               l3_policy_id=None)
        print retval
        self.assertEqual(retval, obj)
        mock_obj.assert_called_once_with(token=self.AUTH_TOKEN,
                                         endpoint_url=self.ENDPOINT_URL)

    def test_delete_l2_policy(self, mock_obj):
        instance = mock_obj.return_value
        obj = instance.delete_l2_policy('l2_policy_id')
        retval = self.gbp_obj.delete_l2_policy(self.AUTH_TOKEN,
                                               'l2_policy_id')
        print retval
        self.assertEqual(retval, obj)
        mock_obj.assert_called_once_with(token=self.AUTH_TOKEN,
                                         endpoint_url=self.ENDPOINT_URL)

    def test_get_l2_policys(self, mock_obj):
        instance = mock_obj.return_value
        obj = instance.list_l2_policies({})['l2_policies']
        retval = self.gbp_obj.get_l2_policys(self.AUTH_TOKEN,
                                             filters={})
        print retval
        self.assertEqual(retval, obj)
        mock_obj.assert_called_once_with(token=self.AUTH_TOKEN,
                                         endpoint_url=self.ENDPOINT_URL)

    def test_get_l2_policy(self, mock_obj):
        instance = mock_obj.return_value
        obj = instance.show_l2_policy(
            'policy_id', {})['l2_policy']
        retval = self.gbp_obj.get_l2_policy(self.AUTH_TOKEN,
                                            'policy_id',
                                            filters={})
        print retval
        self.assertEqual(retval, obj)
        mock_obj.assert_called_once_with(token=self.AUTH_TOKEN,
                                         endpoint_url=self.ENDPOINT_URL)

    def test_create_network_service_policy(self, mock_obj):
        instance = mock_obj.return_value
        obj = instance.create_network_service_policy(
            body='network_service_policy_info')['network_service_policy']
        retval = self.gbp_obj.create_network_service_policy(self.AUTH_TOKEN,
                                                            'network_service_policy_info')
        print retval
        self.assertEqual(retval, obj)
        mock_obj.assert_called_once_with(token=self.AUTH_TOKEN,
                                         endpoint_url=self.ENDPOINT_URL)

    def test_get_network_service_policies(self, mock_obj):
        instance = mock_obj.return_value
        obj = instance.list_network_service_policies({})['network_service_policies']
        retval = self.gbp_obj.get_network_service_policies(self.AUTH_TOKEN,
                                                           filters={})
        print retval
        self.assertEqual(retval, obj)
        mock_obj.assert_called_once_with(token=self.AUTH_TOKEN,
                                         endpoint_url=self.ENDPOINT_URL)

    def test_get_external_policies(self, mock_obj):
        instance = mock_obj.return_value
        obj = instance.list_external_policies({})['external_policies']
        retval = self.gbp_obj.get_external_policies(self.AUTH_TOKEN,
                                                    filters={})
        print retval
        self.assertEqual(retval, obj)
        mock_obj.assert_called_once_with(token=self.AUTH_TOKEN,
                                         endpoint_url=self.ENDPOINT_URL)

    def test_get_policy_rule_sets(self, mock_obj):
        instance = mock_obj.return_value
        obj = instance.list_policy_rule_sets({})['policy_rule_sets']
        retval = self.gbp_obj.get_policy_rule_sets(self.AUTH_TOKEN,
                                                   filters={})
        print retval
        self.assertEqual(retval, obj)
        mock_obj.assert_called_once_with(token=self.AUTH_TOKEN,
                                         endpoint_url=self.ENDPOINT_URL)

    def test_get_policy_actions(self, mock_obj):
        instance = mock_obj.return_value
        obj = instance.list_policy_actions({})['policy_actions']
        retval = self.gbp_obj.get_policy_actions(self.AUTH_TOKEN,
                                                 filters={})
        print retval
        self.assertEqual(retval, obj)
        mock_obj.assert_called_once_with(token=self.AUTH_TOKEN,
                                         endpoint_url=self.ENDPOINT_URL)

    def test_get_policy_rules(self, mock_obj):
        instance = mock_obj.return_value
        obj = instance.list_policy_rules({})['policy_rules']
        retval = self.gbp_obj.get_policy_rules(self.AUTH_TOKEN,
                                               filters={})
        print retval
        self.assertEqual(retval, obj)
        mock_obj.assert_called_once_with(token=self.AUTH_TOKEN,
                                         endpoint_url=self.ENDPOINT_URL)

    def test_create_l3_policy(self, mock_obj):
        instance = mock_obj.return_value
        obj = instance.create_l3_policy(
            body='l3_policy_info')['l3_policy']
        retval = self.gbp_obj.create_l3_policy(self.AUTH_TOKEN,
                                               'l3_policy_info')
        print retval
        self.assertEqual(retval, obj)
        mock_obj.assert_called_once_with(token=self.AUTH_TOKEN,
                                         endpoint_url=self.ENDPOINT_URL)

    def test_get_l3_policy(self, mock_obj):
        instance = mock_obj.return_value
        obj = instance.show_l3_policy('policy_id',
                                      {})['l3_policy']
        retval = self.gbp_obj.get_l3_policy(self.AUTH_TOKEN,
                                            'policy_id',
                                            filters={})
        print retval
        self.assertEqual(retval, obj)
        mock_obj.assert_called_once_with(token=self.AUTH_TOKEN,
                                         endpoint_url=self.ENDPOINT_URL)

    def test_get_l3_policies(self, mock_obj):
        instance = mock_obj.return_value
        obj = instance.list_l3_policies({})['l3_policy']
        retval = self.gbp_obj.get_l3_policies(self.AUTH_TOKEN,
                                              filters={})
        print retval
        self.assertEqual(retval, obj)
        mock_obj.assert_called_once_with(token=self.AUTH_TOKEN,
                                         endpoint_url=self.ENDPOINT_URL)

    def test_get_policy_targets(self, mock_obj):
        instance = mock_obj.return_value
        obj = instance.list_policy_targets({})['policy_targets']
        retval = self.gbp_obj.get_policy_targets(self.AUTH_TOKEN,
                                                 filters={})
        print retval
        self.assertEqual(retval, obj)
        mock_obj.assert_called_once_with(token=self.AUTH_TOKEN,
                                         endpoint_url=self.ENDPOINT_URL)

    def test_list_pt(self, mock_obj):
        instance = mock_obj.return_value
        obj = instance.list_policy_targets({})['policy_targets']
        retval = self.gbp_obj.list_pt(self.AUTH_TOKEN,
                                      filters={})
        print retval
        self.assertEqual(retval, obj)
        mock_obj.assert_called_once_with(token=self.AUTH_TOKEN,
                                         endpoint_url=self.ENDPOINT_URL)

    def test_get_policy_target(self, mock_obj):
        instance = mock_obj.return_value
        obj = instance.show_policy_target('pt_id',
                                          {})['policy_target']
        retval = self.gbp_obj.get_policy_target(self.AUTH_TOKEN,
                                                'pt_id',
                                                filters={})
        print retval
        self.assertEqual(retval, obj)
        mock_obj.assert_called_once_with(token=self.AUTH_TOKEN,
                                         endpoint_url=self.ENDPOINT_URL)

    def test_get_service_profile(self, mock_obj):
        instance = mock_obj.return_value
        obj = instance.show_service_profile(
            'service_profile_id')['service_profile']
        retval = self.gbp_obj.get_service_profile(self.AUTH_TOKEN,
                                                  'service_profile_id')
        print retval
        self.assertEqual(retval, obj)
        mock_obj.assert_called_once_with(token=self.AUTH_TOKEN,
                                         endpoint_url=self.ENDPOINT_URL)

    def test_get_servicechain_node(self, mock_obj):
        instance = mock_obj.return_value
        obj = instance.show_servicechain_node(
            'node_id')['servicechain_node']
        retval = self.gbp_obj.get_servicechain_node(self.AUTH_TOKEN,
                                                    'node_id')
        print retval
        self.assertEqual(retval, obj)
        mock_obj.assert_called_once_with(token=self.AUTH_TOKEN,
                                         endpoint_url=self.ENDPOINT_URL)

    def test_get_servicechain_instance(self, mock_obj):
        instance = mock_obj.return_value
        obj = instance.show_servicechain_instance(
            'instance_id')['servicechain_instance']
        retval = self.gbp_obj.get_servicechain_instance(self.AUTH_TOKEN,
                                                        'instance_id')
        print retval
        self.assertEqual(retval, obj)
        mock_obj.assert_called_once_with(token=self.AUTH_TOKEN,
                                         endpoint_url=self.ENDPOINT_URL)
