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

from gbpservice.nfp.core import poll as core_pt
import gbpservice.nfp.lib.transport as transport

from gbpservice.nfp.config_orchestrator.agent import firewall as fw
from gbpservice.nfp.config_orchestrator.agent import loadbalancer as lb
from gbpservice.nfp.config_orchestrator.agent import vpn as vpn
from gbpservice.nfp.core import log as nfp_logging

from neutron import context as n_context

LOG = nfp_logging.getLogger(__name__)

STOP_POLLING = {'poll': False}
CONTINUE_POLLING = {'poll': True}

"""Periodic Class to service events for visiblity."""


class OTCServiceEventsHandler(core_pt.PollEventDesc):

    def __init__(self, sc, conf):
        self._sc = sc
        self._conf = conf
        self.fw_agent = fw.FirewallNotifier(conf, sc)
        self.lb_agent = lb.LoadbalancerNotifier(conf, sc)
        self.vpn_agent = vpn.VpnNotifier(conf, sc)

    def handle_event(self, ev):
        if ev.id == 'SERVICE_CREATED':
            data = ev.data
            self._create_service(data['context'],
                                 data['resource'])

        elif ev.id == 'SERVICE_DELETED':
            data = ev.data
            self._delete_service(data['context'],
                                 data['resource'])

    def poll_event_cancel(self, event):
        msg = ("Poll Event =%s got time out Event Data = %s " %
               (event.id, event.data))
        LOG.info('%s' % (msg))

    def _create_service(self, context, resource):
        ctxt = n_context.Context.from_dict(context)
        transport.send_request_to_configurator(self._conf,
                                               ctxt, resource,
                                               "CREATE",
                                               network_function_event=True)

    def _delete_service(self, context, resource):
        ctxt = n_context.Context.from_dict(context)
        transport.send_request_to_configurator(self._conf,
                                               ctxt, resource,
                                               "DELETE",
                                               network_function_event=True)

    @core_pt.poll_event_desc(event='SERVICE_CREATE_PENDING', spacing=2)
    def create_sevice_pending_event(self, ev):
        event_data = ev.data
        ctxt = n_context.Context.from_dict(event_data['context'])

        try:
            if (event_data['service_type']).lower() == 'firewall':
                request_data = self.fw_agent._prepare_request_data(
                    ctxt,
                    event_data[
                        'nf_id'],
                    event_data[
                        'resource_id'],
                    event_data[
                        'fw_mac'],
                    event_data[
                        'service_type'])
                msg = ("%s : %s " % (request_data, event_data['fw_mac']))
                LOG.info('%s' % (msg))

            if (event_data['service_type']).lower() == 'loadbalancer':
                request_data = self.lb_agent._prepare_request_data(
                    ctxt,
                    event_data[
                        'nf_id'],
                    event_data[
                        'resource_id'],
                    event_data[
                        'vip_id'],
                    event_data[
                        'service_type'])
                msg = ("%s : %s " % (request_data, event_data['vip_id']))
                LOG.info('%s' % (msg))

            if (event_data['service_type']).lower() == 'vpn':
                request_data = self.vpn_agent._prepare_request_data(
                    ctxt,
                    event_data[
                        'nf_id'],
                    event_data[
                        'resource_id'],
                    event_data[
                        'ipsec_id'],
                    event_data[
                        'service_type'])
                msg = ("%s : %s " % (request_data, event_data['ipsec_id']))
                LOG.info('%s' % (msg))

            if request_data['nf']['status'] == 'ACTIVE':
                new_event_data = {'resource': None,
                                  'context': ctxt.to_dict()}
                nfp_log_ctx = nfp_logging.get_logging_context()
                new_event_data['resource'] = {'eventtype': 'SERVICE',
                                              'eventid': 'SERVICE_CREATED',
                                              'eventdata': request_data,
                                              'info': {'context':
                                                      {'logging_context':
                                                      nfp_log_ctx}}}

                new_ev = self._sc.new_event(id='SERVICE_CREATED',
                                            key='SERVICE_CREATED',
                                            data=new_event_data)
                self._sc.post_event(new_ev)
                return STOP_POLLING
            else:
                return CONTINUE_POLLING
        except Exception as e:
            LOG.error('%s' % (e))
            return STOP_POLLING
