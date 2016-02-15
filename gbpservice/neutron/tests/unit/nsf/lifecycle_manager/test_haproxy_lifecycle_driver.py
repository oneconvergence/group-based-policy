import mock
from mock import patch
import unittest

from gbpservice.neutron.nsf.lifecycle_manager.drivers import (
    haproxy_lifecycle_driver
)


OPENSTACK_DRIVER_CLASS_PATH = ('gbpservice.neutron.nsf.lifecycle_manager'
                               '.openstack.openstack_driver')


@patch(OPENSTACK_DRIVER_CLASS_PATH + '.KeystoneClient.__init__',
       mock.MagicMock(return_value=None))
@patch(OPENSTACK_DRIVER_CLASS_PATH + '.NovaClient.__init__',
       mock.MagicMock(return_value=None))
@patch(OPENSTACK_DRIVER_CLASS_PATH + '.GBPClient.__init__',
       mock.MagicMock(return_value=None))
@patch(OPENSTACK_DRIVER_CLASS_PATH + '.NeutronClient.__init__',
       mock.MagicMock(return_value=None))
class HaproxyLifecycleDriverTestCase(unittest.TestCase):

    def test_is_device_sharing_supproted_when_hotplug_unsupported(self):
        driver = haproxy_lifecycle_driver.HaproxyLifeCycleDriver(
                        supports_device_sharing=True,
                        supports_hotplug=False)
        self.assertFalse(driver.is_device_sharing_supported(None))

    def test_is_device_sharing_supproted_when_hotplug_supported(self):
        driver = haproxy_lifecycle_driver.HaproxyLifeCycleDriver(
                        supports_device_sharing=True,
                        supports_hotplug=True)
        self.assertTrue(driver.is_device_sharing_supported(None))

    def test_get_device_filters_for_sharing_when_device_sharing_unsupported(
                                                                self):
        driver = haproxy_lifecycle_driver.HaproxyLifeCycleDriver(
                        supports_device_sharing=False)
        self.assertRaises(Exception,
                          driver.get_device_filters_for_sharing,
                          None)

    def test_get_device_filters_for_sharing(self):
        driver = haproxy_lifecycle_driver.HaproxyLifeCycleDriver(
                        supports_device_sharing=True,
                        supports_hotplug=True)
        device_data = {'tenant_id': 'tenant_id',
                       'service_vendor': 'service_vendor'}
        reply = driver.get_device_filters_for_sharing(device_data)
        self.assertIsInstance(reply, dict,
                              msg=('Return value of'
                                   ' get_device_filters_for_sharing'
                                   ' is not dict'))
        for k, v in reply.iteritems():
            self.assertIsInstance(v, list,
                                  msg=("The type of the value for key %s"
                                       "in the returned filters is not list"
                                       % (k)))

    def test_get_device_to_reuse_when_device_sharing_unsupported(self):
        driver = haproxy_lifecycle_driver.HaproxyLifeCycleDriver(
                        supports_device_sharing=False)
        self.assertRaises(Exception,
                          driver.get_device_to_reuse,
                          None,
                          None)

    def test_get_device_to_reuse(self):
        driver = haproxy_lifecycle_driver.HaproxyLifeCycleDriver(
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
                                  'port_policy': 'gbp'}]
                       }
        self.assertIsNotNone(driver.get_device_to_reuse(devices, device_data),
                             msg=('Device sharing is broken with respect to'
                                  ' maximum interfaces that'
                                  ' the device supports'))

        # test to get device when max interfaces is not permissible
        device_data['ports'].append({'id': '3',
                                     'port_classification': 'consumer',
                                     'port_policy': 'gbp'})
        self.assertIsNone(driver.get_device_to_reuse(devices, device_data),
                          msg=('Device sharing is broken with respect to'
                               ' maximum interfaces that'
                               ' the device supports'))

    def test_create_device(self):
        driver = haproxy_lifecycle_driver.HaproxyLifeCycleDriver(
                        supports_device_sharing=True,
                        supports_hotplug=True,
                        max_interfaces=10)

        # Monkey patch the methods
        driver.identity_handler.get_admin_token = mock.MagicMock(
                                                        return_value='token')
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
                       'network_policy': 'gbp',
                       'management_network_info': {'id': '2'},
                       'compute_policy': 'xyz'}
        self.assertRaises(Exception,
                          driver.create_device,
                          device_data)
        device_data['compute_policy'] = 'nova'
        self.assertIsInstance(driver.create_device(device_data), dict,
                              msg=('Return value from the create_device call'
                                   ' is not a dictionary'))

        # test for create device along with provider port
        device_data.update({'ports': [{'id': '3',
                                       'port_policy': 'gbp',
                                       'port_classification': 'provider'},
                                      {'id': '4',
                                       'port_policy': 'gbp',
                                       'port_classification': 'consumer'}]})
        driver.supports_hotplug = False
        self.assertIsInstance(driver.create_device(device_data), dict,
                              msg=('Return value from the create_device call'
                                   ' is not a dictionary'))

    def test_delete_device(self):
        driver = haproxy_lifecycle_driver.HaproxyLifeCycleDriver(
                        supports_device_sharing=True,
                        supports_hotplug=True,
                        max_interfaces=10)

        # Monkey patch the methods
        driver.identity_handler.get_admin_token = mock.MagicMock(
                                                        return_value='token')
        driver.compute_handler_nova.delete_instance = mock.MagicMock(
                                                        return_value=None)
        driver.network_handler_gbp.delete_policy_target = mock.MagicMock(
                                                return_value=None)
        driver.network_handler_neutron.delete_port = mock.MagicMock(
                                                return_value=None)

        device_data = {'id': '1',
                       'tenant_id': '2',
                       'compute_policy': 'xyz',
                       'mgmt_data_ports': [{'id': '3',
                                            'port_policy': 'gbp',
                                            'port_classification': 'mgmt'}]}
        self.assertRaises(Exception,
                          driver.delete_device,
                          device_data)
        device_data['compute_policy'] = 'nova'
        self.assertIsNone(driver.delete_device(device_data))

    def test_is_device_up(self):
        driver = haproxy_lifecycle_driver.HaproxyLifeCycleDriver(
                        supports_device_sharing=True,
                        supports_hotplug=True,
                        max_interfaces=10)

        # Monkey patch the methods
        driver.identity_handler.get_admin_token = mock.MagicMock(
                                                        return_value='token')
        driver.compute_handler_nova.get_instance = mock.MagicMock(
                                            return_value={'status': 'ACTIVE'})

        device_data = {'id': '1',
                       'tenant_id': '2',
                       'compute_policy': 'xyz'}
        self.assertRaises(Exception, driver.is_device_up, device_data)
        device_data['compute_policy'] = 'nova'

        self.assertTrue(driver.is_device_up(device_data))

        driver.compute_handler_nova.get_instance = mock.MagicMock(
                                            return_value={'status': 'BOOTING'})

        self.assertFalse(driver.is_device_up(device_data))

    def test_plug_interfaces(self):
        driver = haproxy_lifecycle_driver.HaproxyLifeCycleDriver(
                supports_device_sharing=True,
                supports_hotplug=False,
                max_interfaces=10)

        # Monkey patch the methods
        driver.identity_handler.get_admin_token = mock.MagicMock(
                                                        return_value='token')
        driver.compute_handler_nova.attach_interface = mock.MagicMock(
                                                        return_value=None)
        driver.network_handler_gbp.get_policy_target = mock.MagicMock(
                                                return_value={'port_id': '7'})

        self.assertRaises(Exception, driver.plug_interfaces, None)

        driver.supports_hotplug = True

        device_data = {'id': '1',
                       'tenant_id': '2',
                       'compute_policy': 'xyz',
                       'ports': [{'id': '3',
                                  'port_policy': 'gbp',
                                  'port_classification': 'provider'},
                                 {'id': '4',
                                  'port_policy': 'neutron',
                                  'port_classification': 'consumer'}]}
        self.assertRaises(Exception, driver.plug_interfaces, device_data)

        device_data['compute_policy'] = 'nova'

        self.assertTrue(driver.plug_interfaces(device_data),
                        msg='')

    def test_unplug_interfaces(self):
        driver = haproxy_lifecycle_driver.HaproxyLifeCycleDriver(
                supports_device_sharing=True,
                supports_hotplug=False,
                max_interfaces=10)

        # Monkey patch the methods
        driver.identity_handler.get_admin_token = mock.MagicMock(
                                                        return_value='token')
        driver.compute_handler_nova.detach_interface = mock.MagicMock(
                                                        return_value=None)
        driver.network_handler_gbp.get_policy_target = mock.MagicMock(
                                                return_value={'port_id': '7'})

        self.assertRaises(Exception, driver.unplug_interfaces, None)

        driver.supports_hotplug = True

        device_data = {'id': '1',
                       'tenant_id': '2',
                       'compute_policy': 'xyz',
                       'ports': [{'id': '3',
                                  'port_policy': 'gbp',
                                  'port_classification': 'provider'},
                                 {'id': '4',
                                  'port_policy': 'neutron',
                                  'port_classification': 'consumer'}]}
        self.assertRaises(Exception, driver.unplug_interfaces, device_data)

        device_data['compute_policy'] = 'nova'

        self.assertTrue(driver.unplug_interfaces(device_data),
                        msg='')

    def test_get_device_healthcheck_params(self):
        driver = haproxy_lifecycle_driver.HaproxyLifeCycleDriver(
                supports_device_sharing=True,
                supports_hotplug=False,
                max_interfaces=10)

        device_data = {'id': '1',
                       'mgmt_ip_address': 'a.b.c.d'}

        self.assertIsInstance(driver.get_device_healthcheck_params(
                                                                device_data),
                              dict, msg='')


if __name__ == '__main__':
    unittest.main()
