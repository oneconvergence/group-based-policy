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

import ast
import time

from gbpservice.nfp.core import common as nfp_common
from gbpservice.nfp.core import poll as core_pt
import gbpservice.nfp.lib.transport as transport

from gbpservice.nfp.config_orchestrator.agent import firewall as fw
from gbpservice.nfp.config_orchestrator.agent import loadbalancer as lb
from gbpservice.nfp.config_orchestrator.agent import vpn as vpn

from neutron_fwaas.db.firewall import firewall_db
from neutron_lbaas.db.loadbalancer import loadbalancer_db
from neutron_vpnaas.db.vpn import vpn_db

from oslo_log import log as oslo_logging


LOGGER = oslo_logging.getLogger(__name__)
LOG = nfp_common.log

"""Periodic Class to service events for visiblity."""


class OTCServiceEventsHandler(core_pt.PollEventDesc):

    class PullDbEntry(firewall_db.Firewall_db_mixin,
                      loadbalancer_db.LoadBalancerPluginDb,
                      vpn_db.VPNPluginDb,
                      vpn_db.VPNPluginRpcDbMixin
                      ):

        def __init__(self):
            super(PullDbEntry, self).__init__()

        def get_firewalls(self, context):
            db_data = super(PullDbEntry, self)
            return db_data.get_firewalls(context)

        def get_vips(self, context):
            db_data = super(PullDbEntry, self)
            return db_data.get_vips(context)

        def get_ipsec_site_connections(self, context):
            db_data = super(PullDbEntry, self)
            return db_data.get_ipsec_site_conns(context)

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

        elif ev.id == 'PULL_BULK_DATA':
            data = ev.data
            self._pull_bulk_data(data)

    def poll_event_cancel(self, event):
        msg = ("Poll Event =%s got time out Event Data = %s " %
               (event.id, event.data))
        LOG(LOGGER, 'INFO', '%s' % (msg))

    def _create_service(self, context, resource):
        transport.send_request_to_configurator(self._conf,
                                               context, resource,
                                               "CREATE",
                                               network_function_event=True)

    def _delete_service(self, context, resource):
        transport.send_request_to_configurator(self._conf,
                                               context, resource,
                                               "DELETE",
                                               network_function_event=True)

    def _prepare_request_data(self, event_data):
        request_data = None
        try:
            nf_instance_id = event_data.pop('nf_instance_id')
            context = event_data.pop('context')
            request_data = common.get_network_function_map(
                context, nf_instance_id)
            event_data.update(resource_data)
        except Exception as e:
            return event_data
        return event_data

    @core_pt.poll_event_desc(event='SERVICE_CREATE_PENDING', spacing=5)
    def create_sevice_pending_event(self, ev):
        event_data = ev.data
        updated_event_data = self._prepare_request_data(event_data)
        LOG(LOGGER, 'INFO', '%s' % (updated_event_data))
        if updated_event_data['nf']['status'] == 'ACTIVE':
            new_event_data = {'resource': None,
                              'context': updated_event_data['context']}
            new_event_data['resource'] = {'eventtype': 'SERVICE',
                                          'eventid': updated_event_data.pop(
                                              'eventid'),
                                          'eventdata': updated_event_data}

            new_ev = self._sc.new_event(id='SERVICE_CREATED',
                                        key='SERVICE_CREATED',
                                        data=new_event_data)
            self._sc.post_event(new_ev)
            self._sc.poll_event_done(ev)

    def _get_firewall_bulk_data(self, context, firewalls):
        fw_request_data_list = []
        for firewall in firewalls:
            try:
                firewall_desc = ast.literal_eval(firewall['description'])
                fw_mac = firewall_desc['provider_ptg_info'][0]
                nf_instance_id = firewall_desc['network_function_instance_id']
                service_type = 'firewall'
                request_data = {'nf_instance_id': nf_instance_id,
                                'fw_mac': fw_mac,
                                'service_type': service_type,
                                'neutron_resource_id': firewall['id'],
                                'context': context,
                                'eventid': 'SERVICE_CREATED'
                                }
                fw_request_data_list.append(request_data)
            except Exception as e:
                LOG(LOGGER, 'ERROR', "firewall desc : %s " e)
        return fw_request_data_list

    def _get_vip_bulk_data(self, context, vips):
        vip_request_data_list = []
        for vip in vips:
            try:
                vip_desc = ast.literal_eval(vip['description'])
                nf_instance_id = vip_desc['network_function_instance_id']
                vip_id = vip['id']
                service_type = 'loadbalancer'
                request_data = {'nf_instance_id': nf_instance_id,
                                'vip_id': fw_mac,
                                'service_type': service_type,
                                'neutron_resource_id': vip_id,
                                'context': context,
                                'eventid': 'SERVICE_CREATED'
                                }
                vip_request_data_list.append(request_data)
            except Exception as e:
                LOG(LOGGER, 'ERROR', "vip desc : %s " e)
        return vip_request_data_list

    def _get_dict_desc_from_string(self, vpn_svc):
        svc_desc = vpn_svc.split(";")
        desc = {}
        for ele in svc_desc:
            s_ele = ele.split("=")
            desc.update({s_ele[0]: s_ele[1]})
        return desc

    def _get_ipsec_site_connection_bulk_data(self, context,
                                             ipsec_site_connections):
        ipsec_request_data_list = []
        for ipsec_site_connection in ipsec_site_connections:
            try:
                ipsec_desc = self._get_dict_desc_from_string(
                    ipsec_site_connection['description'])
                nf_instance_id = ipsec_desc['network_function_instance_id']
                ipsec_id = ipsec_site_connection['id']
                service_type = 'vpn'
                request_data = {'context': context,
                                'nf_instance_id': nf_instance_id,
                                'ipsec_site_connection_id': ipsec_id,
                                'service_type': service_type,
                                'neutron_resource_id': (
                                    ipsec_site_connection['id']),
                                'eventid': 'SERVICE_DELETED'
                                }
                ipsec_request_data_list.append(request_data)
            except Exception as e:
                LOG(LOGGER, 'ERROR', "ipsec desc : %s " e)

    def _pull_bulk_data(self, data):
        try:
            context = data['context']
            pull_db = PullDbEntry()
            firewalls = pull_db.get_firewalls(context)
            vips = pull_db.get_vips(context)
            ipsec_site_connections = pull_db.get_ipsec_site_connections(
                context)

            bulk_response_data = []
            bulk_response_data.extend(
                self._get_firewall_bulk_data(context, firewalls))
            bulk_response_data.extend(self._get_vip_bulk_data(context, vips))
            bulk_response_data.extend(self.
                                      _get_ipsec_site_connection_bulk_data(
                                          context,
                                          ipsec_site_connections))

            # Stashing all the event
            for response_data in bulk_response_data:
                event = self.sc.new_event(
                    id='STASH_EVENT', key='STASH_EVENT', data=response_data)
                self.sc.stash_event(event)

        except Exception as e:
            LOG(LOGGER, 'ERROR',
                "get_bulk_network_function_context failed : Reason %s " % (
                    e))

    @core_pt.poll_event_desc(event='SERVICE_OPERATION_POLL_EVENT', spacing=5)
    def service_operation_poll_stash_event(self, ev):
        events = self.sc.get_stashed_events()
        time.sleep(0)
        for event in events:
            data = event.data

            if data['eventid'] == "SERVICE_CREATED":
                new_event = self._sc.new_event(id='SERVICE_CREATE_PENDING',
                                               key='SERVICE_CREATE_PENDING',
                                               data=data)
                self._sc.poll_event(new_event)

            elif data['eventid'] == "SERVICE_DELETED":
                updated_event_data = self._prepare_request_data(data)
                LOG(LOGGER, 'INFO', '%s' % (updated_event_data))
                if updated_event_data['nf']['status'] == 'ACTIVE':
                    new_event_data = {'resource': None,
                                      'context': updated_event_data['context']}
                    new_event_data['resource'] = {'eventtype': 'SERVICE',
                                                  'eventid': (
                                                      updated_event_data.pop(
                                                          'eventid')),
                                                  'eventdata': (
                                                      updated_event_data)
                                                  }
                    ev = self._sc.new_event(id="SERVICE_DELETED",
                                            key="SERVICE_DELETED",
                                            data=new_event_data)
                    self._sc.post_event(ev)
