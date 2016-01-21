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

from oslo.config import cfg

from gbpservice.neutron.nsf.core.main import ServiceController
from gbpservice.neutron.nsf.core.main import Event
from gbpservice.neutron.nsf.core.main import RpcAgent
from gbpservice.neutron.nsf.core.main import RpcManager
from gbpservice.neutron.nsf.db import nsf_db as nsf_db


def rpc_init(controller):
    rpcmgr = RpcHandler(cfg.CONF, controller)
    agent = RpcAgent(
            controller,
            host=cfg.CONF.host,
            topic="NSF_LICENSE_MANAGER",
            manager=rpcmgr
            )
    controller.register_rpc_agents([agent])

def events_init(controller):
    evs = [
        Event(id='APPLY_LICENSE', data=None, handler=LicenseManager),
        Event(id='DETACH_LICENSE', data=None, handler=LicenseManager)]
    controller.register_events(evs)


def module_init(controller):
    events_init(controller)
    rpc_init(controller)


class RpcHandler(RpcManager):
    RPC_API_VERSION = '1.0'

    def __init__(self, conf, controller):
        super(RpcHandler, self).__init__()
        self.conf = conf
        self._controller = controller

    # Health check status change notification from Configurator
    def device_licensed(self, context, **kwargs):
        resource = kwargs.get('resource')
        status = kwargs.get('status')
        ev = self._controller.event(id='DEVICE_ACTIVE', data=resource, handler=None)


class LicenseManager(object):
    def __init__(self):
        pass

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

    def handle_event(self, ev):
        if ev.handler:
            device_lm_handler = ev.handler
        else:
            device_lm_handler = LicenseHandler()
        self.event_method_mapping(ev.id, device_lm_handler)(ev.data)


class LicenseHandler(object):
    def __init__(self, request, state="INIT", _id=None):
        self.id = _id
        self.state = state
        self.request = request

    def create_network_service_device(self, profile, device_classification):
        """ Returns device instance for a new service

        This method either returns existing device which could be reused for a
        new service or it creates new device instance
        """
        device = None