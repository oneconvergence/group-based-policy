#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import oslo_serialization.jsonutils as jsonutils

from oslo_log import log as logging
import pecan
from pecan import rest

LOG = logging.getLogger(__name__)
TOPIC = 'configurator'

"""Implements all the APIs Invoked by HTTP requests.

Implements following HTTP methods.
    -get
    -post

"""

notifications = []


class Controller(rest.RestController):

    def __init__(self, method_name):
        try:
            self.method_name = method_name
            self.supported_service_types = ['config_script',
                                            'firewall', 'loadbalancer', 'vpn']
            self.resource_map = {
                ('interfaces', 'healthmonitor', 'routes'): 'orchestrator',
                ('heat'): 'service_orchestrator',
                ('firewall', 'lb', 'vpn'): 'neutron'
            }
            super(Controller, self).__init__()
        except Exception as err:
            msg = (
                "Failed to initialize Controller class  %s." %
                str(err).capitalize())
            LOG.error(msg)

    def _push_notification(self, context, request_info, result, config_data):
        resource = config_data['resource']
        receiver = ''
        for key in self.resource_map.keys():
            if resource in key:
                receiver = self.resource_map[key]

        response = {
            'receiver': receiver,
            'resource': resource,
            'method': 'network_function_device_notification',
            'kwargs': [
                {
                    'context': context,
                    'resource': resource,
                    'request_info': request_info,
                    'result': result
                }
            ]
        }

        notifications.append(response)

    @pecan.expose(method='GET', content_type='application/json')
    def get(self):
        """Method of REST server to handle request get_notifications.

        This method send an RPC call to configurator and returns Notification
        data to config-agent

        Returns: Dictionary that contains Notification data

        """

        global notifications
        try:
            notification_data = jsonutils.dumps(notifications)
            msg = ("NOTIFICATION_DATA sent to config_agent %s"
                   % notification_data)
            LOG.info(msg)
            notifications = []
            return notification_data
        except Exception as err:
            pecan.response.status = 400
            msg = ("Failed to get notification_data  %s."
                   % str(err).capitalize())
            LOG.error(msg)
            error_data = self._format_description(msg)
            return jsonutils.dumps(error_data)

    @pecan.expose(method='POST', content_type='application/json')
    def post(self, **body):
        try:
            global notifications
            body = None
            if pecan.request.is_body_readable:
                body = pecan.request.json_body

            service_type = body['info'].get('service_type')

            # Assuming config list will have only one element
            config_data = body['config'][0]
            context = config_data['kwargs']['context']
            request_info = config_data['kwargs']['request_info']

            if service_type.lower() in self.supported_service_types:
                result = "handled"
                self._push_notification(context, request_info,
                                        result, config_data)
            else:
                result = "unhandled"
                self._push_notification(context, request_info,
                                        result, config_data)
        except Exception as err:
            pecan.response.status = 400
            msg = ("Failed to serve HTTP post request %s %s."
                   % (self.method_name, str(err).capitalize()))
            LOG.error(msg)
            error_data = self._format_description(msg)
            return jsonutils.dumps(error_data)

    @pecan.expose(method='PUT', content_type='application/json')
    def put(self, **body):
        try:
            body = None
            if pecan.request.is_body_readable:
                body = pecan.request.json_body

            service_type = body['info'].get('service_type')

            # Assuming config list will have only one element
            config_data = body['config'][0]
            context = config_data['kwargs']['context']
            request_info = config_data['kwargs']['request_info']

            if service_type.lower() in self.supported_service_types:
                result = "handled"
                self._push_notification(context, request_info,
                                        result, config_data)
            else:
                result = "error"
                self._push_notification(context, request_info,
                                        result, config_data)
        except Exception as err:
            pecan.response.status = 400
            msg = ("Failed to serve HTTP put request %s %s."
                   % (self.method_name, str(err).capitalize()))
            LOG.error(msg)
            error_data = self._format_description(msg)
            return jsonutils.dumps(error_data)

    def _format_description(self, msg):
        """This methgod formats error description.

        :param msg: An error message that is to be formatted

        Returns: error_data dictionary
        """

        error_data = {'failure_desc': {'msg': msg}}
        return error_data
