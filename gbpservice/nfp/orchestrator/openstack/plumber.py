
from netaddr import IPNetwork
from openstack_driver import KeystoneClient
from openstack_driver import NeutronClient
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class SCPlumber():
    """ Class to perform plumbing function
    """
    def __init__(self, conf):
        self.plumber = NeutronPlumber(conf)

    def get_stitching_info(self, tenant_id, router_id=None,
                           fip_required=False):
        # create a port for hotplug with port security disabled
        # assign fip if needed
        # After successful operation, return port details.
        stitching_port_info = self.plumber.create_stitching_for_svc(
            tenant_id, router_id, fip_required)
        return stitching_port_info

    def ports_state_down(self, ports):
        self.plumber.make_ports_down(ports)

    def clear_all_extraroutes(self, router_id):
        # cli - neutron router-update xyz --routes action=clear
        self.plumber.clear_router_routes(router_id)

    def update_router_service_gateway(self, router_id, peer_cidrs,
                                      stitching_interface_ip, delete=False):
        if not delete:
            self.plumber.add_extra_route(router_id, peer_cidrs,
                                         stitching_interface_ip)
        else:
            self.plumber.delete_extra_route(router_id, peer_cidrs)

    def undo_plumbing(self, **kwargs):
        self.plumber.undo_plumbing(**kwargs)


class NeutronPlumber():
    def __init__(self, conf):
        self.conf = conf
        self.keystone = KeystoneClient(conf)
        self.neutron = NeutronClient(conf)

    def add_extra_route(self, router_id, peer_cidrs,
                        stitching_interface_ip):
        routes_to_add = []
        for peer_cidr in peer_cidrs:
            routes_to_add.append({"nexthop": stitching_interface_ip,
                                 "destination": peer_cidr})
        self._add_router_route(router_id, routes_to_add)

    def delete_extra_route(self, router_id, peer_cidrs):
        routes_to_remove = []
        for peer_cidr in peer_cidrs:
            routes_to_remove.append({"destination": peer_cidr})
        self._remove_router_route(router_id, routes_to_remove)

    def _add_router_route(self, router_id, route_to_add):
        token = self.keystone.get_admin_token()
        router = self.neutron.get_router(token, router_id)
        existing_routes = router['router']['routes']
        for add_route in route_to_add:
            if add_route not in existing_routes:
                existing_routes.append(add_route)
        self._update_router_routes(token, router_id, existing_routes)
        LOG.debug("Routes on router %s updated." % router_id)

    def _remove_router_route(self, router_id, route_to_remove):
        token = self.keystone.get_admin_token()
        router = self.neutron.get_router(token, router_id)
        existing_routes = router['router']['routes']
        route_list_to_remove = []
        for route in existing_routes:
            for del_route in route_to_remove:
                if del_route['destination'] == route['destination']:
                    route_list_to_remove.append(route)
                    break
        new_routes = [x for x in existing_routes if x not in
                      route_list_to_remove]
        self._update_router_routes(token, router_id, new_routes)
        LOG.debug("Routes on router %s updated." % router_id)

    def _update_router_routes(self, token, router_id, new_routes):
        """
        Adds extra routes to the router resource.

        :param router_id: uuid of the router,
        :param new_routes: list of new routes in this format
                          "routes": [
                                       {
                                            "nexthop": "10.1.0.10",
                                            "destination": "40.0.1.0/24"
                                       },....
                                    ]
        """

        response = self.neutron.update_router(token, router_id,
                                              routes=new_routes)
        try:
            _ = response['router']['routes']
        except KeyError, err:
            err = ("Failed to update routes on the router: %s"
                   " Openstack Neutron service's response :: %s."
                   " KeyError :: %s" % (router_id, response, err))
            LOG.error(err)
            raise Exception(err)
        except Exception, err:
            LOG.error(err)
            raise Exception(err)

    def _get_new_subnet_cidr(self, token, tenant_id):
        filters = {'name': "stitching_subnet-%s" % tenant_id,
                   'fields': ['cidr']}
        ip_pool = IPNetwork('172.16.0.0/24')
        subnet_cidrs = self.neutron.get_subnets(token, filters=filters)
        ipsubnet_list = [IPNetwork(i['cidr']) for i in subnet_cidrs]
        subnets = ip_pool.subnet(29)
        for cidr in subnets:
            if cidr not in ipsubnet_list:
                return cidr
        err = ("Unable to create new subnet in tenant %s, "
               "Subnet cidrs for tenant exhausted" % tenant_id)
        raise Exception(err)

    def _create_stitching_network(self, token, tenant_id):
        name = "stitching_net-%s" % tenant_id
        attrs = {"name": name}
        stitching_net = self.neutron.create_network(
            token, self.conf.keystone_authtoken.admin_tenant_id, attrs=attrs)
        cidr = self._get_new_subnet_cidr(token, tenant_id)
        attrs = {"network_id": stitching_net['id'], "cidr": cidr,
                 "ip_version": 4, 'name': "stitching_subnet-%s" % tenant_id}
        stitching_subnet = self.neutron.create_subnet(
            token, self.conf.keystone_authtoken.admin_tenant_id, attrs=attrs)
        return [stitching_net], stitching_subnet

    def _check_stitching_network(self, token, tenant_id, router_id):
        stitching_net, stitching_subnet = self._create_stitching_network(
            token, tenant_id)
        if not stitching_net:
            err = ("Unable to create stitching network for tenant %s" %
                   tenant_id)
            LOG.error(err)
            raise Exception(err)

        net_id = stitching_net[0]['id']
        subnet_id = stitching_subnet['id']
        cidr = stitching_subnet['cidr']
        gateway_ip = stitching_subnet['gateway_ip']
        if router_id:
            filters = {"network_id": net_id,
                       "device_owner": "network:router_interface",
                       "device_id": router_id}
            router_if = self.neutron.get_ports(token, filters)
            if not router_if:
                self.neutron.add_router_interface(token, router_id,
                                                  {'subnet_id': subnet_id})
        return net_id, cidr, gateway_ip

    def _check_router_gateway(self, token, floating_net_id, router_id):
        filters = {'device_owner': "network:router_gateway",
                   'device_id': router_id}
        gw_port = self.neutron.get_ports(token, filters)
        if not gw_port:
            self.neutron.add_router_gateway(token, router_id,
                                            floating_net_id)

    def clear_router_routes(self, router_id):
        token = self.keystone.get_admin_token()
        response = self.neutron.update_router(token, router_id,
                                              routes=None)
        return response

    def create_stitching_for_svc(self, tenant_id, router_id,
                                 fip_required):
        token = self.keystone.get_admin_token()
        net_id, cidr, gateway_ip = self._check_stitching_network(
            token, tenant_id, router_id)
        attrs = {'port_security_enabled': False,
                 'name': 'nfp-owned-stitching-port'}
        # stitching port belongs to services tenant, so tenant_id is not set
        hotplug_port = self.neutron.create_port(token, "", net_id,
                                                attrs)
        # self.nova.attach_interface(token, tenant_id, instance_id,
        #                           hotplug_port['id'])
        stitching_fip = None
        if fip_required:
            floating_net_id = self.conf.keystone_authtoken.internet_ext_network
            self._check_router_gateway(token, floating_net_id, router_id)
            stitching_fip = self.neutron.create_floatingip(
                token, floating_net_id,
                hotplug_port['id'])['floating_ip_address']
        return {"port": hotplug_port,
                "floating_ip": stitching_fip,
                "gateway": gateway_ip,
                "cidr": cidr}

    def make_ports_down(self, ports):
        token = self.keystone.get_admin_token()
        for port in ports:
            self.neutron.update_port(token, port, admin_state_up=False)

    def undo_plumbing(self, **kwargs):
        subnet_id = kwargs['subnet_id']
        port_id = kwargs['port_id']
        network_id = kwargs['network_id']
        router_id = kwargs['router_id']
        token = self.keystone.get_admin_token()
        fip = self.neutron.get_floating_ips(token, port_id=port_id)
        if fip:
            # delete the fip
            self.neutron.delete_floatingip(token, fip[0]['id'])
        # delete stitching port
        self.neutron.delete_port(token, port_id)
        # delete router interface
        interface_info = {'subnet_id': subnet_id}
        self.neutron.remove_router_interface(token, router_id,
                                             interface_info)
        # delete SUBNET
        self.neutron.delete_subnet(token, subnet_id)
        # delete NETWORK
        self.neutron.delete_network(token, network_id)
