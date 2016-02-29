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

from oslo_config import cfg
from oslo_messaging import target
from oslo_log import log as logging
from neutron import manager
from gbpservice.nfp.config_agent import topics
from neutron.common import rpc as n_rpc
from neutron.plugins.common import constants

LOG = logging.getLogger(__name__)
Version = 'v1'  # v1/v2/v3#


class RPCClient(object):
    API_VERSION = '1.0'

    def __init__(self, topic):
        self.topic = topic
        _target = target.Target(topic=self.topic,
                                version=self.API_VERSION)
        n_rpc.init(cfg.CONF)
        self.client = n_rpc.get_client(_target)
        self.cctxt = self.client.prepare(version=self.API_VERSION,
                                         topic=self.topic)


def prepare_request_data(resource, kwargs, service_type):

    request_data = {'info': {
        'version': Version,
        'service_type': service_type
    },

        'config': [{
            'resource': resource,
            'kwargs': kwargs
        }]
    }

    return request_data
