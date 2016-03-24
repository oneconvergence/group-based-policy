import mock
from neutron.tests import base

from gbpservice.nfp.config_orchestrator.agent.vpn import VpnAgent


class VpnAgentTestCase(base.BaseTestCase):
    def setUp(self):
        self.conf = mock.Mock()
        self.sc = mock.Mock()
        self.context = mock.Mock()
        super(VpnAgentTestCase, self).setUp()
        # self.neutron_vpnaas_mock = mock.Mock()
        # modules = {
        #     'neutron_vpnaas': self.neutron_vpnaas_mock,
        #     'neutron_vpnaas.db': self.neutron_vpnaas_mock.db,
        #     'neutron_vpnaas.db.vpn': self.neutron_vpnaas_mock.db.vpn
        # }
        # self.module_patcher = mock.patch.dict('sys.modules', modules)
        # self.module_patcher.start()
        # from gbpservice.nfp.agent.agent.vpn import VpnAgent
        self.vpn_agent = VpnAgent(self.conf, self.sc)

    @mock.patch.object(VpnAgent, "wait_for_device_ready")
    def test_vpnservice_updated(self, mock_wait_for_device_ready):
        data = {
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
                'description': 'service_profile_id=id1',
                },
            'svc_type': 'ipsec',
            'service_vendor': 'vyos',
            'reason': 'create',
            }
        mock_wait_for_device_ready.return_value = {
            'status': 'ACTIVE',
            'description': "{'standby_fip': None, 'fip': 'fip1', "
                           "'stitching_gateway': 'gateway',"
                           "'stitching_cidr': 'cidr1', 'fixed_ip': 'ip1',"
                           " 'mgmt_gw_ip': '', 'user_access_ip': 'fip1',"
                           "'service_vendor': 'vyos',"
                           " 'network_service': 'neutron_vpn_service',"
                           "'tunnel_local_cidr': 'cidr1'}",
            'heat_stack_id': None,
            'network_function_instances': [],
            'service_chain_id': None,
            'id': '23d83bbf-921b-4f28-9298-3f3d1384c772',
            'service_profile_id': 'oc',
            'service_config': 'rtr1', 'tenant_id': 'services',
            'service_id': 'rsrc1'}
        self.vpn_agent.vpnservice_updated(self.context, **data)
