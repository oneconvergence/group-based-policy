# One Convergence, Inc. CONFIDENTIAL
# Copyright (c) 2012-2015, One Convergence, Inc., USA
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

import eventlet
import time

from neutron.common import rpc as n_rpc
from neutron.openstack.common import log as logging

eventlet.monkey_patch()

LOG = logging.getLogger(__name__)
SERVICE_MANAGER_RPC_TOPIC = "topics_ocmanager_agent"


class SvcManagerClientApi(n_rpc.RpcProxy):
    """ Client side of service manager """

    API_VERSION = '2.0'

    def __init__(self, host):
        super(SvcManagerClientApi, self).__init__(SERVICE_MANAGER_RPC_TOPIC,
                                                  self.API_VERSION)
        self.host = host

    def get_svc_mgmt_ip(self, context, tenant_id, service_type):
        return self.call(context,
                         self.make_msg('get_service_instance_mgmt_ip',
                                       tenant_id=tenant_id,
                                       service_type=service_type))

    def create_service_instance(self, context, **kwargs):
        svc_status = None
        self.cast(context, self.make_msg('create_service_instance', **kwargs),
                  topic='%s' % (self.topic),
                  version=self.API_VERSION)
        start = end = int(time.time())
        interval = 10
        while end - start <= 900:
            # Wait for 300 seconds for service VM to be launched and health
            # check on VM agent port to succeed
            eventlet.sleep(interval)
            svc_status = self.call(
                context, self.make_msg(
                    'get_service_instance_status',
                    tenant_id=kwargs['tenant_id'],
                    service_chain_instance_id=kwargs[
                        'service_chain_instance_id'],
                    service_type=kwargs['service_type']))

            end = int(time.time())

            if svc_status == 'ACTIVE':
                LOG.debug(_("Service %s became ACTIVE"), kwargs[
                    'service_type'])
                return svc_status
            elif svc_status == 'ERROR':
                # REVISIT(Magesh): Not sure if we have to log error here.
                # The caller may also be logging the same error from the
                # exception we are raising
                err_msg = "Service %s went to ERROR state" % kwargs[
                    'service_type']
                LOG.error(_(err_msg))
                raise Exception(err_msg)
            elif not svc_status:
                err_msg = ("%s Service information not added to DB by Service "
                           "Manager. Retrying .." % kwargs['service_type'])
                LOG.warn(_(err_msg))
                # Sleep time here is exponentially increased for a total of 150
                # seconds in case the VM launch did not happen by this time
                if interval < 120:
                    interval += interval
                else:
                    err_msg = (" %s Service not found in DB, thus exiting"
                               % kwargs['service_type'])
                    raise Exception(_(err_msg))

        err_msg = "Service VM bringup did not complete in 5 minutes"
        LOG.error(_(err_msg))
        raise Exception(err_msg)

    def delete_service_instance(self, context, **kwargs):
        return self.call(context,
                         self.make_msg('delete_service_instance', **kwargs))

    def get_service_info_with_srvc_type(self, context, **kwargs):
        return self.call(
            context, self.make_msg('get_service_info_with_srvc_type',
                                   **kwargs))

    def get_existing_service_for_sharing(self, context, **kwargs):
        return self.call(
            context, self.make_msg('get_existing_service_for_sharing',
                                   **kwargs))

    def get_service_instance_satus(self, context, **kwargs):
        svc_db = self.call(
            context, self.make_msg(
                'get_service_instance_status',
                tenant_id=kwargs['tenant_id'],
                service_chain_instance_id=kwargs['service_chain_instance_id'],
                service_type=kwargs['service_type']))
        return svc_db

    def get_service_floating_ip(self, context, tenant_id, service_type):
        fip = self.call(context,
                        self.make_msg('get_service_floating_ip',
                                      tenant_id=tenant_id,
                                      service_type=service_type))
        return fip

    def get_service_ports(self, context, tenant_id, service_type):
        ports_list = self.call(context,
                               self.make_msg('get_service_ports',
                                             tenant_id=tenant_id,
                                             service_type=service_type))
        return ports_list
