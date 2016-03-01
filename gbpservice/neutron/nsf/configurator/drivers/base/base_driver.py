import subprocess
from oslo_log import log as logging
LOG = logging.getLogger(__name__)
SUCCESS = 'SUCCESS'
FAILED = 'FAILED'


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

    def configure_healthmonitor(self, context, kwargs):
        # Ping based basic HM support provided by BaseDriver.
        # Service provider can override the method implementation
        # if they want to support other types.
        ip = kwargs.get('mgmt_ip')
        COMMAND = 'ping -c5 '+ip
        try:
            subprocess.check_output(COMMAND, stderr=subprocess.STDOUT,
                                    shell=True)
        except Exception:
            # LOG.error("Health check failed for vm=%s, ip=%s," % (
            #                                        kwargs.get('vmid'), ip))
            return FAILED
        return SUCCESS

    def clear_healthmonitor(self, context, kwargs):
        return SUCCESS
