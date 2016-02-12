from oslo_log import log as logging
LOG = logging.getLogger(__name__)


class BaseDriver(object):
    """Every service vendor must inherit this class. If any service vendor wants
    to add extra methods for their service, apart from below given, they should
    add method definition here and implement the method in their driver
    """
    def __init__(self):
        pass

    def configure_interfaces(self, context, **kwargs):
        return None

    def clear_interfaces(self, context, floating_ip, service_vendor,
                         provider_interface_position,
                         stitching_interface_position):
        return None

    def configure_source_routes(self, context, floating_ip, service_vendor,
                                source_cidrs, destination_cidr, gateway_ip,
                                provider_interface_position):
        return None

    def delete_source_routes(self, context, floating_ip, service_vendor,
                             source_cidrs,
                             provider_interface_position):
        return None
