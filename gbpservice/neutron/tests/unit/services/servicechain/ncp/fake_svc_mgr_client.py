
class SvcManagerClientApi(object):
    
    def __init__(self, host):
        self.tenant_id = ""
        self.service_instance_id = ""
        self.chain_instance_id = ""
        self.service_type = ""
        self.vm_id = ""
        self.active_vm_id = ""
        self.standby_vm_id = ""
        self.floating_ip = ""
        self.floating_id = ""
        self.provider_port_id = ""
        self.consumer_port_id = ""
        self.mgmt_port_id = ""
        self.stitching_port_id = ""
        self.service_count = ""
        self.vm_status = ""

    def get_svc_mgmt_ip(self, context, tenant_id, service_type):
        pass
    
    def _set_params(self, service_chain_instance_id, tenant_id, service_type,
                    provider_network_port, consumer_network_port,
                    stitching_network_port, management_port,
                    management_fip_id):
        self.tenant_id = tenant_id
        self.service_instance_id = service_chain_instance_id
        self.chain_instance_id = ""
        self.service_type = service_type
        self.vm_id = ""
        self.active_vm_id = ""
        self.standby_vm_id = ""
        self.floating_ip = ""
        self.floating_id = management_fip_id
        self.provider_port_id = provider_network_port
        self.consumer_port_id = consumer_network_port
        self.mgmt_port_id = management_port
        self.stitching_port_id = stitching_network_port
        self.service_count = 1
        self.vm_status = "ACTIVE"

    def create_service_instance(self, context, service_chain_instance_id,
                                tenant_id, service_type, provider_network_port,
                                consumer_network_port, stitching_network_port,
                                management_port, management_fip_id):
        self._set_params(service_chain_instance_id, tenant_id, service_type,
                         provider_network_port, consumer_network_port,
                         stitching_network_port, management_port,
                         management_fip_id)

    def delete_service_instance(self, context, **kwargs):
        ports_to_cleanup = {}
        if self.provider_port_id:
            ports_to_cleanup.update({"provider_port_id": self.provider_port_id})
        if self.consumer_port_id:
            ports_to_cleanup.update({"consumer_port_id": self.consumer_port_id})
        if self.mgmt_port_id:
            ports_to_cleanup.update({"mgmt_port_id": self.mgmt_port_id})
        if self.stitching_port_id:
            ports_to_cleanup.update({"stitching_port_id": self.stitching_port_id})
        return ports_to_cleanup

    def get_service_info_with_srvc_type(self, context, **kwargs):
        return {'floating_ip': self.floating_ip,
                'provider_port_id': self.provider_port_id}

    def get_existing_service_for_sharing(self, context, **kwargs):
        return None

    def get_service_instance_satus(self, context, **kwargs):
        pass
    
    def get_service_floating_ip(self, context, tenant_id, service_type):
        pass
    
    def get_service_ports(self, context, tenant_id, service_type):
        pass
    
    def get_vpn_access_ip(self, context, stitching_port):
        pass
