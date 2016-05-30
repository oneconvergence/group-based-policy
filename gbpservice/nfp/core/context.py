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

import threading

nfp_context_store = threading.local()

class NfpContext(object):
    def __init__(self, **kwargs):
        self.admin_token = kwargs.get('admin_token', None)
        self.tenant_tokens = kwargs.get('tenant_tokens', None)
        self.nfp_device_data = kwargs.get('nfp_device_data', None)
        self.nfp_service_data = kwargs.get('nfp_service_data', None)
    
    def to_dict(self):
        return {'admin_token': self.admin_token,
                'tenant_tokens': self.tenant_tokens,
                'nfp_device_data': self.nfp_device_data,
                'nfp_service_data': self.nfp_service_data}

def store_nfp_context(**kwargs):
    nfp_context_store.context = NfpContext(**kwargs)

def clear_nfp_context():
    nfp_context_store.context = None

def get_nfp_context():
    context = getattr(nfp_context_store, 'context', None)
    if context:
        return context.to_dict()
    return {}
