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
import copy
import time

from gbpservice.nfp.core import common as nfp_common
from gbpservice.nfp.core import poll as core_pt
from gbpservice.nfp.lib import transport
from gbpservice.nfp.config_orchestrator.common import common

from neutron_fwaas.db.firewall import firewall_db
from neutron_lbaas.db.loadbalancer import loadbalancer_db
from neutron_vpnaas.db.vpn import vpn_db

from oslo_log import log as oslo_logging


LOGGER = oslo_logging.getLogger(__name__)
LOG = nfp_common.log

"""Periodic Class to service events for visiblity."""


class VisibilityEventsHandler(core_pt.PollEventDesc):

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

    def handle_event(self, ev):
        if ev.id == 'VISIBILITY_EVENT':
            self._handle_visibility_event(ev.data)
        elif ev.id == 'SET_FIREWALL_STATUS':
            self._handle_set_firewall_status(ev.data)
        elif ev.id == 'FIREWALL_DELETED':
            self._handle_firewall_deleted(ev.data)
        elif ev.id == 'VIP_DELETED':
            self._handle_vip_deleted(ev.data)
        elif ev.id == 'UPDATE_STATUS':
            self._handle_update_status(ev.data)
        elif ev.id == 'IPSEC_SITE_CONN_DELETED':
            self._handle_ipsec_site_conn_deleted(ev.data)
        elif ev.id == 'SERVICE_CREATED':
            self._handle_create_service(ev.data)
        elif ev.id == 'SERVICE_DELETED':
            self._handle_delete_service(ev.data)
        elif ev.id == 'PULL_BULK_DATA':
            self._handle_pull_bulk_data(ev.data)
        elif ev.id == 'SERVICE_OPERATION_POLL_EVENT':
            self._sc.poll_event(ev)

    def _get_all_data(self, data):
        notification_data = data['notification_data']
        notification = notification_data['notification'][0]
        notification_info = notification_data['info']
        resource_data = notification['data']
        context = data['context']
        return context, notification_info, resource_data

    def _handle_set_firewall_status(self, data):
        context, notification_info, resource_data = self.\
            _get_all_data(data)
        firewall_id = resource_data['firewall_id']
        nf_instance_id = notification_info['context'][
            'network_function_instance_id']
        fw_mac = notification_info['context']['fw_mac']
        service_type = notification_info['service_type']
        # Sending An Event for visiblity #
        request_data = {'nf_instance_id': nf_instance_id,
                        'fw_mac': fw_mac,
                        'service_type': service_type,
                        'neutron_resource_id': firewall_id,
                        'context': context,
                        'eventid': 'SERVICE_CREATE_PENDING'
                        }
        event = self._sc.new_event(
            id='STASH_EVENT', key='STASH_EVENT', data=request_data)
        self._sc.stash_event(event)

    def _handle_firewall_deleted(self, data):
        context, notification_info, resource_data = self.\
            _get_all_data(data)
        firewall_id = resource_data['firewall_id']
        nf_instance_id = notification_info['context'][
            'network_function_instance_id']
        fw_mac = notification_info['context']['fw_mac']
        service_type = notification_info['service_type']

        # Sending An Event for visiblity #
        request_data = {'nf_instance_id': nf_instance_id,
                        'fw_mac': fw_mac,
                        'service_type': service_type,
                        'context': context,
                        'neutron_resource_id': firewall_id,
                        'eventid': 'SERVICE_DELETED'
                        }
        event = self._sc.new_event(
            id='STASH_EVENT', key='STASH_EVENT', data=request_data)
        self._sc.stash_event(event)

    def _handle_vip_deleted(self, data):
        context, notification_info, resource_data = self.\
            _get_all_data(data)
        nf_instance_id = notification_info['context'][
            'network_function_instance_id']
        vip_id = notification_info['context']['vip_id']
        service_type = notification_info['service_type']

        # Sending An Event for visiblity
        request_data = {'context': context,
                        'nf_instance_id': nf_instance_id,
                        'vip_id': vip_id,
                        'service_type': service_type,
                        'neutron_resource_id': vip_id,
                        'eventid': 'SERVICE_DELETED'
                        }
        event = self._sc.new_event(
            id='STASH_EVENT', key='STASH_EVENT', data=request_data)
        self._sc.stash_event(event)

    def _handler_vpn_update_status(context, notification_info,
                                   resource_data):
        # Sending An Event for visiblity
        if notification['resource'].lower() is\
                'ipsec_site_connection':
            nf_instance_id = notification_info['context'][
                'network_function_instance_id']
            ipsec_id = notification_info['context'][
                'ipsec_site_connection_id']
            service_type = notification_info['service_type']

            # Sending An Event for visiblity
            request_data = {'context': context,
                            'nf_instance_id': nf_instance_id,
                            'ipsec_site_connection_id': ipsec_id,
                            'service_type': service_type,
                            'neutron_resource_id': ipsec_id,
                            'eventid': 'SERVICE_CREATE_PENDING'
                            }
            event = self._sc.new_event(
                id='STASH_EVENT', key='STASH_EVENT', data=request_data)
            self._sc.stash_event(event)

    def _handler_loadbalancer_update_status(self, context,
                                            notification_info, resource_data):
        obj_type = resource_data['obj_type']
        if obj_type.lower() == 'vip':
            nf_instance_id = notification_info['context'][
                'network_function_instance_id']
            vip_id = notification_info['context']['vip_id']
            service_type = notification_info['service_type']
            # sending notification to visibility
            request_data = {'context': context,
                            'nf_instance_id': nf_instance_id,
                            'vip_id': vip_id,
                            'service_type': service_type,
                            'neutron_resource_id': vip_id,
                            'eventid': 'SERVICE_CREATE_PENDING'
                            }
            event = self._sc.new_event(
                id='STASH_EVENT', key='STASH_EVENT', data=request_data)
            self._sc.stash_event(event)

    def _handle_update_status(self, data):
        context, notification_info, resource_data = self.\
            _get_all_data(data)
        service_type = notification_info['service_type']
        if service_type.lower() == "loadbalancer":
            self._handler_loadbalancer_update_status(context,
                                                     notification_info,
                                                     resource_data)

        elif service_type.lower() == "vpn":
            self._handler_vpn_update_status(context,
                                            notification_info,
                                            resource_data)

    def _handle_ipsec_site_conn_deleted(self, data):
        context, notification_info, resource_data = self.\
            _get_all_data(data)
        resource_id = resource_data['resource_id']
        # Sending An Event for visiblity
        nf_instance_id = notification_info[
            'context']['network_function_instance_id']
        ipsec_id = notification_info['context']['ipsec_site_connection_id']
        service_type = notification_info['service_type']

        # Sending An Event for visiblity
        request_data = {'context': context,
                        'nf_instance_id': nf_instance_id,
                        'ipsec_site_connection_id': ipsec_id,
                        'service_type': service_type,
                        'neutron_resource_id': ipsec_id,
                        'eventid': 'SERVICE_DELETED'
                        }
        event = self._sc.new_event(
            id='STASH_EVENT', key='STASH_EVENT', data=request_data)
        self._sc.stash_event(event)

    def _handle_create_service(self, data):
        context = data['context']
        resource = data['resource']
        transport.send_request_to_configurator(self._conf,
                                               context, resource,
                                               "CREATE",
                                               network_function_event=True)

    def _handle_delete_service(self, data):
        context = data['context']
        resource = data['resource']
        transport.send_request_to_configurator(self._conf,
                                               context, resource,
                                               "DELETE",
                                               network_function_event=True)

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
                                'eventid': 'SERVICE_CREATE_PENDING'
                                }
                fw_request_data_list.append(request_data)
            except Exception as e:
                LOG(LOGGER, 'ERROR', "firewall desc : %s " % e)
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
                                'eventid': 'SERVICE_CREATE_PENDING'
                                }
                vip_request_data_list.append(request_data)
            except Exception as e:
                LOG(LOGGER, 'ERROR', "vip desc : %s " % e)
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
                                'eventid': 'SERVICE_CREATE_PENDING'
                                }
                ipsec_request_data_list.append(request_data)
            except Exception as e:
                LOG(LOGGER, 'ERROR', "ipsec desc : %s " % e)

    def _handle_visibility_event(self, data):
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
                event = self._sc.new_event(
                    id='STASH_EVENT', key='STASH_EVENT', data=response_data)
                self._sc.stash_event(event)

        except Exception as e:
            LOG(LOGGER, 'ERROR',
                "get_bulk_network_function_context failed : Reason %s " % (
                    e))

    def _prepare_request_data(self, event_data):
        request_data = None
        try:
            nf_instance_id = event_data.pop('nf_instance_id')
            context = event_data.pop('context')
            request_data = common.get_network_function_map(
                context, nf_instance_id)
            event_data.update(request_data)
        except Exception as e:
            return event_data
        return event_data, context

    def _trigger_service_event(self, context, event_data, event_type):
        new_event_data = {'resource': None,
                          'context': context}
        new_event_data['resource'] = {'eventtype': 'SERVICE',
                                      'eventid': event_type,
                                      'eventdata': event_data}

        new_ev = self._sc.new_event(id=event_type,
                                    key=event_type,
                                    data=new_event_data)
        self._sc.post_event(new_ev)

    @core_pt.poll_event_desc(event='SERVICE_CREATE_PENDING', spacing=5)
    def create_sevice_pending_event(self, ev):
        event_data = copy.deepcopy(ev.data)
        try:
            updated_event_data, context = self._prepare_request_data(
                event_data)
            LOG(LOGGER, 'INFO', '%s' % (updated_event_data))
            if updated_event_data['nf']['status'] == 'ACTIVE':
                self._trigger_service_event(
                    context, updated_event_data, 'SERVICE_CREATED')
                self._sc.poll_event_done(ev)
        except Exception as e:
            LOG(LOGGER, 'ERROR', 'Failed : %s Reason : %s' % (event_data, e))

    @core_pt.poll_event_desc(event='SERVICE_OPERATION_POLL_EVENT', spacing=5)
    def service_operation_poll_stash_event(self, ev):
        events = self._sc.get_stashed_events()
        LOG(LOGGER, 'ERROR', "Stash Queue is: %s" % events)
        for event in events:
            data = copy.deepcopy(event.data)
            eventid = data.pop('eventid')
            if eventid == "SERVICE_CREATE_PENDING":
                new_event = self._sc.new_event(id=eventid,
                                               key=eventid,
                                               data=data)
                self._sc.poll_event(new_event)

            elif eventid == "SERVICE_DELETED":
                try:
                    updated_event_data, context = self._prepare_request_data(
                        data)
                    LOG(LOGGER, 'INFO', '%s' % (updated_event_data))
                    self._trigger_service_event(
                        context, updated_event_data, eventid)
                except Exception as e:
                    LOG(LOGGER, 'ERROR', 'Failed : %s Reason : %s' % (data, e))
            time.sleep(0)
