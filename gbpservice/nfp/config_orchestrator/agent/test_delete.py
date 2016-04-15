from gbpservice.nfp.config_orchestrator.agent import topics
from gbpservice.nfp.lib.transport import RPCClient
from neutron import context


class TestSO(object):

    @property
    def so_rpc_client(self):
        return RPCClient(topics.NFP_NSO_TOPIC)

    def test_delete(self, nw_fun_id):
        ctxt = context.get_admin_context()
        nw_fun_info = {'id': nw_fun_id, 'service_type': 'firewall'}
        self.so_rpc_client.cctxt.call(ctxt,
                                      'neutron_delete_nw_function_config',
                                      network_function=nw_fun_info)


test_so = TestSO()
test_so.test_delete('4dce26e66b7d44d78fc618b2628336de')
