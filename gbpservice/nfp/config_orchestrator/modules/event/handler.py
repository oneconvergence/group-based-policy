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
import sys
import time
import traceback

from gbpservice.nfp.config_orchestrator.common import common
from gbpservice.nfp.core.event import Event
from gbpservice.nfp.core import log as nfp_logging
from gbpservice.nfp.core import module as nfp_api
from gbpservice.nfp.lib import transport

from neutron import context as n_context
from neutron_fwaas.db.firewall import firewall_db
from neutron_lbaas.db.loadbalancer import loadbalancer_db
from neutron_vpnaas.db.vpn import vpn_db


LOG = nfp_logging.getLogger(__name__)

STOP_POLLING = {'poll': False}
CONTINUE_POLLING = {'poll': True}


def event_init(sc, conf):
    evs = [
        Event(id='OTC_EVENT',
              handler=EventsHandler(sc, conf)),
        Event(id='SET_FIREWALL_STATUS',
              handler=EventsHandler(sc, conf)),
        Event(id='FIREWALL_DELETED',
              handler=EventsHandler(sc, conf)),
        Event(id='VIP_DELETED',
              handler=EventsHandler(sc, conf)),
        Event(id='UPDATE_STATUS',
              handler=EventsHandler(sc, conf)),
        Event(id='IPSEC_SITE_CONN_DELETED',
              handler=EventsHandler(sc, conf)),
        Event(id='SERVICE_OPERATION_POLL_EVENT',
              handler=EventsHandler(sc, conf)),
        Event(id='SERVICE_CREATED',
              handler=EventsHandler(sc, conf)),
        Event(id='SERVICE_DELETED',
              handler=EventsHandler(sc, conf)),
        Event(id='SERVICE_CREATE_PENDING',
              handler=EventsHandler(sc, conf))]

    sc.register_events(evs)


def nfp_module_init(sc, conf):
    event_init(sc, conf)


def nfp_module_post_init(sc, conf):
    try:
        ev = sc.new_event(id='SERVICE_OPERATION_POLL_EVENT',
                          key='SERVICE_OPERATION_POLL_EVENT')
        sc.post_event(ev)
    except Exception as e:
        msg = ("%s" % (e))
        LOG.error(msg)


"""Periodic Class to service events for visiblity."""


class EventsHandler(nfp_api.NfpEventHandler):

    def __init__(self, sc, conf):
        self._sc = sc
        self._conf = conf

    class PullDbEntry(firewall_db.Firewall_db_mixin,
                      loadbalancer_db.LoadBalancerPluginDb,
                      vpn_db.VPNPluginDb,
                      vpn_db.VPNPluginRpcDbMixin
                      ):

        def __init__(self):
            super(EventsHandler.PullDbEntry, self).__init__()

        def get_firewalls(self, context):
            db_data = super(EventsHandler.PullDbEntry, self)
            return db_data.get_firewalls(context)

        def get_vips(self, context):
            db_data = super(EventsHandler.PullDbEntry, self)
            return db_data.get_vips(context)

        def get_ipsec_site_connections(self, context):
            db_data = super(EventsHandler.PullDbEntry, self)
            return db_data.get_ipsec_site_connections(context)

    def handle_event(self, ev):
        if ev.id == 'OTC_EVENT':
            self._handle_otc_event(ev.data)
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
        elif ev.id == 'SERVICE_OPERATION_POLL_EVENT':
            self._sc.poll_event(ev)

    def event_cancelled(self, event, reason):
        msg = ("Poll Event =%s got time out Event Data = %s " %
               (event.id, event.data))
        LOG.info(msg)

    def _get_all_data(self, data):
        notification_data = data['notification_data']
        notification = notification_data['notification'][0]
        notification_info = notification_data['info']
        resource_data = notification['data']
        resource = notification['resource']
        context = data['context']
        return context, notification_info, resource_data, resource

    def _handle_set_firewall_status(self, data):
        context, notification_info, resource_data, _ = self.\
            _get_all_data(data)
        firewall_id = resource_data['firewall_id']
        nf_id = notification_info['context'][
            'network_function_id']
        fw_mac = notification_info['context']['fw_mac']
        service_type = notification_info['service_type']
        # Sending An Event for visiblity #
        request_data = {'nf_id': nf_id,
                        'fw_mac': fw_mac,
                        'service_type': service_type,
                        'neutron_resource_id': firewall_id,
                        'context': context,
                        'LogMetaID': nf_id,
                        'eventid': 'SERVICE_CREATE_PENDING'
                        }
        msg = ("Stashing Event for data : %s" % (request_data))
        LOG.info(msg)
        event = self._sc.new_event(
            id='STASH_EVENT', key='STASH_EVENT', data=request_data)
        self._sc.stash_event(event)

    def _handle_firewall_deleted(self, data):
        context, notification_info, resource_data, _ = self.\
            _get_all_data(data)
        firewall_id = resource_data['firewall_id']
        nf_id = notification_info['context'][
            'network_function_id']
        fw_mac = notification_info['context']['fw_mac']
        service_type = notification_info['service_type']

        # Sending An Event for visiblity #
        request_data = {'nf_id': nf_id,
                        'fw_mac': fw_mac,
                        'service_type': service_type,
                        'context': context,
                        'LogMetaID': nf_id,
                        'neutron_resource_id': firewall_id,
                        'eventid': 'SERVICE_DELETED'
                        }
        msg = ("Stashing Event for data : %s" % (request_data))
        LOG.info(msg)
        event = self._sc.new_event(
            id='STASH_EVENT', key='STASH_EVENT', data=request_data)
        self._sc.stash_event(event)

    def _handle_vip_deleted(self, data):
        context, notification_info, resource_data, _ = self.\
            _get_all_data(data)
        nf_id = notification_info['context'][
            'network_function_id']
        vip_id = notification_info['context']['vip_id']
        service_type = notification_info['service_type']

        # Sending An Event for visiblity
        request_data = {'context': context,
                        'nf_id': nf_id,
                        'vip_id': vip_id,
                        'service_type': service_type,
                        'LogMetaID': nf_id,
                        'neutron_resource_id': vip_id,
                        'eventid': 'SERVICE_DELETED'
                        }
        msg = ("Stashing Event for data : %s" % (request_data))
        LOG.info(msg)
        event = self._sc.new_event(
            id='STASH_EVENT', key='STASH_EVENT', data=request_data)
        self._sc.stash_event(event)

    def _handler_vpn_update_status(self, context, notification_info,
                                   resource_data, resource):
        # Sending An Event for visiblity
        if resource.lower() ==\
                'ipsec_site_connection':
            nf_id = notification_info['context'][
                'network_function_id']
            ipsec_id = notification_info['context'][
                'ipsec_site_connection_id']
            service_type = notification_info['service_type']

            # Sending An Event for visiblity
            request_data = {'context': context,
                            'nf_id': nf_id,
                            'ipsec_site_connection_id': ipsec_id,
                            'service_type': service_type,
                            'neutron_resource_id': ipsec_id,
                            'LogMetaID': nf_id,
                            'eventid': 'SERVICE_CREATE_PENDING'
                            }
            msg = ("Stashing Event for data : %s" % (request_data))
            LOG.info(msg)
            event = self._sc.new_event(
                id='STASH_EVENT', key='STASH_EVENT', data=request_data)
            self._sc.stash_event(event)

    def _handler_loadbalancer_update_status(self, context,
                                            notification_info, resource_data):
        obj_type = resource_data['obj_type']
        if obj_type.lower() == 'vip':
            nf_id = notification_info['context'][
                'network_function_id']
            vip_id = notification_info['context']['vip_id']
            service_type = notification_info['service_type']
            # sending notification to otc
            request_data = {'context': context,
                            'nf_id': nf_id,
                            'vip_id': vip_id,
                            'service_type': service_type,
                            'neutron_resource_id': vip_id,
                            'LogMetaID': nf_id,
                            'eventid': 'SERVICE_CREATE_PENDING'
                            }
            msg = ("Stashing Event for data : %s" % (request_data))
            LOG.info(msg)
            event = self._sc.new_event(
                id='STASH_EVENT', key='STASH_EVENT', data=request_data)
            self._sc.stash_event(event)

    def _handle_update_status(self, data):
        context, notification_info, resource_data, resource = self.\
            _get_all_data(data)
        service_type = notification_info['service_type']
        if service_type.lower() == "loadbalancer":
            self._handler_loadbalancer_update_status(context,
                                                     notification_info,
                                                     resource_data)

        elif service_type.lower() == "vpn":
            self._handler_vpn_update_status(context,
                                            notification_info,
                                            resource_data,
                                            resource)

    def _handle_ipsec_site_conn_deleted(self, data):
        context, notification_info, resource_data, _ = self.\
            _get_all_data(data)
        resource_id = resource_data['resource_id']
        # Sending An Event for visiblity
        nf_id = notification_info[
            'context']['network_function_id']
        ipsec_id = notification_info['context']['ipsec_site_connection_id']
        service_type = notification_info['service_type']

        # Sending An Event for visiblity
        request_data = {'context': context,
                        'nf_id': nf_id,
                        'ipsec_site_connection_id': ipsec_id,
                        'service_type': service_type,
                        'neutron_resource_id': resource_id,
                        'LogMetaID': nf_id,
                        'eventid': 'SERVICE_DELETED'
                        }
        msg = ("Stashing Event for data : %s" % (request_data))
        LOG.info(msg)
        event = self._sc.new_event(
            id='STASH_EVENT', key='STASH_EVENT', data=request_data)
        self._sc.stash_event(event)

    def _handle_create_service(self, data):
        context = data['context']
        resource = data['resource']
        ctxt = n_context.Context.from_dict(context)
        transport.send_request_to_configurator(self._conf,
                                               ctxt, resource,
                                               "CREATE",
                                               network_function_event=True)

    def _handle_delete_service(self, data):
        context = data['context']
        resource = data['resource']
        ctxt = n_context.Context.from_dict(context)
        transport.send_request_to_configurator(self._conf,
                                               ctxt, resource,
                                               "DELETE",
                                               network_function_event=True)

    def _get_firewall_bulk_data(self, context, firewalls):
        fw_request_data_list = []
        for firewall in firewalls:
            try:
                firewall_desc = ast.literal_eval(firewall['description'])
                nf_id = firewall_desc['network_function_id']
                nf = common.get_network_function_details(context, nf_id)
                description = ast.literal_eval(
                    (nf['description'].split('\n'))[1])
                fw_mac = description['provider_ptg_info'][0]
                service_type = 'firewall'
                request_data = {'nf_id': nf_id,
                                'fw_mac': fw_mac,
                                'service_type': service_type,
                                'neutron_resource_id': firewall['id'],
                                'context': context.to_dict(),
                                'LogMetaID': nf_id,
                                'eventid': 'SERVICE_CREATE_PENDING'
                                }
                fw_request_data_list.append(request_data)
            except Exception as e:
                msg = ("firewall desc : %s " % (e))
                LOG.error(msg)
        return fw_request_data_list

    def _get_vip_bulk_data(self, context, vips):
        vip_request_data_list = []
        for vip in vips:
            try:
                vip_desc = ast.literal_eval(vip['description'])
                nf_id = vip_desc['network_function_id']
                vip_id = vip['id']
                service_type = 'loadbalancer'
                request_data = {'nf_id': nf_id,
                                'vip_id': vip_id,
                                'service_type': service_type,
                                'neutron_resource_id': vip_id,
                                'context': context.to_dict(),
                                'LogMetaID': nf_id,
                                'eventid': 'SERVICE_CREATE_PENDING'
                                }
                vip_request_data_list.append(request_data)
            except Exception as e:
                msg = ("vip desc : %s " % (e))
                LOG.error(msg)
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
                ipsec_desc = ast.literal_eval(ipsec_site_connection[
                    'description'])
                nf_id = ipsec_desc['network_function_id']
                ipsec_id = ipsec_site_connection['id']
                service_type = 'vpn'
                request_data = {'context': context.to_dict(),
                                'nf_id': nf_id,
                                'ipsec_site_connection_id': ipsec_id,
                                'service_type': service_type,
                                'neutron_resource_id': (
                                    ipsec_site_connection['id']),
                                'LogMetaID': nf_id,
                                'eventid': 'SERVICE_CREATE_PENDING'
                                }
                ipsec_request_data_list.append(request_data)
            except Exception as e:
                msg = ("ipsec desc : %s " % e)
                LOG.error(msg)
        return ipsec_request_data_list

    def _handle_otc_event(self, data):
        try:
            # context = data['context']
            context = n_context.get_admin_context()
            pull_db = self.PullDbEntry()
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
            if bulk_response_data == []:
                msg = ("No Event to Stash")
                LOG.info(msg)

            for response_data in bulk_response_data:
                msg = ("Stashing Event for data : %s" % (response_data))
                LOG.info(msg)
                event = self._sc.new_event(
                    id='STASH_EVENT', key='STASH_EVENT', data=response_data)
                self._sc.stash_event(event)

        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()

            msg = ("get_bulk_network_function_context failed : Reason %s  %s"
                   % (e, traceback.format_exception(exc_type,
                                                    exc_value,
                                                    exc_traceback)))
            LOG.error(msg)

    def _prepare_request_data(self, event_data):
        request_data = None
        try:
            nf_id = event_data.pop('nf_id')
            context = event_data.pop('context')
            ctxt = n_context.Context.from_dict(context)
            request_data = common.get_network_function_map(
                ctxt, nf_id)
            event_data.update(request_data)
        except Exception:
            return event_data
        return event_data, context

    def _trigger_service_event(self, context, event_data, event_type):
        new_event_data = {'resource': None,
                          'context': context}
        nfp_log_ctx = nfp_logging.get_logging_context()
        new_event_data['resource'] = {'eventtype': 'SERVICE',
                                      'eventid': event_type,
                                      'eventdata': event_data,
                                      'info': {'context':
                                               {'logging_context':
                                                nfp_log_ctx}}}

        new_ev = self._sc.new_event(id=event_type,
                                    key=event_type,
                                    data=new_event_data)
        self._sc.post_event(new_ev)

    @nfp_api.poll_event_desc(event='SERVICE_CREATE_PENDING', spacing=5)
    def create_sevice_pending_event(self, ev):
        event_data = copy.deepcopy(ev.data)
        try:
            updated_event_data, context = self._prepare_request_data(
                event_data)
            msg = ('%s' % (updated_event_data))
            LOG.info(msg)
            if updated_event_data['nf']['status'] == 'ACTIVE':
                self._trigger_service_event(
                    context, updated_event_data, 'SERVICE_CREATED')
                return STOP_POLLING

            return CONTINUE_POLLING
        except Exception as e:
            msg = ('Failed : %s Reason : %s' % (event_data, e))
            LOG.error(msg)
            return STOP_POLLING

    @nfp_api.poll_event_desc(event='SERVICE_OPERATION_POLL_EVENT', spacing=5)
    def service_operation_poll_stash_event(self, ev):
        events = self._sc.get_stashed_events()
        msg = ("Stash Queue is: %s" % (events))
        LOG.debug(msg)
        for event in events:
            data = copy.deepcopy(event.data)
            eventid = data.pop('eventid')
            if eventid == "SERVICE_CREATE_PENDING":
                new_event = self._sc.new_event(id=eventid,
                                               key=eventid,
                                               data=data, max_times=24)
                self._sc.poll_event(new_event)

            elif eventid == "SERVICE_DELETED":
                try:
                    updated_event_data, context = self._prepare_request_data(
                        data)
                    msg = ('%s' % (updated_event_data))
                    LOG.info(msg)
                    self._trigger_service_event(
                        context, updated_event_data, eventid)
                except Exception as e:
                    msg = ('Failed : %s Reason : %s' % (data, e))
                    LOG.error(msg)
            time.sleep(0)
