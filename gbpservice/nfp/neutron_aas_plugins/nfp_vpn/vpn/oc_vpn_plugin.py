from neutron_vpnaas.db.vpn import vpn_db
from neutron_vpnaas.services.vpn import plugin as base_plugin


class OCVPNDriverPlugin(base_plugin.VPNDriverPlugin, vpn_db.VPNPluginDb):
    """OC VpnPlugin which supports VPN Service Drivers."""
    def __init__(self):
        super(OCVPNDriverPlugin, self).__init__()

    def delete_ipsec_site_connection(self, context, ipsec_conn_id):
        ipsec_site_connection = self.get_ipsec_site_connection(
            context, ipsec_conn_id)

        super(OCVPNDriverPlugin, self).update_ipsec_site_conn_status(
            context,
            ipsec_conn_id,
            base_plugin.constants.PENDING_DELETE)

        driver = self._get_driver_for_ipsec_site_connection(
            context, ipsec_site_connection)
        driver.delete_ipsec_site_connection(context, ipsec_site_connection)

    def _delete_ipsec_site_connection(self, context, ipsec_conn_id):
        base_plugin.VPNPlugin.delete_ipsec_site_connection(self, context,
                                                           ipsec_conn_id)

    def delete_vpnservice(self, context, vpnservice_id):
        vpn_svc = self.get_vpnservice(context, vpnservice_id)
        driver = self._get_driver_for_vpnservice(vpnservice_id)
        driver.delete_vpnservice(context, vpn_svc)

    def _delete_vpnservice(self, context, vpnservice_id):
        base_plugin.VPNPlugin.delete_vpnservice(self, context,
                                                vpnservice_id)
    #def assert_update_allowed(self, obj):
    #    return
