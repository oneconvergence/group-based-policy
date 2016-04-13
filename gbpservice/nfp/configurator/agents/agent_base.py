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

import pika

from gbpservice.nfp.configurator.lib import constants as const
from oslo_log import log as logging

LOG = logging.getLogger(__name__)

"""Implements base class for all service agents.

Common methods for service agents are implemented in this class. Configurator
module invokes these methods through the service agent's child class instance.

"""


class AgentBaseRPCManager(object):

    def __init__(self, sc, conf):
        self.sc = sc
        self.conf = conf

    def validate_request(self, sa_req_list, notification_data):
        """Preliminary validation of function input.

        :param sa_req_list: List of data blobs prepared by de-multiplexer
        for service agents processing.
        :param notification_data: Notification blobs prepared by the service
        agents after processing requests blobs. Each request blob will have
        a corresponding notification blob.

        Returns: True if validation passes. False if validation fails.

        """

        if (isinstance(sa_req_list, list) and
                isinstance(notification_data, dict)):
            return True
        else:
            return False

    def process_request(self, sa_req_list, notification_data):
        """Forwards the RPC message from configurator to service agents.

        Checks if the request message contains multiple data blobs. If multiple
        data blobs are found, a batch event is generated otherwise a single
        event.

        :param sa_req_list: List of data blobs prepared by de-multiplexer
        for service agents processing.
        :param notification_data: Notification blobs prepared by the service
        agents after processing requests blobs. Each request blob will have
        a corresponding notification blob.

        Returns: None

        """

        # In case of malformed input, send failure notification
        if not self.validate_request(sa_req_list, notification_data):
            # TODO(JAGADISH): Need to send failure notification
            return

        # Multiple request data blobs needs batch processing. Send batch
        # processing event or do direct processing of single request data blob
        if (len(sa_req_list) > 1):
            args_dict = {
                'sa_req_list': sa_req_list,
                'notification_data': notification_data
            }
            ev = self.sc.new_event(id=const.EVENT_PROCESS_BATCH,
                                   data=args_dict, key=None)
            self.sc.post_event(ev)
        else:
            sa_req_list[0]['context'].update(
                {'notification_data': notification_data})
            sa_req_list[0]['context'].update(
                {'resource': sa_req_list[0]['resource']})
            getattr(self, sa_req_list[0]['method'])(
                sa_req_list[0]['context'],
                **sa_req_list[0]['kwargs'])


""" RMQPublisher for under the cloud services.

    This class acts as publisher to publish all the notification events to
    under the cloud services on rabbitmq's 'configurator-notifications'queue.
"""


class AgentBaseNotification(object):

    def __init__(self, sc):
        self.sc = sc
        self.queue = const.NOTIFICATION_QUEUE
        self.rabbitmq_host = const.RABBITMQ_HOST
        self.create_connection()

    def create_connection(self):
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(
                                                  host=self.rabbitmq_host,
                                                  heartbeat_interval=0))

    def _notification(self, data):
        """Enqueues notification event into rabbitmq's
           'configurator-notifications' queue

        These events are enqueued into 'configurator-notifications' queue
        and are retrieved when get_notifications() API lands on configurator.

        :param data: Event data blob

        Returns: None

        """

        try:
            self.channel = self.connection.channel()
            self.channel.queue_declare(queue=self.queue,
                                       # make queue persistent
                                       durable=True
                                       )
            body = str(data)
            self.channel.basic_publish(exchange='',
                                       routing_key=self.queue,
                                       body=body,
                                       properties=pika.BasicProperties(
                                           # make msg persistent
                                           delivery_mode=2
                                       ))
            self.channel.close()
        except Exception as e:
            self.connection.close()
            self.create_connection()
            self._notification(data)


class AgentBaseEventHandler(object):

    def __init__(self, sc, drivers, rpcmgr):
        self.sc = sc
        self.drivers = drivers
        self.rpcmgr = rpcmgr
        self.notify = AgentBaseNotification(self.sc)

    def process_batch(self, ev):
        """Processes a request with multiple data blobs.

        Configurator processes the request with multiple data blobs and sends
        a list of service information to be processed. This function goes
        through the list of service information and invokes specific service
        driver methods. After processing each request data blob, notification
        data blob is prepared.

        :param ev: Event instance that contains information of event type and
        corresponding event data to be processed.

        """

        # Get service agent information list and notification data list
        # from the event data
        sa_req_list = ev.data.get('sa_req_list')
        notification_data = ev.data.get('notification_data')

        for request in sa_req_list:
            try:
                # Process the first data blob from the request list.
                # Get necessary parameters needed for driver method invocation.
                method = request['method']
                resource = request['resource']
                kwargs = request['kwargs']
                request_info = kwargs['kwargs']['request_info']
                # del kwargs['kwargs']['request_info']
                context = request['context']
                service_type = kwargs.get('kwargs').get('service_type')

                # Get the service driver and invoke its method
                driver = self._get_driver(service_type)

                # Service driver should return "success" on successful API
                # processing. All other return values and exceptions are
                # treated as failures.
                result = getattr(driver, method)(context, **kwargs)
                if result == 'SUCCESS':
                    success = True
                else:
                    success = False
            except Exception as err:
                result = ("Failed to process %s request. %s" %
                          (method, str(err).capitalize()))
                success = False
            finally:
                # Prepare success notification and populate notification
                # data list
                msg = {
                    'receiver': const.ORCHESTRATOR,
                    'resource': const.ORCHESTRATOR,
                    'method': const.NFD_NOTIFICATION,
                    'kwargs': [
                        {
                            'context': context,
                            'resource': resource,
                            'request_info': request_info,
                            'result': result
                        }
                    ]
                }

                # If the data processed is first one, then prepare notification
                # dict. Otherwise, append the notification to the kwargs list.
                # Whether it is a data batch or single data blob request,
                # notification generated will be single dictionary. In case of
                # batch, multiple notifications are sent in the kwargs list.
                if not notification_data:
                    notification_data.update(msg)
                else:
                    data = {
                        'context': context,
                        'resource': resource,
                        'request_info': request_info,
                        'result': result
                    }
                    notification_data['kwargs'].append(data)

            if not success:
                self.notify._notification(notification_data)
                raise Exception(msg)

        self.notify._notification(notification_data)


def init_agent_complete(cm, sc, conf):
    """Placeholder method to satisfy configurator module agent loading."""
    pass


def init_agent(cm, sc, conf):
    """Placeholder method to satisfy configurator module agent loading."""
    pass
