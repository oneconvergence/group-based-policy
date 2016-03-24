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

import json
import oslo_serialization.jsonutils as jsonutils
import subprocess

from neutron.agent.common import config
from gbpservice.nfp.configurator.lib import constants
from gbpservice.nfp.configurator.lib import demuxer
from neutron.common import rpc as n_rpc
from gbpservice.nfp.configurator.lib import schema_validator
from oslo_config import cfg
from oslo_log import log as logging
import oslo_messaging
import pecan
from pecan import rest

LOG = logging.getLogger(__name__)
TOPIC = 'configurator'

"""Implements all the APIs Invoked by HTTP requests.

Implements following HTTP methods.
    -get
    -post
    -put
According to the HTTP request received from config-agent this class make
call/cast to configurator and return response to config-agent

"""

notifications = []

class Controller(rest.RestController):

    def __init__(self, method_name):
        try:
            self.host = subprocess.check_output(
                'hostname', shell=True).rstrip()
            self.rpcclient = RPCClient(topic=TOPIC, host=self.host)
            self.method_name = method_name
            super(Controller, self).__init__()
            self._demuxer = demuxer.ServiceAgentDemuxer()
            self._schema_validator = schema_validator.SchemaValidator()

        except Exception as err:
            msg = (
                "Failed to initialize Controller class  %s." %
                str(err).capitalize())
            LOG.error(msg)

    def _push_notification(self, context, request_info, result):
        response = {
            'receiver': constants.SERVICE_ORCHESTRATOR,
            'resource': constants.RESOURCE_HEAT,
            'method': constants.NFD_NOTIFICATION,
            'kwargs': [
                {
                    'context': context,
                    'resource': constants.RESOURCE_HEAT,
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
            notification_data = json.dumps(notifications)
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
        """Method of REST server to handle all the post requests.

        This method sends an RPC cast to configurator according to the
        HTTP request.

        :param body: This method excepts dictionary as a parameter in HTTP
        request and send this dictionary to configurator with RPC cast.

        Returns: None

        """

        try:
            body = None
            if pecan.request.is_body_readable:
                body = pecan.request.json_body

            if not self._schema_validator.decode(body):
                msg = ("Decode failed for request data=%s" %
                       (body))
                raise Exception(msg)

            service_type = self._demuxer.get_service_type(body)
            if (constants.invalid_service_type == service_type):
                msg = ("Configurator received invalid service type %s." %
                       service_type)
                raise Exception(msg)

            # Assuming config list will have only one element
            config_data = body['config'][0]
            context = config_data['kwargs']['context']
            request_info = config_data['kwargs']['request_info']

            # Only heat is supported presently
            if (service_type == "heat"):
                result = "unhandled"
                self._push_notification(context, request_info, result)
            else:
                result = "error"
                self._push_notification(context, request_info, result)
        except Exception as err:
            pecan.response.status = 400
            msg = ("Failed to serve HTTP post request %s %s."
                   % (self.method_name, str(err).capitalize()))
            LOG.error(msg)
            error_data = self._format_description(msg)
            return jsonutils.dumps(error_data)

    @pecan.expose(method='PUT', content_type='application/json')
    def put(self, **body):
        """Method of REST server to handle all the put requests.

        This method sends an RPC cast to configurator according to the
        HTTP request.

        :param body: This method excepts dictionary as a parameter in HTTP
        request and send this dictionary to configurator with RPC cast.

        Returns: None

        """
        try:
            body = None
            if pecan.request.is_body_readable:
                body = pecan.request.json_body

            self.rpcclient.cast(self.method_name, body)
            msg = ("Successfully served HTTP request %s" % self.method_name)
            LOG.info(msg)
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


"""Implements call/cast methods used in REST Controller.

Implements following methods.
    -call
    -cast
This class send an RPC call/cast to configurator according to the data sent
by Controller class of REST server.

 """


class RPCClient(object):

    API_VERSION = '1.0'

    def __init__(self, topic, host):

        self.topic = topic
        self.host = host
        target = oslo_messaging.Target(
            topic=self.topic,
            version=self.API_VERSION)
        n_rpc.init(cfg.CONF)
        self.client = n_rpc.get_client(target)

    def call(self):
        """Method for sending call request on behalf of REST Controller.

        This method sends an RPC call to configurator.

        Returns: Notification data sent by configurator.

        """
        cctxt = self.client.prepare(server=self.host)
        return cctxt.call(self,
                          'get_notifications')

    def cast(self, method_name, request_data):
        """Method for sending cast request on behalf of REST Controller.

        This method sends an RPC cast to configurator according to the
        method_name passed by COntroller class of REST server.

        :param method_name:method name can be any of the following.


        Returns: None.

        """
        cctxt = self.client.prepare(server=self.host)
        return cctxt.cast(self,
                          method_name,
                          request_data=request_data)

    def to_dict(self):
        """This function return empty dictionary.

        For making RPC call/cast it internally requires context class that
        contains to_dict() function. Here we are sending context inside
        request data so we are passing class itself as a context that
        contains to_dict() function.

        Returns: Dictionary.

        """
        return {}
