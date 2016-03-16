import mock
from mock import patch
import unittest

from gbpservice.nfp.orchestrator.drivers import (
    vyos_orchestration_driver
)


OPENSTACK_DRIVER_CLASS_PATH = ('gbpservice.nfp.orchestrator'
                               '.openstack.openstack_driver')


@patch(OPENSTACK_DRIVER_CLASS_PATH + '.KeystoneClient.__init__',
       mock.MagicMock(return_value=None))
@patch(OPENSTACK_DRIVER_CLASS_PATH + '.NovaClient.__init__',
       mock.MagicMock(return_value=None))
@patch(OPENSTACK_DRIVER_CLASS_PATH + '.GBPClient.__init__',
       mock.MagicMock(return_value=None))
@patch(OPENSTACK_DRIVER_CLASS_PATH + '.NeutronClient.__init__',
       mock.MagicMock(return_value=None))
class VyosOrchestrationDriverTestCase(unittest.TestCase):

    def test_get_nfd_sharing_info_when_device_sharing_unsupported(self):
        driver = vyos_orchestration_driver.VyosOrchestrationDriver(
                        supports_device_sharing=False)
        self.assertIsNone(driver.get_network_function_device_sharing_info(
                                                                        None))

    def test_get_network_function_device_sharing_info(self):
        driver = vyos_orchestration_driver.VyosOrchestrationDriver(
                        supports_device_sharing=True,
                        supports_hotplug=True)
        device_data = {'tenant_id': 'tenant_id',
                       'service_vendor': 'service_vendor'}
        reply = driver.get_network_function_device_sharing_info(device_data)
        self.assertIsInstance(reply['filters'], dict,
                              msg=('Return value of'
                                   ' get_network_function_device_sharing_info'
                                   ' is not dict'))
        for k, v in reply['filters'].iteritems():
            self.assertIsInstance(v, list,
                                  msg=("The type of the value for key %s"
                                       " in the returned filters is not list"
                                       % (k)))

    def test_select_network_function_device_when_device_sharing_unsupported(
                                                                        self):
        driver = vyos_orchestration_driver.VyosOrchestrationDriver(
                        supports_device_sharing=False)
        self.assertIsNone(driver.select_network_function_device(None, None))

    def test_select_network_function_device(self):
        driver = vyos_orchestration_driver.VyosOrchestrationDriver(
                        supports_device_sharing=True,
                        supports_hotplug=True,
                        max_interfaces=10)

        # test to get device when max interfaces is permissible
        devices = [
                   {'id': '1',
                    'interfaces_in_use': 9}
                   ]
        device_data = {'ports': [{'id': '2',
                                  'port_classification': 'provider',
                                  'port_model': 'gbp'}]
                       }
        self.assertIsNotNone(driver.select_network_function_device(
                                                                devices,
                                                                device_data),
                             msg=('Device sharing is broken with respect to'
                                  ' maximum interfaces that'
                                  ' the device supports'))

        # test to get device when max interfaces is not permissible
        device_data['ports'].append({'id': '3',
                                     'port_classification': 'consumer',
                                     'port_model': 'gbp'})
        self.assertIsNone(driver.select_network_function_device(devices,
                                                                device_data),
                          msg=('Device sharing is broken with respect to'
                               ' maximum interfaces that'
                               ' the device supports'))

    def test_create_network_function_device(self):
        driver = vyos_orchestration_driver.VyosOrchestrationDriver(
                        supports_device_sharing=True,
                        supports_hotplug=True,
                        max_interfaces=10)

        # Monkey patch the methods
        driver.identity_handler.get_admin_token = mock.MagicMock(
                                                        return_value='token')
        driver.identity_handler.get_tenant_id = mock.MagicMock(
                                                            return_value='8')
        driver.identity_handler.get_keystone_creds = mock.MagicMock(
                                    return_value=(None, None, 'admin', None))
        driver.network_handler_gbp.create_policy_target = mock.MagicMock(
                                                return_value={'id': '5'})
        driver.network_handler_neutron.create_port = mock.MagicMock(
                                                return_value={'id': '5'})
        driver.compute_handler_nova.get_image_id = mock.MagicMock(
                                                return_value='6')
        driver.network_handler_gbp.get_policy_target = mock.MagicMock(
                                                return_value={'port_id': '7'})
        driver.compute_handler_nova.create_instance = mock.MagicMock(
                                                return_value='8')
        driver.network_handler_gbp.delete_policy_target = mock.MagicMock(
                                                return_value=None)
        driver.network_handler_neutron.delete_port = mock.MagicMock(
                                                return_value=None)
        driver.network_handler_neutron.get_port = mock.MagicMock(
                return_value={
                    'port': {
                        'fixed_ips': [{'ip_address': '0.0.0.0'}]
                    }
                })

        # test for create device when interface hotplug is enabled
        device_data = {'tenant_id': '1',
                       'network_model': 'gbp',
                       'service_vendor': 'vyos',
                       'management_network_info': {'id': '2'},
                       'compute_policy': 'xyz',
                       'ports': [{'id': '3',
                                  'port_model': 'gbp',
                                  'port_classification': 'provider'},
                                 {'id': '4',
                                  'port_model': 'gbp',
                                  'port_classification': 'consumer'}]}
        self.assertRaises(Exception,
                          driver.create_network_function_device,
                          device_data)
        device_data['compute_policy'] = 'nova'
        self.assertIsInstance(driver.create_network_function_device(
                                                                device_data),
                              dict,
                              msg=('Return value from the'
                                   ' create_network_function_device call'
                                   ' is not a dictionary'))

        # test for create device along with provider port
        driver.supports_hotplug = False
        self.assertIsInstance(driver.create_network_function_device(
                                                                device_data),
                              dict,
                              msg=('Return value from the'
                                   ' create_network_function_device call'
                                   ' is not a dictionary'))

    def test_delete_network_function_device(self):
        driver = vyos_orchestration_driver.VyosOrchestrationDriver(
                        supports_device_sharing=True,
                        supports_hotplug=True,
                        max_interfaces=10)

        # Monkey patch the methods
        driver.identity_handler.get_admin_token = mock.MagicMock(
                                                        return_value='token')
        driver.identity_handler.get_tenant_id = mock.MagicMock(
                                                            return_value='8')
        driver.identity_handler.get_keystone_creds = mock.MagicMock(
                                    return_value=(None, None, 'admin', None))
        driver.compute_handler_nova.delete_instance = mock.MagicMock(
                                                        return_value=None)
        driver.network_handler_gbp.delete_policy_target = mock.MagicMock(
                                                return_value=None)
        driver.network_handler_neutron.delete_port = mock.MagicMock(
                                                return_value=None)

        device_data = {'id': '1',
                       'tenant_id': '2',
                       'compute_policy': 'xyz',
                       'mgmt_port_id': {'id': '3',
                                        'port_model': 'gbp',
                                        'port_classification': 'mgmt'}}
        driver.stats['instances'] = 1
        driver.stats['management_interfaces'] = 1
        self.assertRaises(Exception,
                          driver.delete_network_function_device,
                          device_data)
        device_data['compute_policy'] = 'nova'
        self.assertIsNone(driver.delete_network_function_device(device_data))

    def test_get_network_function_device_status(self):
        driver = vyos_orchestration_driver.VyosOrchestrationDriver(
                        supports_device_sharing=True,
                        supports_hotplug=True,
                        max_interfaces=10)

        # Monkey patch the methods
        driver.identity_handler.get_admin_token = mock.MagicMock(
                                                        return_value='token')
        driver.identity_handler.get_tenant_id = mock.MagicMock(
                                                            return_value='8')
        driver.identity_handler.get_keystone_creds = mock.MagicMock(
                                    return_value=(None, None, 'admin', None))
        driver.compute_handler_nova.get_instance = mock.MagicMock(
                                            return_value={'status': 'ACTIVE'})

        device_data = {'id': '1',
                       'tenant_id': '2',
                       'compute_policy': 'xyz'}
        self.assertRaises(Exception,
                          driver.get_network_function_device_status,
                          device_data)
        device_data['compute_policy'] = 'nova'

        # self.assertTrue(driver.is_device_up(device_data))
        self.assertTrue(
                driver.get_network_function_device_status(device_data) ==
                'ACTIVE')

    def test_plug_network_function_device_interfaces(self):
        driver = vyos_orchestration_driver.VyosOrchestrationDriver(
                supports_device_sharing=True,
                supports_hotplug=False,
                max_interfaces=10)

        # Monkey patch the methods
        driver.identity_handler.get_admin_token = mock.MagicMock(
                                                        return_value='token')
        driver.identity_handler.get_tenant_id = mock.MagicMock(
                                                            return_value='8')
        driver.identity_handler.get_keystone_creds = mock.MagicMock(
                                    return_value=(None, None, 'admin', None))
        driver.network_handler_neutron.update_port = mock.MagicMock(
                                                        return_value=None)
        driver.compute_handler_nova.attach_interface = mock.MagicMock(
                                                        return_value=None)
        driver.network_handler_gbp.get_policy_target = mock.MagicMock(
                                                return_value={'port_id': '7'})

        self.assertRaises(Exception,
                          driver.plug_network_function_device_interfaces, None)

        driver.supports_hotplug = True

        device_data = {'id': '1',
                       'tenant_id': '2',
                       'compute_policy': 'xyz',
                       'ports': [{'id': '3',
                                  'port_model': 'gbp',
                                  'port_classification': 'provider'},
                                 {'id': '4',
                                  'port_model': 'neutron',
                                  'port_classification': 'consumer'}]}
        self.assertRaises(Exception,
                          driver.plug_network_function_device_interfaces,
                          device_data)

        device_data['compute_policy'] = 'nova'

        self.assertTrue(driver.plug_network_function_device_interfaces(
                                                                device_data),
                        msg='')

    def test_unplug_network_function_device_interfaces(self):
        driver = vyos_orchestration_driver.VyosOrchestrationDriver(
                supports_device_sharing=True,
                supports_hotplug=False,
                max_interfaces=10)

        # Monkey patch the methods
        driver.identity_handler.get_admin_token = mock.MagicMock(
                                                        return_value='token')
        driver.identity_handler.get_tenant_id = mock.MagicMock(
                                                            return_value='8')
        driver.identity_handler.get_keystone_creds = mock.MagicMock(
                                    return_value=(None, None, 'admin', None))
        driver.network_handler_neutron.update_port = mock.MagicMock(
                                                        return_value=None)
        driver.compute_handler_nova.detach_interface = mock.MagicMock(
                                                        return_value=None)
        driver.network_handler_gbp.get_policy_target = mock.MagicMock(
                                                return_value={'port_id': '7'})

        self.assertRaises(Exception,
                          driver.unplug_network_function_device_interfaces,
                          None)

        driver.supports_hotplug = True

        device_data = {'id': '1',
                       'tenant_id': '2',
                       'compute_policy': 'xyz',
                       'ports': [{'id': '3',
                                  'port_model': 'gbp',
                                  'port_classification': 'provider'},
                                 {'id': '4',
                                  'port_model': 'neutron',
                                  'port_classification': 'consumer'}]}
        self.assertRaises(Exception,
                          driver.unplug_network_function_device_interfaces,
                          device_data)

        device_data['compute_policy'] = 'nova'

        self.assertTrue(driver.unplug_network_function_device_interfaces(
                                                                device_data),
                        msg='')

    def test_get_network_function_device_healthcheck_info(self):
        driver = vyos_orchestration_driver.VyosOrchestrationDriver(
                supports_device_sharing=True,
                supports_hotplug=False,
                max_interfaces=10)

        device_data = {'id': '1',
                       'mgmt_ip_address': 'a.b.c.d'}

        self.assertIsInstance(
            driver.get_network_function_device_healthcheck_info(device_data),
            dict, msg='')

    def test_get_network_function_device_config_info(self):
        driver = vyos_orchestration_driver.VyosOrchestrationDriver(
                supports_device_sharing=True,
                supports_hotplug=False,
                max_interfaces=10)

        # Monkey patch the methods
        driver.identity_handler.get_admin_token = mock.MagicMock(
                                                        return_value='token')
        driver.network_handler_gbp.get_policy_target = mock.MagicMock(
                                                return_value={'port_id': '7'})
        driver.network_handler_neutron.get_port = mock.MagicMock(
                            return_value={'port': {
                                            'mac_address': 'aa:bb:cc:dd:ee:ff',
                                            'fixed_ips': [
                                                {
                                                    'ip_address': 'p.q.r.s',
                                                    'subnet_id': '8'
                                                }
                                            ]
                                        }})
        driver.network_handler_neutron.get_subnet = mock.MagicMock(
                            return_value={'subnet': {
                                            'cidr': 'p.q.r.s/t',
                                            'gateway_ip': 'p.q.r.1'
                                        }})

        device_data = {'service_vendor': 'vyos',
                       'mgmt_ip_address': 'a.b.c.d',
                       'ports': [{'id': '3',
                                  'port_model': 'gbp',
                                  'port_classification': 'provider'}],
                       'service_type': 'firewall',
                       'network_function_id': '4',
                       'tenant_id': '5'}

        reply = driver.get_network_function_device_config_info(device_data)
        self.assertIsInstance(reply, dict, msg='')
        self.assertTrue('info' in reply)
        self.assertTrue('version' in reply['info'])
        self.assertTrue('config' in reply)


if __name__ == '__main__':
    unittest.main()
