from wsme import types as wtypes
from wsmeext import pecan as wsme_pecan
from pecan import rest
from pecan import expose
import controller


class ControllerResolver(object):
    """this class send parameter to controller class according to query string"""
    device_config = controller.Controller("device_config")
    service_config = controller.Controller("service_config")
    get_notifications = controller.Controller("get_notifications")


class V1Controller(object):

    """ all request with nsf in curl land here"""
    nsf = ControllerResolver()

    @wsme_pecan.wsexpose(wtypes.text)
    def get(self):
        # TODO(blogan): decide what exactly should be here, if anything
        return {'versions': [{'status': 'CURRENT',
                              'updated': '2014-12-11T00:00:00Z',
                              'id': 'v1'}]}
