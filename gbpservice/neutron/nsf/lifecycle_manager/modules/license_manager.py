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
import oslo_messaging

from gbpservice.neutron.nsf.core.main import Event
from gbpservice.neutron.nsf.core.main import RpcAgent


def rpc_init(controller):
    rpcmgr = RpcHandler(cfg.CONF, controller)
    agent = RpcAgent(controller, host=cfg.CONF.host,
                     topic="NFP_LICENSE_MANAGER", manager=rpcmgr)
    controller.register_rpc_agents([agent])


def events_init(controller):
    evs = [
        Event(id='APPLY_LICENSE', data=None, handler=LicenseManager),
        Event(id='DETACH_LICENSE', data=None, handler=LicenseManager)]
    controller.register_events(evs)


def module_init(controller):
    events_init(controller)
    rpc_init(controller)


class RpcHandler(object):
    RPC_API_VERSION = '1.0'
    target = oslo_messaging.Target(version=RPC_API_VERSION)

    def __init__(self, conf, controller):
        super(RpcHandler, self).__init__()
        self.conf = conf
        self._controller = controller

    # Health check status change notification from Configurator
    def device_licensed(self, context, device_info):
        license_handler = LicenseHandler(self._controller)
        return license_handler.handle_licenfing_complete(context, device_info)

    def device_licenfing_failed(self, context, device_info):
        license_handler = LicenseHandler(self._controller)
        return license_handler.handle_licenfing_failed(context, device_info)


class LicenseManager(object):
    def __init__(self, controller):
        self.controller = controller

    def event_method_mapping(self, state, lifecycle_handler):
        state_machine = {
            "APPLY_LICENSE": LicenseHandler.apply_license,
            "DETACH_LICENSE": LicenseHandler.detach_license,
            "LICENSE_FAILED": LicenseHandler.handle_license_failed,
        }
        if state not in state_machine:
            raise Exception("Invalid state")
        else:
            return state_machine[state]

    def handle_event(self, event):
        license_handler = LicenseHandler(self.controller)
        self.event_method_mapping(event.id, license_handler)(
            event.data)


class LicenseHandler(object):
    def __init__(self, controller):
        self._controller = controller

    def apply_license(self, license_request):
        pass

    def detach_license(self, detach_license_request):
        pass

    def handle_licenfing_complete(self, context, device_info):
        pass

    def handle_licenfing_failed(self, context, device_info):
        pass
