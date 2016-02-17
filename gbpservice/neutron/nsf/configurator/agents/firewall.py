# One Convergence, Inc. CONFIDENTIAL
# Copyright (c) 2012-2016, One Convergence, Inc., USA
# All Rights Reserved.
#
# All information contained herein is, and remains the property of
# One Convergence, Inc. and its suppliers, if any. The intellectual and
# technical concepts contained herein are proprietary to One Convergence,
# Inc. and its suppliers.
#
# Dissemination of this information or reproduction of this material is
# strictly forbidden unless prior written permission is obtained from
# One Convergence, Inc., USA

import os

from oslo_config import cfg
from oslo_log import log as logging
import oslo_messaging as messaging
from requests import ConnectionError

from gbpservice.neutron.nsf.configurator.lib import fw_constants as const
from gbpservice.neutron.nsf.core.main import Event
from gbpservice.neutron.nsf.core.queue import Queue
''' TO DO[DEE]: Avoid the following imports. Do dynamic driver imports
'''
from gbpservice.neutron.nsf.configurator.drivers.firewall.\
                            vyos.vyos_fw_driver import FwaasDriver

LOG = logging.getLogger(__name__)

rest_timeout = [
    cfg.IntOpt(
        'rest_timeout',
        default=30,
        help=_("rest api timeout"))]
cfg.CONF.register_opts(rest_timeout)

OPTS = [
    cfg.IntOpt('oc_periodic_interval', default=10, help='Define periodic '
                                                        'interval for tasks'),
    cfg.IntOpt('oc_report_interval', default=10,
               help='Reporting interval from agent to firewall plugin')
]
GROUP_OPTS = cfg.OptGroup(name='ocfwaas', title='OC FW OPTIONS')
cfg.CONF.register_group(GROUP_OPTS)
cfg.CONF.register_opts(OPTS, group=GROUP_OPTS)


class FwaasRpcSender(object):
    """ APIs to FWaaS Plugin.
    """

    def __init__(self, sc, host):
        self.sc = sc
        self.host = host
        self.qu = Queue(sc)

    def set_firewall_status(self, context, firewall_id, status):
        """Make an RPC to set the status of a firewall."""

        msg = {'resource': 'firewall',
               'method': 'set_firewall_status',
               'data': {'context': context,
                        'host': self.host,
                        'firewall_id': firewall_id,
                        'status': status}
               }
        self.qu.put(msg)

    def firewall_deleted(self, context, firewall_id):
        """Make an RPC to indicate that the firewall resources are deleted."""

        msg = {'resource': 'firewall',
               'method': 'firewall_deleted',
               'data': {'context': context,
                        'host': self.host,
                        'firewall_id': firewall_id}
               }
        self.qu.put(msg)


class FWaasRpcManager(object):
    """
    APIs for receiving RPC messages from Firewall plugin.
    """
    RPC_API_VERSION = '1.0'
    target = messaging.Target(version=RPC_API_VERSION)

    def __init__(self, conf, sc):
        self.conf = conf
        self._sc = sc

    def create_firewall(self, **kwargs):
        LOG.debug("FwaasRpcReceiver received Create Firewall request.")
        ev = self._sc.event(id='CREATE_FIREWALL', data=kwargs)
        self._sc.rpc_event(ev)

    def update_firewall(self, **kwargs):
        LOG.debug("FwaasRpcReceiver received Update Firewall request.")
        ev = self._sc.event(id='UPDATE_FIREWALL', data=kwargs)
        self._sc.rpc_event(ev)

    def delete_firewall(self, **kwargs):
        LOG.debug("FwaasRpcReceiver received Delete Firewall request.")
        ev = self._sc.event(id='DELETE_FIREWALL', data=kwargs)
        self._sc.rpc_event(ev)

class FWaasEventHandler(object):
    """
    Handler class for demultiplexing firewall configuration
    requests from Fwaas Plugin and sending to appropriate driver.
    """

    def __init__(self, sc, drivers):
        self._sc = sc
        self.drivers = drivers
        self.host = cfg.CONF.host
        self.plugin_rpc = FwaasRpcSender(
            sc, self.host)

    def _get_driver(self, data):
        ''' TO DO[DEE]: Do demultiplexing logic based on vendor
                        when a new vendor comes.
        '''
        return self.drivers['vyos_fwaas']

    def _is_firewall_rule_exists(self, fw):
        if not fw['firewall_rule_list']:
            return False
        else:
            return True

    def handle_event(self, ev):
        try:
            msg = ("Worker process with ID: %s starting "
                   "to handle task: %s of type firewall. "
                   % (os.getpid(), ev.id))
            LOG.debug(msg)

            driver = self._get_driver(ev.data)
            self.method = getattr(driver, "%s" % (ev.id.lower()))
            self.invoke_driver_for_plugin_api(ev)
        except Exception as err:
            LOG.error("Failed to perform the operation: %s. %s"
                      % (ev.id, str(err).capitalize()))

    def invoke_driver_for_plugin_api(self, ev):
        kwargs = ev.data.get('kwargs')
        context = kwargs.get('context')
        firewall = kwargs.get('firewall')
        agent_mode = None
        apply_list = None

        if ev.id == 'CREATE_FIREWALL':
            if not self._is_firewall_rule_exists(firewall):
                msg = ("Firewall status set to ACTIVE")
                LOG.debug(msg)
                return self.plugin_rpc.set_firewall_status(
                    context, firewall['id'], const.STATUS_ACTIVE)
            # Added to handle in service vm agents. VM agent will add
            # default DROP rule.
            # if not self._is_firewall_rule_exists(firewall):
            #     self.plugin_rpc.set_firewall_status(
            #         context, firewall['id'], const.STATUS_ACTIVE)
            try:
                status = self.method(agent_mode, apply_list, firewall)
            except Exception as err:
                self.plugin_rpc.set_firewall_status(
                    context, firewall['id'], const.STATUS_ERROR)
                msg = ("Failed to configure Firewall and status is "
                       "changed to ERROR. %s." % str(err).capitalize())
                LOG.error(msg)
            else:
                self.plugin_rpc.set_firewall_status(
                    context, firewall['id'], status)
                msg = ("Configured Firewall and status set to %s" % status)
                LOG.info(msg)

        elif ev.id == 'DELETE_FIREWALL':
            if not self._is_firewall_rule_exists(firewall):
                return self.plugin_rpc.firewall_deleted(context,
                                                        firewall['id'])
            try:
                status = self.method(agent_mode, apply_list, firewall)
            except ConnectionError:
                # FIXME(Vikash) It can't be correct everytime
                LOG.warning("There is a connection error for firewall %r of "
                            "tenant %r. Assuming either there is serious "
                            "issue with VM or data path is completely "
                            "broken. For now marking that as delete."
                            % (firewall['id'], firewall['tenant_id']))
                self.plugin_rpc.firewall_deleted(context, firewall['id'])

            except Exception as err:
                # TODO(Vikash) Is it correct to raise ? As the subsequent
                # attempt to clean will only re-raise the last one.And it
                # can go on and on and may not be ever recovered.
                self.plugin_rpc.set_firewall_status(
                    context, firewall['id'], const.STATUS_ERROR)
                msg = ("Failed to delete Firewall and status is "
                       "changed to ERROR. %s." % str(err).capitalize())
                LOG.error(msg)
                # raise(err)
            else:
                if status == const.STATUS_ERROR:
                    self.plugin_rpc.set_firewall_status(
                        context, firewall['id'], status)
                else:
                    LOG.info("Firewall %r deleted of tenant: %r" % (
                            firewall['id'], firewall['tenant_id']))
                    self.plugin_rpc.firewall_deleted(
                                        context, firewall['id'])

        elif ev.id == 'UPDATE_FIREWALL':
            if not self._is_firewall_rule_exists(firewall):
                return self.plugin_rpc.set_firewall_status(
                    context, firewall['id'], const.STATUS_ACTIVE)
            try:
                status = self.method(agent_mode, apply_list, firewall)
            except Exception as err:
                self.plugin_rpc.set_firewall_status(
                            context, firewall['id'], 'ERROR')
                msg = ("Failed to update Firewall and status is "
                       "changed to ERROR. %s." % str(err).capitalize())
                LOG.error(msg)
            else:
                self.plugin_rpc.set_firewall_status(
                                context, firewall['id'], status)
                msg = ("Updated Firewall and status set to %s" % status)
                LOG.info(msg)
        else:
            raise Exception("Wrong call to Fwaas event handler.")


def events_init(sc, drivers):
    evs = [
        Event(id='CREATE_FIREWALL', handler=FWaasEventHandler(sc, drivers)),
        Event(id='UPDATE_FIREWALL', handler=FWaasEventHandler(sc, drivers)),
        Event(id='DELETE_FIREWALL', handler=FWaasEventHandler(sc, drivers))]
    sc.register_events(evs)


def load_drivers():
    ''' Create objects of firewall drivers.

        TODO: We need to make load_drivers() work by dynamic class detection
        from the driver directory and instantiate objects out of it.
    '''
    drivers = {"vyos_fwaas": FwaasDriver()}
    return drivers


def register_service_agent(cm, sc, conf):
    service_type = 'firewall'
    rpc_mgr = FWaasRpcManager(sc, conf)
    cm.register_service_agent(service_type, rpc_mgr)


def init_agent(cm, sc, conf):
    drivers = load_drivers()
    events_init(sc, drivers)
    register_service_agent(cm, sc, conf)


def init_agent_complete(sa, sc, conf):
    LOG.info(" firewall agent init complete")
