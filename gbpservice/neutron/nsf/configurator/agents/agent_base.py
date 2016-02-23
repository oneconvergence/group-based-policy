
from gbpservice.neutron.nsf.configurator.lib import (
                            generic_config_constants as const)

"""Implements base class for all service agents.

Common methods for service agents are implemented in this class. Configurator
module invokes these methods through the service agent's child class instance.

"""


class AgentBaseRPCManager(object):
    def __init__(self, sc, conf):
        self._sc = sc
        self.conf = conf

    def validate_request(self, sa_info_list, notification_data):
        if (isinstance(sa_info_list, list) and
                isinstance(notification_data, dict)):
            return True
        else:
            return False

    def forward_request(self, sa_info_list, notification_data):
        """Forwards the RPC message from configurator to service agents.

        Checks if the request message contains multiple data blobs. If multiple
        data blobs are found, a batch event is generated otherwise a single
        event.

        :param sa_info_list: List of data blobs prepared by de-multiplexer
        for service agents processing.
        :param notification_data: Notification blobs prepared by the service
        agents after processing requests blobs. Each request blob will have
        a corresponding notification blob.

        Returns: None

        """

        # In case of malformed input, send failure notification
        if not self.validate_request(sa_info_list, notification_data):
            # TODO: Need to send failure notification
            return

        # Multiple request data blobs needs batch processing. Send batch
        # processing event or do direct processing of single request data blob
        if (len(sa_info_list) > 1):
            args_dict = {
                         'sa_info_list': sa_info_list,
                         'notification_data': notification_data
                        }
            ev = self._sc.event(id='PROCESS_BATCH', data=args_dict)
            self._sc.rpc_event(ev)
        else:
            sa_info_list[0]['context'].update(
                            {'notification_data': notification_data})
            getattr(self, sa_info_list[0]['method'])(
                                            sa_info_list[0]['context'],
                                            **sa_info_list[0]['kwargs'])


class AgentBaseEventHandler(object):
    def __init__(self, sc, drivers, rpcmgr, nqueue):
        self._sc = sc
        self.drivers = drivers
        self._rpcmgr = rpcmgr
        self.nqueue = nqueue

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

        try:
            # Get service agent information list and notification data list
            # from the event data
            sa_info_list = ev.data.get('sa_info_list')
            notification_data = ev.data.get('notification_data')

            # Process the first data blob from the service information list.
            # Get necessary parameters needed for driver method invocation.
            method = sa_info_list[0]['method']
            kwargs = sa_info_list[0]['kwargs']
            context = sa_info_list[0]['context']
            service_type = kwargs.get('kwargs').get('service_type')

            # Get the service driver and invoke its method
            driver = self._get_driver(service_type)

            # Service driver should return "success" on successful API
            # processing. All other return values and exceptions are treated
            # as failures.
            result = getattr(driver, method)(context, **kwargs)
            success = True
        except Exception as err:
            result = ("Failed to process %s request for %s service type. %s" %
                      (method, service_type, str(err).capitalize()))

            success = False
        finally:
            # Prepare success notification and populate notification data list
            msg = {
                    'receiver': const.ORCHESTRATOR,
                    'resource': const.ORCHESTRATOR,
                    'method': "network_function_device_notification",
                    'kwargs': [{'context': context, 'result': result}]
                }

            # If the data processed is first one, then prepare notification
            # dict. Otherwise, append the notification to the kwargs list.
            # Whether it is a data batch or single data blob request,
            # notification generated will be single dictionary. In case of
            # batch, multiple notifications are sent in the kwargs list.
            if not notification_data:
                notification_data.update(msg)
            else:
                data = {'context': context,
                        'result': result}
                notification_data['kwargs'].extend(data)

        if success:
            # Remove the processed request data blob from the service
            # information list. APIs will always process first data blob in
            # the request.
            sa_info_list.pop(0)

            # Invoke base class method to process further data blobs in the
            # request
            self._rpcmgr.forward_request(sa_info_list, notification_data)
        else:
            self.nqueue.put(notification_data)
            raise Exception(err)


def init_agent_complete(cm, sc, conf):
    """Placeholder method to satisfy configurator module agent loading."""
    pass


def init_agent(cm, sc, conf, nqueue):
    """Placeholder method to satisfy configurator module agent loading."""
    pass
