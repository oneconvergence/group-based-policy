from oslo_log import log as logging
LOG = logging.getLogger(__name__)
SUCCESS = 'SUCCESS'


class BaseDriver(object):
    """Every service vendor must inherit this class. If any service vendor wants
    to add extra methods for their service, apart from below given, they should
    add method definition here and implement the method in their driver
    """
    def __init__(self):
        pass

    def configure_interfaces(self, context, kwargs):
        return SUCCESS

    def clear_interfaces(self, context, kwargs):
        return SUCCESS

    def configure_routes(self, context, kwargs):
        return SUCCESS

    def clear_routes(self, context, kwargs):
        return SUCCESS
