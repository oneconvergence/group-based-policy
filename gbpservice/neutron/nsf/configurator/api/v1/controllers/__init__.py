from pecan import expose
from pecan import rest
from wsmeext import pecan as wsme_pecan
from wsme import types as wtypes

import controller


class ControllerResolver(object):
    """this class send parameter to controller class
    according to query string"""
    create_network_function_device_config = controller.Controller(
        "create_network_function_device_config")
    delete_network_function_device_config = controller.Controller(
        "delete_network_function_device_config")
    update_network_function_device_config = controller.Controller(
        "update_network_function_device_config")
    create_network_function_config = controller.Controller(
        "create_network_function_config")
    delete_network_function_config = controller.Controller(
        "delete_network_function_config")
    update_network_function_config = controller.Controller(
        "update_network_function_config")
    get_notifications = controller.Controller("get_notifications")


class V1Controller(object):

    """ all request with nsf in query land here"""
    nfp = ControllerResolver()

    @wsme_pecan.wsexpose(wtypes.text)
    def get(self):
        # TODO(blogan): decide what exactly should be here, if anything
        return {'versions': [{'status': 'CURRENT',
                              'updated': '2014-12-11T00:00:00Z',
                              'id': 'v1'}]}
