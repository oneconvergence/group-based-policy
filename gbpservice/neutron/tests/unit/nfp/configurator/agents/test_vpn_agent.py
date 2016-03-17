from gbpservice.nfp.configurator.agents import vpn
from gbpservice.nfp.configurator.drivers.vpn.vyos import vyos_vpn_driver
import json
import unittest
import mock
import requests


class MakeDictionaries(object):
    '''
    Class which contains the reqired dictionires to perform vpn ipsec site conn
    '''

    def __init__(self):

        self.context_device = {'notification_data': {},
                               'resource': 'interfaces'}
        self.sc = 'sc'
        self.msg = 'msg'
        self.svc = {' ': ' '}
        self.vm_mgmt_ip = '192.168.20.75'
        self.service_vendor = 'vyos'
        self.source_cidrs = '11.0.0.0/24'
        self.destination_cidr = 'destination_cidr'
        self.gateway_ip = '11.0.0.254'
        self.url = 'http://192.168.20.75:8888'
        self.vpnsvc_status = [{'status': 'ERROR',
                               'updated_pending_status': True,
                               'id': '36cd27d5-8ad0-4ed7-8bbe-57c488a17835'}] 
        self.url_for_add_inte = "%s/add_rule" % self.url
        self.url_for_del_inte = "%s/delete_rule" % self.url
        self.url_for_add_src_route = "%s/add-source-route" % self.url
        self.url_for_del_src_route = "%s/delete-source-route" % self.url
        self.url_create_ipsec_conn = "%s/create-ipsec-site-conn" % self.url
        self.url_update_ipsec_conn = "%s/update-ipsec-site-conn" % self.url
        self.url_delete_ipsec_conn = "%s/delete-ipsec-site-conn?peer_address=1.103.2.2" % self.url
        self.url_create_ipsec_tunnel = "%s/create-ipsec-site-tunnel" % self.url
        self.url_delete_ipsec_tunnel = "%s/delete-ipsec-site-tunnel" % self.url
        self.url_get_ipsec_tunnel = "%s/get-ipsec-site-tunnel-state" % self.url
        self.data_for_interface = '{"stitching_mac": "00:0a:95:9d:68:25", "provider_mac": "00:0a:95:9d:68:16"}'
        self.data_for_add_src_route = '[{"source_cidr": "1.2.3.4/24", "gateway_ip": "1.2.3.4/24"}]'
        self.data_for_del_src_route = '[{"source_cidr": "1.2.3.4/24"}]'
        self.conn_id = 'ac3a0e54-cdf2-4ea7-ac2f-7c0225ab9af6'
        self.data_={"local_cidr": "11.0.6.0/24", "peer_address": "1.103.2.2", "peer_cidrs": "[141.0.0.0/24]"}
        self.data__={"local_cidr": "11.0.6.0/24", "peer_address": "1.103.2.2", "peer_cidr": "141.0.0.0/24"}
        self.timeout = 30

        self.svc_context = {'service': {
            'router_id': '73c64bb0-eab9-4f37-85d0-7c8b0c15ed06',
            'status': 'ACTIVE',
            'name': 'VPNService',
            'admin_state_up': True,
            'subnet_id': '7f42e3e2-80a6-4212-9f49-48194ba58fd9',
            'tenant_id': '9f1663d116f74a01991ad66aaa8756c5',
            'cidr': '30.0.0.0/28',
            'id': '36cd27d5-8ad0-4ed7-8bbe-57c488a17835',
            'description': 'fip=192.168.20.75;tunnel_local_cidr=11.0.6.0/24;user_access_ip=1.103.2.172;fixed_ip=192.168.0.3;standby_fip=1.103.1.21;service_vendor=vyos;stitching_cidr=192.168.0.0/28;stitching_gateway=192.168.0.1;mgmt_gw_ip=30.0.0.254',
            }, 'siteconns': [{'connection': {
            'status': 'INIT',
            'psk': 'secret',
            'initiator': 'bi-directional',
            'name': 'IPsecSiteConnection',
            'admin_state_up': True,
            'tenant_id': '9f1663d116f74a01991ad66aaa8756c5',
            'description': 'fip=192.168.20.75;tunnel_local_cidr=11.0.6.0/24;user_access_ip=1.103.2.172;fixed_ip=192.168.0.3;standby_fip=1.103.1.21;service_vendor=vyos;stitching_cidr=192.168.0.0/28;stitching_gateway=192.168.0.1;mgmt_gw_ip=30.0.0.254'
                ,
            'auth_mode': 'psk',
            'peer_cidrs': ['141.0.0.0/24'],
            'mtu': 1500,
            'ikepolicy_id': '31b79141-3d21-473f-b104-b811bb3ac1fd',
            'dpd': {'action': 'hold', 'interval': 30, 'timeout': 120},
            'route_mode': 'static',
            'vpnservice_id': '36cd27d5-8ad0-4ed7-8bbe-57c488a17835',
            'peer_address': '1.103.2.2',
            'peer_id': '192.168.104.228',
            'id': 'ac3a0e54-cdf2-4ea7-ac2f-7c0225ab9af6',
            'ipsecpolicy_id': 'b45d99b8-c38b-44ce-9ec8-ba223a83fb46',
            }, 'ipsecpolicy': {
            'encapsulation_mode': 'tunnel',
            'encryption_algorithm': '3des',
            'pfs': 'group5',
            'tenant_id': '9f1663d116f74a01991ad66aaa8756c5',
            'name': 'IPsecPolicy',
            'transform_protocol': 'esp',
            'lifetime': {'units': 'seconds', 'value': 3600},
            'id': 'b45d99b8-c38b-44ce-9ec8-ba223a83fb46',
            'auth_algorithm': 'sha1',
            'description': 'My new IPsec policy',
            }, 'ikepolicy': {
            'encryption_algorithm': '3des',
            'pfs': 'group5',
            'name': 'IKEPolicy',
            'tenant_id': '9f1663d116f74a01991ad66aaa8756c5',
            'lifetime': {'units': 'seconds', 'value': 3600},
            'description': 'My new IKE policy',
            'ike_version': 'v1',
            'id': '31b79141-3d21-473f-b104-b811bb3ac1fd',
            'auth_algorithm': 'sha1',
            'phase1_negotiation_mode': 'main',
            }}]}
        self.keywords = {'resource': self.svc_context['siteconns'][0]['connection']}

        self.subnet = [{
            'name': 'apic_owned_res_2b0f246b-b0fc-4731-9245-1bd9ac2bd373',
            'enable_dhcp': None,
            'network_id': 'b7432a1c-66a7-45ff-b317-4bbef9449740',
            'tenant_id': '9f1663d116f74a01991ad66aaa8756c5',
            'dns_nameservers': [],
            'gateway_ip': '192.168.0.1',
            'ipv6_ra_mode': None,
            'allocation_pools': [{'start': '192.168.0.2',
                                  'end': '192.168.0.14'}],
            'host_routes': [],
            'ip_version': 4,
            'ipv6_address_mode': None,
            'cidr': '30.0.0.0/28',
            'id': '7f42e3e2-80a6-4212-9f49-48194ba58fd9',
            }]


        self.vpnservice = [{
             'router_id': '73c64bb0-eab9-4f37-85d0-7c8b0c15ed06',
             'status': 'ACTIVE',
             'name': 'VPNService',
             'admin_state_up': True,
             'subnet_id': '7f42e3e2-80a6-4212-9f49-48194ba58fd9',
             'tenant_id': '9f1663d116f74a01991ad66aaa8756c5',
             'id': '36cd27d5-8ad0-4ed7-8bbe-57c488a17835',
             'description': 'fip=192.168.20.75;tunnel_local_cidr=11.0.6.0/24;user_access_ip=1.103.2.172;fixed_ip=192.168.0.3;standby_fip=1.103.1.21;service_vendor=vyos;stitching_cidr=192.168.0.0/28;stitching_gateway=192.168.0.1;mgmt_gw_ip=30.0.0.254',
             }]
        self.ipsec_site_connection = [{
                        'status': 'INIT',
                        'psk': 'secret',
                        'initiator': 'bi-directional',
                        'name': 'IPsecSiteConnection',
                        'admin_state_up': True,
                        'tenant_id': '9f1663d116f74a01991ad66aaa8756c5',
                        'auth_mode': 'psk',
                        'peer_cidrs': ['141.0.0.0/24'],
                        'mtu': 1500,
                        'ikepolicy_id': '31b79141-3d21-473f-b104-b811bb3ac1fd',
                        'vpnservice_id': (
                                '36cd27d5-8ad0-4ed7-8bbe-57c488a17835'),
                        'dpd': {'action': 'hold',
                                'interval': 30,
                                'timeout': 120},
                        'route_mode': 'static',
                        'ipsecpolicy_id': (
                                'b45d99b8-c38b-44ce-9ec8-ba223a83fb46'),
                        'peer_address': '1.103.2.2',
                        'peer_id': '192.168.104.228',
                        'id': 'ac3a0e54-cdf2-4ea7-ac2f-7c0225ab9af6',
                        'description': 'fip=192.168.20.75;tunnel_local_cidr=11.0.6.0/24;user_access_ip=1.103.2.172;fixed_ip=192.168.0.3;standby_fip=1.103.1.21;service_vendor=vyos;stitching_cidr=192.168.0.0/28;stitching_gateway=192.168.0.1;mgmt_gw_ip=30.0.0.254',
                        }]

        self.ipsec_site_connection_delete = [{
                        u'status': u'INIT',
                        u'psk': u'secret',
                        u'initiator': u'bi-directional',
                        u'name': u'site_to_site_connection1',
                        u'admin_state_up': True,
                        u'tenant_id': u'564aeb9ebd694468bfb79a69da887419',
                        u'auth_mode': u'psk',
                        u'peer_cidrs': [u'11.0.0.0/24'],
                        u'mtu': 1500,
                        u'ikepolicy_id': (
                                u'7a88b9f4-70bf-4184-834d-6814f264d331'),
                        u'vpnservice_id': (
                                u'3d453be6-7ddc-4812-a4a7-3299f9d3d29e'),
                        u'dpd': {u'action': u'hold',
                                 u'interval': 30,
                                 u'timeout': 120},
                        u'route_mode': u'static',
                        u'ipsecpolicy_id': (
                                u'03839460-1519-46ab-a073-b74314c06ec3'),
                        u'peer_address': u'1.103.2.2',
                        u'peer_id': u'1.103.2.2',
                        u'id': u'4dae3c91-0d0a-4ba5-9269-d0deab653316',
                        u'description': u'fip=192.168.20.75;tunnel_local_cidr=11.0.2.0/24;user_access_ip=1.103.2.178;fixed_ip=192.168.0.2;standby_fip=;service_vendor=vyos;stitching_cidr=192.168.0.0/28;stitching_gateway=192.168.0.1;mgmt_gw_ip=30.0.0.254',
                        }]

        self.ikepolicies = [{
            'encryption_algorithm': '3des',
            'pfs': 'group5',
            'name': 'IKEPolicy',
            'phase1_negotiation_mode': 'main',
            'lifetime': {'units': 'seconds', 'value': 3600},
            'tenant_id': '9f1663d116f74a01991ad66aaa8756c5',
            'ike_version': 'v1',
            'id': '31b79141-3d21-473f-b104-b811bb3ac1fd',
            'auth_algorithm': 'sha1',
            'description': 'My new IKE policy',
            }]

        self.ipsecpolicies = [{
            'encapsulation_mode': 'tunnel',
            'encryption_algorithm': '3des',
            'pfs': 'group5',
            'lifetime': {'units': 'seconds', 'value': 3600},
            'name': 'IPsecPolicy',
            'transform_protocol': 'esp',
            'tenant_id': '9f1663d116f74a01991ad66aaa8756c5',
            'id': 'b45d99b8-c38b-44ce-9ec8-ba223a83fb46',
            'auth_algorithm': 'sha1',
            'description': 'My new IPsec policy',
            }]

        self.context = {
            'domain': None,
            'project_name': None,
            'tenant_name': u'services',
            'project_domain': None,
            'timestamp': '2016-03-03 09:19:05.381231',
            'auth_token': u'0711af29a389492cb799e096a003a760',
            'resource_uuid': None,
            'is_admin': True,
            'user': u'19e278f3c3fa43e3964b057bc73cf7d7',
            'tenant': '9f1663d116f74a01991ad66aaa8756c5',
            'read_only': False,
            'project_id': 'b',
            'user_id': 'a',
            'show_deleted': False,
            'roles': [u'admin', u'heat_stack_owner'],
            'user_identity': 'a b - - -',
            'tenant_id': u'9f1663d116f74a01991ad66aaa8756c5',
            'request_id': u'req-da8765fb-4eb4-4f4f-9ebb-843ad1d752bd',
            'user_domain': None,
            'user_name': u'neutron',

            }

    def _make_service_context(self, operation_type=None):
        self.service_info = {}
        self.service_info.update({'vpnservices': self.vpnservice})
        if operation_type is None:
            self.service_info.update({'ikepolicies': self.ikepolicies})
            self.service_info.update({'ipsecpolicies': self.ipsecpolicies})
            self.service_info.update({'ipsec_site_conns': (
                                            self.ipsec_site_connection)})

        self.service_info.update({'subnets': self.subnet})
        self.context.update({'service_info': self.service_info})
        return self.context

    def _create_vpnservice_obj(self):
        return {
                'rsrc_type': 'vpn_service',
                'rsrc_id': '36cd27d5-8ad0-4ed7-8bbe-57c488a17835',
                'resource': {
                    'router_id': '73c64bb0-eab9-4f37-85d0-7c8b0c15ed06',
                    'status': 'ACTIVE',
                    'name': 'VPNService',
                    'admin_state_up': True,
                    'subnet_id': '7f42e3e2-80a6-4212-9f49-48194ba58fd9',
                    'tenant_id': '9f1663d116f74a01991ad66aaa8756c5',
                    'id': '36cd27d5-8ad0-4ed7-8bbe-57c488a17835',
                    'description': 'fip=192.168.20.75;tunnel_local_cidr=11.0.6.0/24;user_access_ip=1.103.2.172;fixed_ip=192.168.0.3;standby_fip=1.103.1.21;service_vendor=vyos;stitching_cidr=192.168.0.0/28;stitching_gateway=192.168.0.1;mgmt_gw_ip=30.0.0.254',
                    },
                'svc_type': 'ipsec',
                'service_vendor': 'vyos',
                'reason': 'create',
                }

    def _create_ipsec_site_conn_obj(self):
        return {
            'rsrc_type': 'ipsec_site_connection',
            'rsrc_id': 'ac3a0e54-cdf2-4ea7-ac2f-7c0225ab9af9',
            'resource': {
                'status': 'INIT',
                'psk': 'secret',
                'initiator': 'bi-directional',
                'name': 'IPsecSiteConnection',
                'admin_state_up': True,
                'tenant_id': '9f1663d116f74a01991ad66aaa8756c5',
                'auth_mode': 'psk',
                'peer_cidrs': ['141.0.0.1/24'],
                'mtu': 1500,
                'ikepolicy_id': '31b79141-3d21-473f-b104-b811bb3ac1fd',
                'vpnservice_id': (
                            '36cd27d5-8ad0-4ed7-8bbe-57c488a17835'),
                'dpd': {'action': 'hold',
                        'interval': 30,
                        'timeout': 120},
                'route_mode': 'static',
                'ipsecpolicy_id': (
                        'b45d99b8-c38b-44ce-9ec8-ba223a83fb46'),
                'peer_address': '1.103.2.2',
                'peer_id': '141.0.0.2',
                'id': 'ac3a0e54-cdf2-4ea7-ac2f-7c0225ab9af9',
                'description': 'fip=192.168.20.75;tunnel_local_cidr=11.0.6.0/24;user_access_ip=1.103.2.172;fixed_ip=192.168.0.3;standby_fip=1.103.1.21;service_vendor=vyos;stitching_cidr=192.168.0.0/28;stitching_gateway=192.168.0.1;mgmt_gw_ip=30.0.0.254',
                },
            'svc_type': 'ipsec',
            'service_vendor': 'vyos',
            'reason': 'create',
            }

    def _delete_ipsec_site_conn_obj(self):
        return {
                u'rsrc_type': u'ipsec_site_connection',
                u'rsrc_id': u'4dae3c91-0d0a-4ba5-9269-d0deab653316',
                u'resource': {
                    u'status': u'INIT',
                    u'psk': u'secret',
                    u'initiator': u'bi-directional',
                    u'name': u'site_to_site_connection1',
                    u'admin_state_up': True,
                    u'tenant_id': u'564aeb9ebd694468bfb79a69da887419',
                    u'auth_mode': u'psk',
                    u'peer_cidrs': [u'11.0.0.0/24'],
                    u'mtu': 1500,
                    u'ikepolicy_id': (
                            u'7a88b9f4-70bf-4184-834d-6814f264d331'),
                    u'vpnservice_id': (
                            u'3d453be6-7ddc-4812-a4a7-3299f9d3d29e'),
                    u'dpd': {u'action': u'hold',
                             u'interval': 30,
                             u'timeout': 120},
                    u'route_mode': u'static',
                    u'ipsecpolicy_id': (
                            u'03839460-1519-46ab-a073-b74314c06ec3'),
                    u'peer_address': u'1.103.2.2',
                    u'peer_id': u'1.103.2.2',
                    u'id': u'4dae3c91-0d0a-4ba5-9269-d0deab653315',
                    u'description': u'fip=192.168.20.75;tunnel_local_cidr=11.0.2.0/24;user_access_ip=1.103.2.178;fixed_ip=192.168.0.2;standby_fip=;service_vendor=vyos;stitching_cidr=192.168.0.0/28;stitching_gateway=192.168.0.1;mgmt_gw_ip=30.0.0.254',
                    },
                u'svc_type': u'ipsec',
                u'service_vendor': u'vyos',
                u'reason': u'delete',
                }

    def _update_ipsec_site_conn_obj(self):
        return {
                u'rsrc_type': u'ipsec_site_connection',
                u'rsrc_id': u'4dae3c91-0d0a-4ba5-9269-d0deab653316',
                u'resource': {
                    u'status': u'INIT',
                    u'psk': u'secret',
                    u'initiator': u'bi-directional',
                    u'name': u'site_to_site_connection1',
                    u'admin_state_up': True,
                    u'tenant_id': u'564aeb9ebd694468bfb79a69da887419',
                    u'auth_mode': u'psk',
                    u'peer_cidrs': [u'11.0.0.0/24'],
                    u'mtu': 1500,
                    u'ikepolicy_id': (
                            u'7a88b9f4-70bf-4184-834d-6814f264d331'),
                    u'vpnservice_id': (
                            u'3d453be6-7ddc-4812-a4a7-3299f9d3d29e'),
                    u'dpd': {u'action': u'hold',
                             u'interval': 30,
                             u'timeout': 120},
                    u'route_mode': u'static',
                    u'ipsecpolicy_id': (
                            u'03839460-1519-46ab-a073-b74314c06ec3'),
                    u'peer_address': u'1.103.2.2',
                    u'peer_id': u'1.103.2.2',
                    u'id': u'4dae3c91-0d0a-4ba5-9269-d0deab653315',
                    u'description': u'fip=192.168.20.75;tunnel_local_cidr=11.0.2.0/24;user_access_ip=1.103.2.178;fixed_ip=192.168.0.2;standby_fip=;service_vendor=vyos;stitching_cidr=192.168.0.0/28;stitching_gateway=192.168.0.1;mgmt_gw_ip=30.0.0.254',
                    },
                u'svc_type': u'ipsec',
                u'service_vendor': u'vyos',
                u'reason': u'update',
                }


    def _make_kwargs(self, operation=None, service_type=None):

        if operation is 'delete':
            return self._delete_ipsec_site_conn_obj()
        if operation is 'update':
            return self._update_ipsec_site_conn_obj()

        if operation == 'create' and service_type == 'ipsec':
            return self._create_ipsec_site_conn_obj()
        else:
            return self._create_vpnservice_obj()

    def _fake_kwargs(self):
        """ A sample keyword arguments for configurator
        Returns: kwargs
        """
        kwargs = {'service_type': 'vpn',
                  'vm_mgmt_ip': '192.168.20.75',
                  'mgmt_ip': '192.168.20.75',
                  'source_cidrs': ['1.2.3.4/24'],
                  'destination_cidr': ['1.2.3.4/24'],
                  'gateway_ip': '1.2.3.4/24',
                  'provider_interface_position': '1',
                  'request_info': 'some_id',
                  'periodicity': 'initial',
                  'rule_info': {
                        'active_provider_mac': '00:0a:95:9d:68:16',
                        'provider_mac': '00:0a:95:9d:68:16',
                        'active_stitching_mac': '00:0a:95:9d:68:25',
                        'stitching_mac': '00:0a:95:9d:68:25',
                        'active_fip': '192.168.20.75',
                        'fip': '192.168.20.75',
                        'service_id': (
                            '1df1cd7a-d82e-4bbd-8b26-a1f106075a6b'),
                        'tenant_id': (
                            '564aeb9ebd694468bfb79a69da887419')},
                  'context': {'notification_data': 'hello'}
                  }
        return kwargs


class FakeEvent(object):
    def __init__(self):
        self.dict_obj = MakeDictionaries()
        self.data = {
                    'context': self.dict_obj._make_service_context(),
                    'kwargs': self.dict_obj._create_ipsec_site_conn_obj()
                 }


class VpnaasIpsecDriverTestCase(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(VpnaasIpsecDriverTestCase, self).__init__(*args, **kwargs)
        self.dict_objects = MakeDictionaries()
        self.context = self.dict_objects._make_service_context()
        self.plugin_rpc = vpn.VpnaasRpcSender(self.context, self.dict_objects.sc)
        self.driver = vyos_vpn_driver.VpnaasIpsecDriver(self.plugin_rpc)
        self.svc_validate = vyos_vpn_driver.VPNSvcValidator(self.plugin_rpc)
        self.resp = mock.Mock()
        self.fake_resp_dict = {'status': True}

    
    def test_create_vpn_service(self):
        context = self.dict_objects._make_service_context(operation_type='vpn')
        
        kwargs = self.dict_objects._make_kwargs(operation='create',
                                                service_type='vpn')
        with mock.patch.object(self.plugin_rpc, 'update_status') as (
                                                mock_update_status):
     
            self.driver.vpnservice_updated(context, kwargs)
            mock_update_status.assert_called_with(
                                        self.context,
                                        self.dict_objects.vpnsvc_status)
     

    def test_create_ipsec_site_conn(self):
        self.resp = mock.Mock(status_code=200)
        kwargs = self.dict_objects._make_kwargs(operation='create',
                                                service_type='ipsec')
        with mock.patch.object(self.plugin_rpc, 'update_status') as (
                                                mock_update_status),\
            mock.patch.object(json, 'loads') as  mock_resp,\
            mock.patch.object(requests, 'post') as (
                                                mock_post):
            mock_resp.return_value = self.fake_resp_dict
            mock_post.return_value = self.resp
            self.driver.vpnservice_updated(self.context, kwargs)
            mock_post.assert_called_with(
                            self.dict_objects.url_create_ipsec_tunnel,
                            data=json.dumps(self.dict_objects.data_),
                            timeout=self.dict_objects.timeout)

            mock_update_status.assert_called_with(self.context,
                                                  self.dict_objects.vpnsvc_status)
            
    def test_delete_ipsec_site_conn(self):
        self.resp = mock.Mock(status_code=200)
        kwargs = self.dict_objects._make_kwargs(operation='delete',
                                                service_type='ipsec')
        with mock.patch.object(self.plugin_rpc, 'update_status') as (
                                                mock_update_status),\
            mock.patch.object(json, 'loads') as  mock_resp,\
            mock.patch.object(requests, 'delete') as (
                                                mock_delete):
            mock_resp.return_value = self.fake_resp_dict
            mock_delete.return_value = self.resp
            self.driver.vpnservice_updated(self.context, kwargs)
            mock_delete.assert_called_with(
                            self.dict_objects.url_delete_ipsec_conn,
                            timeout=self.dict_objects.timeout,
                            data=None)

    def test_check_status(self):
        self.resp = mock.Mock(status_code=200)
        svc_context = self.dict_objects.svc_context
        with mock.patch.object(self.plugin_rpc, 'update_status') as (
                                                mock_update_status),\
            mock.patch.object(self.resp, 'json') as mock_json,\
            mock.patch.object(requests, 'get') as mock_get:
            mock_get.return_value=self.resp
            mock_json.return_value = {'state': 'UP'}
            self.driver.check_status(self.context, svc_context)
            mock_get.assert_called_with(
                            self.dict_objects.url_get_ipsec_tunnel,
                            params=self.dict_objects.data__,
                            timeout=self.dict_objects.timeout)

class VpnGenericConfigDriverTestCase(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(VpnGenericConfigDriverTestCase, self).__init__(*args, **kwargs)

        self.dict_objects = MakeDictionaries()
        self.context = self.dict_objects._make_service_context()
        self.plugin_rpc = vpn.VpnaasRpcSender(self.context,
                                              self.dict_objects.sc)
        self.rest_apt = vyos_vpn_driver.RestApi(self.dict_objects.vm_mgmt_ip)
        self.driver = vyos_vpn_driver.VpnGenericConfigDriver()
        self.resp = mock.Mock()
        self.fake_resp_dict = {'status': True}
        self.kwargs = self.dict_objects._fake_kwargs()
    def setUp(self):
        self.resp = mock.Mock(status_code=200)
    def tearDown(self):
        self.resp = mock.Mock(status_code=200)


    def test_configure_interfaces(self):
        with mock.patch.object(
                requests, 'post', return_value=self.resp) as mock_post, \
             mock.patch.object(
                self.resp, 'json', return_value=self.fake_resp_dict):
            self.driver.configure_interfaces(self.dict_objects.context_device,
                                             self.kwargs)

            mock_post.assert_called_with(self.dict_objects.url_for_add_inte,
                                         self.dict_objects.data_for_interface,
                                         timeout=self.dict_objects.timeout)
    def test_clear_interfaces(self):
        self.resp = mock.Mock(status_code=200)
        with mock.patch.object(
                requests, 'delete', return_value=self.resp) as mock_delete, \
            mock.patch.object(
                self.resp, 'json', return_value=self.fake_resp_dict):
            self.driver.clear_interfaces(self.dict_objects.context_device,
                                         self.kwargs)

            mock_delete.assert_called_with(
                                self.dict_objects.url_for_del_inte,
                                data=self.dict_objects.data_for_interface,
                                timeout=self.dict_objects.timeout)

    def test_configure_source_routes(self):
        with mock.patch.object(
                requests, 'post', return_value=self.resp) as mock_post, \
             mock.patch.object(
                json, 'loads',return_value=self.fake_resp_dict):
            self.driver.configure_routes(
                self.dict_objects.context_device, self.kwargs)

            mock_post.assert_called_with(
                                self.dict_objects.url_for_add_src_route,
                                data=self.dict_objects.data_for_add_src_route,
                                timeout=self.dict_objects.timeout)

    def test_delete_source_routes(self):
        with mock.patch.object(
                requests, 'delete', return_value=self.resp) as mock_delete:
            self.driver.clear_routes(
                self.dict_objects.context_device, self.kwargs)

            mock_delete.assert_called_with(
                                self.dict_objects.url_for_del_src_route,
                                data=self.dict_objects.data_for_del_src_route,
                                timeout=self.dict_objects.timeout)


class VPNSvcValidatorTestCase(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(VPNSvcValidatorTestCase, self).__init__(*args, **kwargs)
        self.dict_objects = MakeDictionaries()
        self.plugin_rpc = vpn.VpnaasRpcSender(self.dict_objects.context,
                                              self.dict_objects.sc)
        self.valid_obj = vyos_vpn_driver.VPNSvcValidator(self.plugin_rpc)

    def validate_active(self):
        svc = self.dict_objects._create_vpnservice_obj()['resource']
        description = str(svc['description'])
        description = description.split(';')
        description[1] = 'tunnel_local_cidr=12.0.6.0/24'
        description = ";".join(description)
        svc.update({'desciption': description})

        with mock.patch.object(self.plugin_rpc, "update_status") as mock_valid:
            self.valid_obj.validate(
                        self.dict_objects._make_service_context(), svc)
            self.dict_objects.vpnsvc_status[0].update({'status': 'ACTIVE'})
            mock_valid.assert_called_with(
                        self.dict_objects._make_service_context(),
                        self.dict_objects.vpnsvc_status)


    def test_validate_error(self):
        with mock.patch.object(self.plugin_rpc, "update_status") as mock_valid:
            self.valid_obj.validate(
                    self.dict_objects._make_service_context(),
                    self.dict_objects._create_vpnservice_obj()['resource'])
            mock_valid.assert_called_with(
                        self.dict_objects._make_service_context(),
                        self.dict_objects.vpnsvc_status)



class RestApiTestCase(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(RestApiTestCase, self).__init__(*args, **kwargs)
        self.rest_obj = vyos_vpn_driver.RestApi(MakeDictionaries().vm_mgmt_ip)
        self.resp = mock.Mock()
        self.resp = mock.Mock(status_code=200)
        self.dict_objects = MakeDictionaries()
        self.args = {'peer_address': '1.103.2.2'}
        self.fake_resp_dict = {'status': None}
        self.timeout = 30
        self.data={'data':'data'}
        self.j_data = json.dumps(self.data)

    def test_post_success(self):
        self.resp = mock.Mock(status_code=200)
        self.fake_resp_dict.update({'status': True})
        with mock.patch.object(requests, 'post', return_value=self.resp) as (
                                                                mock_post),\
            mock.patch.object(json, 'loads', return_value=self.fake_resp_dict):
            self.rest_obj.post('create-ipsec-site-conn', self.data)
            mock_post.assert_called_with(
                                    self.dict_objects.url_create_ipsec_conn,
                                    data=self.j_data,
                                    timeout=self.timeout)

    def post_fail(self):
        self.resp = mock.Mock(status_code=404)
        self.fake_resp_dict.update({'status': False})
        with mock.patch.object(requests, 'post', return_value=self.resp) as (
                                                                mock_post),\
            mock.patch.object(json, 'loads', return_value=self.fake_resp_dict):
            self.rest_obj.post('create_ipsec_site_conn', self.data)
            mock_put.side_effect = Exception(mock.Mock(status=404), 'Not Found')
            mock_post.assert_called_with(
                                    self.dict_objects.url_create_ipsec_conn,
                                    data=self.j_data,
                                    timeout=self.timeout)

    def put_success(self):
        self.resp = mock.Mock(status_code=200)
        with mock.patch.object(requests, 'put', return_value=self.resp) as (
                                                                mock_put):
            self.rest_obj.put('create_ipsec_site_conn', self.data)
            mock_put.assert_called_with(self.dict_objects.url_create_ipsec_conn, data=self.j_data, timeout=self.timeout)

    def put_fail(self):
        self.resp = mock.Mock(status_code=404)
        with mock.patch.object(requests, 'put', return_value=self.resp) as (
                                                                mock_put):

            self.rest_obj.put('create_ipsec_site_conn', self.data)
            mock_put.assert_called_with(self.dict_objects.url_create_ipsec_conn, data=self.j_data, timeout=self.timeout)

    def test_delete_success(self):
        self.resp = mock.Mock(status_code=200)
        self.fake_resp_dict.update({'status': True})
        with mock.patch.object(requests, 'delete', return_value=self.resp) as (
                                                                mock_delete),\
            mock.patch.object(json, 'loads', return_value=self.fake_resp_dict):
            self.rest_obj.delete('delete-ipsec-site-conn', self.args, self.data)
            mock_delete.assert_called_with(
                                    self.dict_objects.url_delete_ipsec_conn,
                                    timeout=self.timeout,
                                    data=self.j_data)
    def exception_raised(self):
        print "Working"

    def delete_fail(self):
        self.resp = mock.Mock(status_code=404)
        self.fake_resp_dict.update({'status': False})
        with mock.patch.object(requests, 'delete', return_value=self.resp) as (
                                                                mock_delete),\
            mock.patch.object(json, 'loads', return_value=self.fake_resp_dict):
            self.rest_obj.delete('delete-ipsec-site-tunnel', self.args, self.data)
            mock_delete.side_effect = Exception(mock.Mock(status=404), 'Not Found')
            mock_delete.side_effect = self.exception_raised()
            mock_delete.assert_called_with(
                                    self.dict_objects.url_delete_ipsec_conn,
                                    timeout=self.timeout,
                                    data=self.j_data)

    def test_get_success(self):
        self.resp = mock.Mock(status_code=200)
        with mock.patch.object(requests, 'get', return_value=self.resp) as (
                                                                mock_get):
            self.rest_obj.get('create-ipsec-site-tunnel', self.data)
            mock_get.assert_called_with(
                                    self.dict_objects.url_create_ipsec_tunnel,
                                    params=self.data,
                                    timeout=self.timeout)

    def test_get_fail(self):
        self.resp = mock.Mock(status_code=404)
        with mock.patch.object(requests, 'get', return_value=self.resp) as (
                                                                mock_get):
            self.rest_obj.get('create-ipsec-site-tunnel', self.data)
            mock_get.assert_called_with(
                                    self.dict_objects.url_create_ipsec_tunnel,
                                    params=self.data,
                                    timeout=self.timeout)

class VPNaasEventHandlerTestCase(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(VPNaasEventHandlerTestCase, self).__init__(*args, **kwargs)
        self.dict_obj = MakeDictionaries()
        self.handler = vpn.VPNaasEventHandler(self.dict_obj.sc,
                                              self.dict_obj.drivers)
        self.ev = FakeEvent()
        self.driver = vyos_vpn_driver.VpnaasIpsecDriver(
                                                self.handler.plugin_rpc)

    def test_handle_event(self):
        with mock.patch.object(self.handler,
                          '_get_driver',
                          return_value=self.dict_obj.drivers) as mock_drivers,\
            mock.patch.object(self.driver, 'vpnservice_updated') as (
                                                    mock_vpnservice_updated):
            self.handler.vpnservice_updated(self.ev, self.driver)
            mock_vpnservice_updated.assert_called_with(self.ev.data['context'],
                                                       self.ev.data['kwargs'])
    def test_sync(self):
        context = self.dict_obj._make_service_context()
        with mock.patch.object(self.handler,
                               '_get_driver',
                          return_value=self.driver) as mock_drivers,\
            mock.patch.object(self.driver, 'check_status') as (
                                                mock_update_status):
            self.handler.sync(context)
            mock_update_status.assert_called_with(context,
                                                  self.dict_obj.svc_context)

    def test_resync_ipsec_conns(self):
        context = self.dict_obj._make_service_context()
        with mock.patch.object(self.handler,
                               '_get_driver',
                          return_value=self.driver) as mock_drivers,\
            mock.patch.object(self.driver, 'delete_ipsec_conn') as (
                                                    mock_delete_ipsec_conn),\
            mock.patch.object(self.handler.plugin_rpc,
                              'ipsec_site_conn_deleted') as (
                                                mock_ipsec_site_conn_deleted):
            self.handler._resync_ipsec_conns(context, self.dict_obj.service_vendor,
                                           self.dict_obj.svc_context)
            
            mock_delete_ipsec_conn.assert_called_with(context,
                                                      **self.dict_obj.keywords)
            mock_ipsec_site_conn_deleted.assert_called_with(context,
                                                    resource_id=self.dict_obj.conn_id)


if __name__ == '__main__':
    unittest.main()

