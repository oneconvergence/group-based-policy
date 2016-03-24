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
from neutron.common import rpc as n_rpc
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


class Controller(rest.RestController):

    def __init__(self, method_name):
        try:
            self.host = subprocess.check_output(
                'hostname', shell=True).rstrip()
            self.rpcclient = RPCClient(topic=TOPIC, host=self.host)
            self.method_name = method_name
            super(Controller, self).__init__()
        except Exception as err:
            msg = (
                "Failed to initialize Controller class  %s." %
                str(err).capitalize())
            LOG.error(msg)

    @pecan.expose(method='GET', content_type='application/json')
    def get(self):
        """Method of REST server to handle request get_notifications.

        This method send an RPC call to configurator and returns Notification
        data to config-agent

        Returns: Dictionary that contains Notification data

        """

        try:
            notification_data = json.dumps(self.rpcclient.call())
            msg = ("NOTIFICATION_DATA sent to config_agent %s"
                   % notification_data)
            LOG.info(msg)
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

            self.rpcclient.cast(self.method_name, body)
            msg = ("Successfully served HTTP request %s" % self.method_name)
            LOG.info(msg)
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
