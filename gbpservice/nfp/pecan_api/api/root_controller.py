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

import pecan

import pecan

try:
    from gbpservice.tests.contrib.nfp_service.reference_configurator\
        import controllers as ref_controllers
    from gbpservice.nfp.base_configurator import controllers as \
        base_controllers
except:
    pass

class RootController(object):
    """This is root controller that forward the request to __init__.py
    file inside controller folder inside v1

    """
    if pecan.base_with_vm:
        v1 = ref_controllers.V1Controller()
    else:
        v1 = base_controllers.V1Controller()

    @pecan.expose()
    def get(self):
        # TODO(blogan): once a decision is made on how to do versions, do that
        # here
        return {'versions': [{'status': 'CURRENT',
                              'updated': '2014-12-11T00:00:00Z',
                              'id': 'v1'}]}
