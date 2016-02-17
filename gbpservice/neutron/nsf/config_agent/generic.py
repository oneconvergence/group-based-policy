import sys
import ast

from oslo_config import cfg
from oslo_messaging import target
from oslo_log import log as logging
from gbpservice.neutron.nsf.config_agent import RestClientOverUnix as rc
from gbpservice.neutron.nsf.config_agent import topics
from neutron.common import rpc as n_rpc

LOG = logging.getLogger(__name__)

Version = "v1"  # v1/v2/v3#


class Generic(object):
    API_VERSION = '1.0'

    def __init__(self):
        self.topic = topics.GC_NSF_PLUGIN_TOPIC
        _target = target.Target(topic=self.topic,
                                version=self.API_VERSION)
        self.client = n_rpc.get_client(_target)
        self.cctxt = self.client.prepare(version=self.API_VERSION,
                                         topic=self.topic)

    def network_function_device_notification(self, resource, **kwargs):
        context = kwargs.get('context')
        del kwargs['context']
        notification_data = {'notification_data': {}}
        notification_data['notification_data'].\
            update({'resource': resource,
                    'kwargs': kwargs})
        self.cctxt.cast(context, 'network_function_device_notification',
                        notification_data=notification_data)


class GcAgent(object):
    RPC_API_VERSION = '1.0'
    target = target.Target(version=RPC_API_VERSION)

    def __init__(self, conf, sc):
        self._conf = conf
        self._sc = sc
        super(GcAgent, self).__init__()

    def _post(self, context, request_data):
        for ele in request_data['request_data']['config']:
            ele['kwargs'].update({'context': context})
        try:
            resp, content = rc.post('create_network_function_device_config',
                                    body=request_data)
        except:
            LOG.error(
                "create_network_function_device_config -> request failed.")

    def _delete(self, context, request_data):
        for ele in request_data['request_data']['config']:
            ele['kwargs'].update({'context': context})
        try:
            resp, content = rc.post('delete_network_function_device_config',
                                    body=request_data, delete=True)
        except:
            LOG.error(
                "delete_network_function_device_config -> request failed.")

    def create_network_function_device_config(self, context, request_data):
        self._post(context, request_data)

    def delete_network_function_device_config(self, context, request_data):
        self._delete(context, request_data)
