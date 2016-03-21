
from openstack_driver import KeystoneClient as keystone
from openstack_driver import NeutronClient as neutron
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class SCPlumber():
    """ Class to perform plumbing function
    """
    def __init__(self):
        self.plumber = _NeutronPlumber()

    def hotplug_stitching_port(self, tenant_id, stitching_nw_name,
                               instance_id, fip_required=False):
        # find network with this name in this tenant
        # If network not present, create a new one
        # create a port for hotplug with port security disabled
        # hotplug this port in the given instance
        # assigne fip if needed
        # After successful operation, return port details.
        self.plumber.create_and_hotplug(tenant_id, stitching_nw_name,
                                        instance_id)
        pass

    def update_router_service_gateway(self, router_id, peer_cidrs,
                                      stitching_interface_ip, delete=False):
        if not delete:
            self.plumber._add_extra_route(router_id, peer_cidrs,
                                          stitching_interface_ip)
        else:
            self.plumber._delete_extra_route(router_id, peer_cidrs,
                                             stitching_interface_ip)


class _NeutronPlumber():
    def _add_extra_route(self, router_id, peer_cidrs,
                         stitching_interface_ip):
        routes_to_add = []
        for peer_cidr in peer_cidrs:
            routes_to_add.append({"nexthop": stitching_interface_ip,
                                 "destination": peer_cidr})
        self.add_router_route(router_id, routes_to_add)

    def _delete_extra_route(self, router_id, peer_cidrs,
                            stitching_interface_ip):
        routes_to_remove = []
        for peer_cidr in peer_cidrs:
            routes_to_remove.append({"destination": peer_cidr})
        self.remove_router_route(router_id, routes_to_remove)

    def add_router_route(self, token, router_id, route_to_add):
        token = keystone.get_admin_token(self)
        router = neutron.get_router(self, token, router_id)
        existing_routes = router['router']['routes']
        if route_to_add not in existing_routes:
            existing_routes.append(route_to_add)
            self.update_router_routes(router_id, existing_routes)
        LOG.debug(_("Routes on router %s updated." % router_id))

    def remove_router_route(self, router_id, route_to_remove):
        token = keystone.get_admin_token(self)
        router = neutron.get_router(self, token, router_id)
        existing_routes = router['router']['routes']
        route_list_to_remove = []
        for route in existing_routes:
            if route_to_remove['destination'] == route['destination']:
                route_list_to_remove.append(route)
        new_routes = [x for x in existing_routes if x not in
                      route_list_to_remove]
        self.update_router_routes(router_id, new_routes)
        LOG.debug(_("Routes on router %s updated." % router_id))

    def update_router_routes(self, token, router_id, new_routes):
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
        router_info = {"router": {"routes": new_routes}}

        response = neutron.update_router(token, router_id,
                                         router_info)
        try:
            resp_router = response['routes']
        except KeyError, err:
            err = ("Failed to update routes on the router: %s"
                   " Openstack Neutron service's response :: %s."
                   " KeyError :: %s" % (router_id, response, err))
            LOG.error(err)
            raise Exception(err)
        except Exception, err:
            LOG.error(err)
            raise Exception(err)

    def create_and_hotplug(self, tenant_id, stitching_nw_name,
                           instance_id):
        token = keystone.get_admin_token(self)
        neutron.get_network(token, tenant_id, stitching_nw_name)