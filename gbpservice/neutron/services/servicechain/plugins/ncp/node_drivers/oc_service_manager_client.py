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

    def create_service(self, context, service_info):
        self.cast(context,
                  self.make_msg('create_service', service_info=service_info),
                  topic='%s' % (self.topic),
                  version=self.API_VERSION)
        start = end = int(time.time())
        interval = 10
        while end - start <= 600:
            # Wait for 600 seconds for service VM to be launched and health
            # check on VM agent port to succeed
            eventlet.sleep(interval)
            services = self.call(
                context, self.make_msg(
                    'get_services',
                    tenant_id=service_info['tenant_id'],
                    service_chain_instance_id=service_info[
                        'service_chain_instance_id'],
                    service_node_id=service_info['service_node_id']))

            end = int(time.time())

            if not services:
                err_msg = ("Service VM for service %s is not yet created by "
                           "service controller. Retrying.."
                           % service_info['service_type'])
                LOG.warn(_(err_msg))
                # Sleep time here is exponentially increased for a total of 150
                # seconds in case the VM launch did not happen by this time
                if interval < 120:
                    interval += interval
                else:
                    err_msg = ("Service VM for service %s is not yet created "
                               "by service controller."
                               % service_info['service_type'])
                    raise Exception(_(err_msg))
            else:
                service = services[0]
                if service['status'] == 'ACTIVE':
                    LOG.info(_("Service %s became ACTIVE"),
                             service_info['service_type'])
                    vm_ips = self.call(context,
                                       self.make_msg('get_management_ips', service_id=service['id']))
                    return vm_ips
                elif service['status'] == 'ERROR':
                    err_msg = "Service %s went to ERROR state" % service_info[
                        'service_type']
                    LOG.error(_(err_msg))
                    raise Exception(err_msg)

        err_msg = "Service VM bringup did not complete in 10 minutes"
        LOG.error(_(err_msg))
        raise Exception(err_msg)

    def delete_service(self, context, tenant_id, service_chain_instance_id,
                       service_node_id):
        services = self.call(
            context, self.make_msg(
                'get_services',
                tenant_id=tenant_id,
                service_chain_instance_id=service_chain_instance_id,
                service_node_id=service_node_id))
        if services:
            return self.call(context,
                             self.make_msg('delete_service', service_id=services[0]['id']))

    def get_management_ips(self, context, tenant_id, service_chain_instance_id,
                           service_node_id):
        services = self.call(
            context, self.make_msg(
                'get_services',
                tenant_id=tenant_id,
                service_chain_instance_id=service_chain_instance_id,
                service_node_id=service_node_id))
        if services:
            vm_ips = self.call(context,
                               self.make_msg('get_management_ips', service_id=services[0]['id']))
            return vm_ips
        else:
            return {}
