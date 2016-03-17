import filter_base
from gbpservice.nfp.configurator.lib import data_filter
from gbpservice.nfp.configurator.lib import filter_constants as constants
import mock


class FilterTest(filter_base.BaseTestCase):
    def __init__(self, *args, **kwargs):
        super(FilterTest, self).__init__(*args, **kwargs)

    def setUp(self):
        self.context = {}
        self.filter_obj = data_filter.Filter(None, None)

    def tearDown(self):
        self.context = {}

    def _make_test(self, context, method, **filters):
        ''' To reduce the boilerplate. '''
        retval = self.filter_obj.call(self.context,
                                      self.filter_obj.make_msg(method,
                                                               **filters))
        return retval

    def _make_vpn_service_context(self):
        ''' to make the context for the vpn service '''
        service_info = self._test_get_vpn_info()
        self.context['service_info'] = service_info
        return self.context

    def _make_lb_service_context(self):
        ''' to make the context for the lb service '''
        service_info = self._test_get_lb_info()
        self.context['service_info'] = service_info
        return self.context

    def _make_fw_service_context(self):
        ''' this will be used when fw comes in picture '''
        service_info = self._test_get_fw_info()
        self.context['service_info'] = service_info
        return self.context

    def test_make_msg(self):

        retval = self.filter_obj.make_msg('get_logical_device',
                                          pool_id=self.pools[0]['id'])
        self.assertEqual(retval, {'method': 'get_logical_device',
                                  'args': {'pool_id': self.pools[0]['id']}})

    def test_make_msg_empty(self):

        retval = self.filter_obj.make_msg('get_logical_device')
        self.assertEqual(retval, {'args': {}, 'method': 'get_logical_device'})

    def test_call(self):
        with mock.patch.object(self.filter_obj, "call") as call_mock:
            call_mock.return_value = True
            retval = self._make_test(self._make_lb_service_context(),
                                     'get_logical_device',
                                     pool_id=[self.pools[0]['id']])
            self.assertEqual(retval, True)

    def test_get_vpn_service_with_tenantid(self):
        retval = self._make_test(self._make_vpn_service_context(),
                                 'get_vpn_services',
                                 filters=(
                            {'tenant_id': [self.vpnservices[0]['tenant_id']]}))

        self.assertEqual(retval, [self.vpnservices[0], self.vpnservices[1]])

    def test_get_vpn_service_with_ids(self):
        retval = self._make_test(self._make_vpn_service_context(),
                                 'get_vpn_services',
                                 ids=[self.vpnservices[0]['id'],
                                      self.vpnservices[1]['id']])
        self.assertEqual(retval, [self.vpnservices[0], self.vpnservices[1]])

    def test_get_ipsec_conns(self):
        retval = self._make_test(
                self._make_vpn_service_context(),
                'get_ipsec_conns',
                tenant_id=[self.ipsec_site_connections[0]['tenant_id']],
                peer_address=[self.ipsec_site_connections[0]['peer_address']])
        self.assertEqual(retval, self.ipsec_site_connections)

    def test_get_ssl_vpn_conn(self):

        retval = self._make_test(
                    self._make_vpn_service_context(),
                    'get_ssl_vpn_conns',
                    tenant_id=[self.ssl_vpn_connections[0]['tenant_id']])
        self.assertEqual(retval, self.ssl_vpn_connections)

    def test_get_logical_device(self):

        retval = self._make_test(self._make_lb_service_context(),
                                 'get_logical_device',
                                 pool_id=self.pools[0]['id'])

        self.ports[0]['fixed_ips'] = self.subnets[1]
        self.vips[0]['port'] = self.ports[0]
        expected = {'pool': self.pools[0],
                    'vip': self.vips[0],
                    'members': self.members[0],
                    'healthmonitors': {}
                    }
        self.assertNotEqual(retval, expected)

    def test_get_vpn_servicecontext_ipsec_service_type(self):

        service_info = self._test_get_vpn_info()
        self.context['service_info'] = service_info
        retval = self.filter_obj.get_vpn_servicecontext(
                    self.context,
                    constants.SERVICE_TYPE_IPSEC,
                    {'tenant_id': self.vpnservices[0]['tenant_id'],
                     'vpnservice_id': self.vpnservices[0]['id'],
                     'ipsec_site_connections':
                     self.ipsec_site_connections[0]['id']})

        expected = {'service': self.vpnservices[0],
                    'siteconns': [{'connection':
                                   self.ipsec_site_connections[0],
                                   'ikepolicy': self.ikepolicies[0],
                                   'ipsecpolicy': self.ipsecpolicies[0]
                                   }]}

        self.assertEqual(retval, [expected])

    def test_get_vpn_servicecontext_ipsec_service_type_with_tenantid(self):

        service_info = self._test_get_vpn_info()
        self.context['service_info'] = service_info
        retval = self.filter_obj.get_vpn_servicecontext(
                    self.context,
                    constants.SERVICE_TYPE_IPSEC,
                    {'tenant_id': self.vpnservices[0]['tenant_id'],
                     })

        expected = {'service': self.vpnservices[0],
                    'siteconns': [{'connection':
                                   self.ipsec_site_connections[0],
                                   'ikepolicy': self.ikepolicies[0],
                                   'ipsecpolicy': self.ipsecpolicies[0]
                                   }]}

        self.assertEqual(retval, [expected])

    def test_get_vpn_servicecontext_openvpn_service_type(self):

        service_info = self._test_get_vpn_info()
        self.context['service_info'] = service_info
        retval = self.filter_obj.get_vpn_servicecontext(
                        self.context,
                        constants.SERVICE_TYPE_OPENVPN,
                        {'tenant_id': self.vpnservices[0]['tenant_id'],
                         'vpnservice_id': self.vpnservices[0]['id'],
                         'ipsec_site_connections':
                         self.ipsec_site_connections[0]['id']})
        expected = {
                     'sslvpnconns': [{
                            'credential': None,
                            'connection': self.ssl_vpn_connections[0]}],
                     'service': self.vpnservices[0]}
        self.assertEqual(retval, [expected])

    def test_get_vpn_servicecontext_openvpn_service_type_with_tenantid(self):

        service_info = self._test_get_vpn_info()
        self.context['service_info'] = service_info
        retval = self.filter_obj.get_vpn_servicecontext(
                        self.context,
                        constants.SERVICE_TYPE_OPENVPN,
                        {'tenant_id': self.vpnservices[0]['tenant_id']})
        expected = {
                     'sslvpnconns': [{
                            'credential': None,
                            'connection': self.ssl_vpn_connections[0]}],
                     'service': self.vpnservices[0]}
        self.assertEqual(retval, [expected])

    def test_get_vpn_servicecontext_openvpn_service_type_with_vpnsid(self):

        service_info = self._test_get_vpn_info()
        self.context['service_info'] = service_info
        retval = self.filter_obj.get_vpn_servicecontext(
                        self.context,
                        constants.SERVICE_TYPE_OPENVPN,
                        {'vpnservice_id': self.vpnservices[0]['id']})
        expected = {
                     'sslvpnconns': [{
                            'credential': None,
                            'connection': self.ssl_vpn_connections[0]}],
                     'service': self.vpnservices[0]}
        self.assertEqual(retval, [expected])

    def test_get_vpn_servicecontext_openvpn_service_type_with_ipsec(self):

        service_info = self._test_get_vpn_info()
        self.context['service_info'] = service_info
        retval = self.filter_obj.get_vpn_servicecontext(
                        self.context,
                        constants.SERVICE_TYPE_OPENVPN,
                        {
                         'ipsec_site_connections':
                                    self.ipsec_site_connections[0]['id']
                        })
        expected = {
                     'sslvpnconns': [{
                            'credential': None,
                            'connection': self.ssl_vpn_connections[0]}],
                     'service': self.vpnservices[0]}
        self.assertEqual(retval, [expected])

