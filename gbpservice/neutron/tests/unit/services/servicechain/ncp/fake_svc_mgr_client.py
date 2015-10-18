
class SvcManagerClientApi(object):
    
    def __init__(self, host):
        self.is_ha = False

    def get_management_ips(self, context, tenant_id, service_chain_instance_id,
                           service_node_id):
        if self.is_ha:
            return {"active_mgmt_fip": "192.168.1.1",
                    "standby_mgmt_fip": "192.168.1.1",}
        else:
            return {"active_mgmt_fip": "192.168.1.1"}
    
    def _set_params(self, service_info):
        if service_info.get("stitching_vip_port_id"):
            self.is_ha = True
            return {"active_mgmt_fip": "192.168.1.1",
                    "standby_mgmt_fip": "192.168.1.1",}
        else:
            self.is_ha = False
            return {"active_mgmt_fip": "192.168.1.1"}

    def create_service(self, context, service_info):
        return self._set_params(service_info)

    def delete_service(self, context, tenant_id, service_chain_instance_id,
                       service_node_id):
        pass
