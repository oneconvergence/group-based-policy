import socket

from neutron.common import exceptions
from neutron.common import rpc as n_rpc
from neutron.db import agents_db
from neutron.db import agentschedulers_db
from neutron import manager
from neutron_vpnaas.db.vpn import vpn_validator
from neutron_vpnaas.services.vpn.common import constants as const
from neutron_vpnaas.services.vpn.common import topics
from neutron_vpnaas.services.vpn.plugin import VPNPlugin
from neutron_vpnaas.services.vpn import service_drivers
from neutron_vpnaas.services.vpn.service_drivers import base_ipsec

from oslo_log import log as logging
import oslo_messaging

LOG = logging.getLogger(__name__)

BASE_IPSEC_VERSION = '1.0'


class VPNAgentHostingServiceNotFound(exceptions.NeutronException):
    message = _("VPN Agent hosting vpn service '%(vpnservice_id)s' not found")


class VPNAgentNotFound(exceptions.NeutronException):
    message = _("VPN Agent not found in agent_db")


class IpsecSiteConnOverlappingPeerAdress(exceptions.NeutronException):
    message = _("Overlapping peer cidr '%(peer_cidr)s' for \
        peer '%(peer_address)s'")


class DuplicateVpnService(exceptions.NeutronException):
    message = _("Duplicate vpn service '%(name)s'")


class VpnServiceInvalidSubnet(exceptions.NeutronException):
    message = _("Invalid subnet '%(subnet_id)s'")


class InvalidVPNServiceDesc(exceptions.NeutronException):
    message = _("Invalid vpn svc desc '%(desc)s' should be \
        e.g., fip=192.168.20.120;tunnel_local_cidr=10.0.0.0/24")


class VPNServiceInErrorState(exceptions.NeutronException):
    message = _("VPN service is in error state")


class VPNPluginExt(VPNPlugin, agentschedulers_db.AgentSchedulerDbMixin):
    """
    Extends the base VPN Plugin class to inherit agentdb too.
    Required to get agent entry into the database.
    """

    def __init__(self):
        super(VPNPluginExt, self).__init__()


class OCIPsecVpnDriverCallBack(object):
    """Callback for IPSecVpnDriver rpc."""

    target = oslo_messaging.Target(version=BASE_IPSEC_VERSION)

    def __init__(self, driver):
        super(OCIPsecVpnDriverCallBack, self).__init__()
        self.driver = driver

    def create_rpc_dispatcher(self):
        return n_rpc.PluginRpcDispatcher([self])

    def get_vpn_servicecontext(self, context, svctype, filters=None):
        if svctype == const.SERVICE_TYPE_IPSEC:
            return self._get_ipsec_site2site_contexts(context, filters)
        elif svctype == const.SERVICE_TYPE_OPENVPN:
            return self._get_ssl_vpn_contexts(context, filters)

    def get_ipsec_conns(self, context, filters):
        plugin = self.driver.service_plugin
        ipsec_site_conns = plugin.get_ipsec_site_connections(
            context,
            filters=filters,
            fields=None)
        return ipsec_site_conns

    def get_vpn_services(self, context, ids=None, filters=None):
        plugin = self.driver.service_plugin
        vpnservices = []

        if ids:
            for svc_id in ids:
                vpnservice = plugin.get_vpnservice(context, svc_id)
                vpnservices.append(vpnservice)
        else:
            if filters:
                vpnservices = plugin.get_vpnservices(
                    context, filters=filters)

        return vpnservices

    def update_status(self, context, **status):
        """Update status of vpnservices."""
        plugin = self.driver.service_plugin
        plugin.update_status_by_agent(context, status['status'])

    def ipsec_site_conn_deleted(self, context, **resource_id):
        """ Delete ipsec connection notification from driver."""
        resource_id = resource_id['resource_id']
        plugin = self.driver.service_plugin
        plugin._delete_ipsec_site_connection(context, resource_id)

    def vpnservice_deleted(self, context, **kwargs):
        vpnservice_id = kwargs['id']
        plugin = self.driver.service_plugin
        plugin._delete_vpnservice(context, vpnservice_id)

    def update_ipsec_site_conn_description(self, context, conn_id,
                                           description):
        plugin = self.driver.service_plugin
        plugin.update_ipsec_site_connection(context, conn_id, description)

    def _get_ipsec_site2site_contexts(self, context, filters=None):
        """
        filters =   {   'tenant_id': <value>,
                        'vpnservice_id': <value>,
                        'siteconn_id': <value>
                    }
                    'tenant_id' - To get s2s conns of that tenant
                    'vpnservice_id' - To get s2s conns of that vpn service
                    'siteconn_id' - To get a specific s2s conn

        { 'vpnserviceid':
            { 'service': <VPNServiceDbObject>,
              'siteconns':  [   {
                                'connection': <IPSECsiteconnectionsDbObject>,
                                'ikepolicy': <IKEPolicyDbObject>,
                                'ipsecpolicy': <IPSECPolicyDbObject>
                                }
                            ]
            }
        }
        """
        vpnservices = {}

        plugin = self.driver.my_plugin
        core_plugin = self.driver.core_plugin
        s_filters = {}

        if 'tenant_id' in filters:
            s_filters['tenant_id'] = [filters['tenant_id']]
        if 'vpnservice_id' in filters:
            s_filters['vpnservice_id'] = [filters['vpnservice_id']]
        if 'siteconn_id' in filters:
            s_filters['id'] = [filters['siteconn_id']]
        if 'peer_address' in filters:
            s_filters['peer_address'] = [filters['peer_address']]

        ipsec_site_conns = plugin.get_ipsec_site_connections(
            context, filters=s_filters, fields=None)

        for ipsec_site_conn in ipsec_site_conns:
            vpnservice = plugin.get_vpnservice(
                context, ipsec_site_conn['vpnservice_id'])

            ikepolicy = plugin.get_ikepolicy(
                context, ipsec_site_conn['ikepolicy_id'])

            ipsecpolicy = plugin.get_ipsecpolicy(
                context, ipsec_site_conn['ipsecpolicy_id'])

            cidr = core_plugin.get_subnet(
                context, vpnservice['subnet_id'])['cidr']

            vpnservice['cidr'] = cidr

            siteconn = {}
            siteconn['connection'] = ipsec_site_conn
            siteconn['ikepolicy'] = ikepolicy
            siteconn['ipsecpolicy'] = ipsecpolicy
            vpnserviceid = vpnservice['id']

            if vpnserviceid not in vpnservices.keys():
                vpnservices[vpnserviceid] = \
                    {'service': vpnservice, 'siteconns': []}

            vpnservices[vpnserviceid]['siteconns'].append(siteconn)

        site2site_context = self.driver._make_vpnservice_context(vpnservices)
        return site2site_context


class OCIpsecVpnAgentApi(service_drivers.BaseIPsecVpnAgentApi):
    """API and handler for OC IPSec plugin to agent RPC messaging."""
    target = oslo_messaging.Target(version=BASE_IPSEC_VERSION)

    def __init__(self, topic, default_version, driver):
        super(OCIpsecVpnAgentApi, self).__init__(
            topic, default_version, driver)

    def _is_agent_hosting_vpnservice(self, agent, vpnservice_id):
        """
        In case we have agent running on each compute node.
        We have to write logic here to get
        the agent which is hosting this vpn service
        """
        host = agent['host']
        lhost = socket.gethostname()
        if host == lhost:
            return True
        return False

    def _get_agent_hosting_vpnservice(self, admin_context, vpnservice_id):
        filters = {'agent_type': [const.AGENT_TYPE_VPN]}
        agents = manager.NeutronManager.get_plugin().get_agents(
            admin_context,  filters=filters)

        try:
            for agent in agents:
                if not agent['alive']:
                    continue
                res = self._is_agent_hosting_vpnservice(
                    agent, vpnservice_id)
                if res is True:
                    return agent

            # valid vpn agent is not found, hostname comparison might be
            # failed. Return whichever agent is available.
            for agent in agents:
                if not agent['alive']:
                    continue
                return agent
        except:
            raise VPNAgentNotFound()

        LOG.error(_('No active vpn agent found. Configuration will fail.'))
        raise VPNAgentHostingServiceNotFound(vpnservice_id=vpnservice_id)

    def _agent_notification(self, context, method, vpnservice_id,
                            version=None, **kwargs):
        """Notify update for the agent.
            For some reason search with
            'agent_type=AGENT_TYPE_VPN is not working.
            Hence, get all the agents,
            loop and find AGENT_TYPE_VPN, and also the one which
            is hosting that vpn service and
            implementing OC_IPSEC_TOPIC
        """
        admin_context = context.is_admin and context or context.elevated()

        if not version:
            version = self.target.version
        vpn_agent = self._get_agent_hosting_vpnservice(
            admin_context, vpnservice_id)

        LOG.debug(_('Notify agent at %(topic)s.%(host)s the message '
                    '%(method)s %(args)s'), {
            'topic': self.topic, 'host': vpn_agent['host'],
            'method': method, 'args': kwargs})

        cctxt = self.client.prepare(server=vpn_agent['host'],
                                    version=version)
        cctxt.cast(context, method, **kwargs)

    def vpnservice_updated(self, context, vpnservice_id, **kwargs):
        """
        Make rpc to agent for 'vpnservice_updated'
        """
        try:
            self._agent_notification(
                context, 'vpnservice_updated',
                vpnservice_id, **kwargs)
        except:
            LOG.error(_('Notifying agent failed'))


class OCIPsecVPNDriver(base_ipsec.BaseIPsecVPNDriver):
    """VPN Service Driver class for IPsec."""

    def __init__(self, service_plugin):
        super(OCIPsecVPNDriver, self).__init__(
            service_plugin,
            OCVpnValidator(service_plugin))

    def create_rpc_conn(self):
        self._core_plugin = None
        self.endpoints = [
            OCIPsecVpnDriverCallBack(self),
            agents_db.AgentExtRpcCallback(VPNPluginExt())]

        self.conn = n_rpc.create_connection(new=True)
        self.conn.create_consumer(
            topics.VPN_PLUGIN_TOPIC, self.endpoints, fanout=False)
        self.conn.consume_in_threads()
        self.agent_rpc = OCIpsecVpnAgentApi(
            topics.VPN_AGENT_TOPIC, BASE_IPSEC_VERSION, self)

    @property
    def service_type(self):
        return 'VPN'

    @property
    def my_plugin(self):
        return self.service_plugin

    @property
    def core_plugin(self):
        if not self._core_plugin:
            self._core_plugin = manager.NeutronManager.get_plugin()
        return self._core_plugin

    def _get_service_vendor(self, context, vpnservice_id):
        vpnservice = self.service_plugin.get_vpnservice(
                context, vpnservice_id)
        desc = vpnservice['description']
        # if the call is through GBP workflow,
        # fetch the service profile from description
        # else, use 'VYOS' as the service profile
        if 'service_vendor=' in desc:
            tokens = desc.split(';')
            service_vendor = tokens[5].split('=')[1]
        else:
            service_vendor = 'VYOS'
        return service_vendor

    def create_ipsec_site_connection(self, context, ipsec_site_connection):
        service_vendor = self._get_service_vendor(
            context, ipsec_site_connection['vpnservice_id'])
        self.agent_rpc.vpnservice_updated(
            context,
            ipsec_site_connection['vpnservice_id'],
            rsrc_type='ipsec_site_connection',
            svc_type=const.SERVICE_TYPE_IPSEC,
            rsrc_id=ipsec_site_connection['id'],
            resource=ipsec_site_connection,
            reason='create', service_vendor=service_vendor)

    def update_ipsec_site_connection(self,
                                     context,
                                     old_ipsec_site_connection,
                                     ipsec_site_connection):
        service_vendor = self._get_service_vendor(
            context, ipsec_site_connection['vpnservice_id'])
        self.agent_rpc.vpnservice_updated(
            context,
            ipsec_site_connection['vpnservice_id'],
            rsrc_type='ipsec_site_connection',
            svc_type=const.SERVICE_TYPE_IPSEC,
            rsrc_id=ipsec_site_connection['id'],
            resource={
                'old': old_ipsec_site_connection,
                'new': ipsec_site_connection},
            reason='update', service_vendor=service_vendor)

    def delete_ipsec_site_connection(self, context, ipsec_site_connection):
        service_vendor = self._get_service_vendor(
            context, ipsec_site_connection['vpnservice_id'])
        self.agent_rpc.vpnservice_updated(
            context,
            ipsec_site_connection['vpnservice_id'],
            rsrc_type='ipsec_site_connection',
            svc_type=const.SERVICE_TYPE_IPSEC,
            rsrc_id=ipsec_site_connection['id'],
            resource=ipsec_site_connection,
            reason='delete', service_vendor=service_vendor)

    def create_ikepolicy(self, context, ikepolicy):
        pass

    def delete_ikepolicy(self, context, ikepolicy):
        pass

    def update_ikepolicy(self, context, old_ikepolicy, ikepolicy):
        pass

    def create_ipsecpolicy(self, context, ipsecpolicy):
        pass

    def delete_ipsecpolicy(self, context, ipsecpolicy):
        pass

    def update_ipsecpolicy(self, context, old_ipsec_policy, ipsecpolicy):
        pass

    def create_vpnservice(self, context, vpnservice):
        service_vendor = self._get_service_vendor(context,
                                                  vpnservice['id'])
        self.agent_rpc.vpnservice_updated(
            context,
            vpnservice['id'],
            rsrc_type='vpn_service',
            svc_type=const.SERVICE_TYPE_IPSEC,
            rsrc_id=vpnservice['id'],
            resource=vpnservice,
            reason='create', service_vendor=service_vendor)

    def update_vpnservice(self, context, old_vpnservice, vpnservice):
        pass

    def delete_vpnservice(self, context, vpnservice):
        service_vendor = self._get_service_vendor(context,
                                                  vpnservice['id'])
        self.agent_rpc.vpnservice_updated(
            context,
            vpnservice['id'],
            rsrc_type='vpn_service',
            svc_type=const.SERVICE_TYPE_IPSEC,
            rsrc_id=vpnservice['id'],
            resource=vpnservice,
            reason='delete', service_vendor=service_vendor)

    def _make_vpnservice_context(self, vpnservices):
        """
        Generate vpnservice context from the dictionary of vpnservices.
        See, if some values are not needed by agent-driver, do not pass them.
        As of now, passing everything.
        """

        return vpnservices.values()


class OCVpnValidator(vpn_validator.VpnReferenceValidator):

    def __init__(self, service_plugin):
        self.service_plugin = service_plugin
        super(OCVpnValidator, self).__init__()

    def _vpnsvc_validate_subnet_id(self,
                                   context,
                                   subnet_id):
        subnet = self.core_plugin.\
            get_subnet(context, subnet_id)
        if not subnet:
            raise VpnServiceInvalidSubnet(subnet_id=subnet_id)

    def _vpnsvc_validate_desc(self, vpnsvc):
        desc = vpnsvc['description']
        if 'fip=' not in desc:
            raise InvalidVPNServiceDesc(desc=desc)
        if 'tunnel_local_cidr' not in desc:
            raise InvalidVPNServiceDesc(desc=desc)
        if 'service_vendor' not in desc:
            raise InvalidVPNServiceDesc(desc=desc)

    def _vpnsvc_get_lcidr(self, desc):
        return desc.split(';')[0].split('=')[1]

    def _vpnsvc_validate_lcidr(self, context, vpnsvc):
        desc = vpnsvc['description']
        lcidr = self._vpnsvc_get_lcidr(vpnsvc)

        filters = {'tenant_id': [context.tenant_id]}
        vpnsvcs = self.service_plugin.get_vpnservices(
            context, filters=filters)
        for svc in vpnsvcs:
            l_lcidr = self._vpnsvc_get_lcidr(
                svc['description'])
            if l_lcidr == lcidr:
                raise DuplicateVpnService(
                    name=vpnsvc['name'])

    def _ipsec_validate_tunnels(self,
                                context,
                                ipsec_siteconn):
        # Get the conns for this tenant
        filters = {
            'tenant_id': [context.tenant_id],
            'vpnservice_id': [ipsec_siteconn['vpnservice_id']],
            'peer_address': [ipsec_siteconn['peer_address']]}

        siteconns = self.service_plugin.get_ipsec_site_connections(
            context,
            filters=filters)

        for siteconn in siteconns:
            n_pcidrs = ipsec_siteconn['peer_cidrs']
            pcidrs = siteconn['peer_cidrs']
            for pcidr in pcidrs:
                if pcidr in n_pcidrs:
                    raise IpsecSiteConnOverlappingPeerAdress(
                        peer_address=ipsec_siteconn['peer_address'],
                        peer_cidr=pcidr)

    def validate_vpnservice(self, context, vpnservice):
        # Validate subnet id to be valid
        self._vpnsvc_validate_subnet_id(
            context, vpnservice['subnet_id'])

    def _check_vpnsvc_state(self, context, vpnsvc):
        if vpnsvc['status'] == 'ERROR':
            raise VPNServiceInErrorState()

    def validate_ipsec_site_connection(self, context, ipsec_sitecon,
                                       ip_version, vpnservice=None):
        super(OCVpnValidator, self).validate_ipsec_site_connection(
            context, ipsec_sitecon, ip_version, vpnservice)

        if vpnservice:
            self._check_vpnsvc_state(
                context, vpnservice)

        # Check if this conn has overlapping tunnel def
        # with other conns for same tenant + same vpn service
        if ipsec_sitecon.get("id", None):
            self._ipsec_validate_tunnels(context, ipsec_sitecon)

    def assign_sensible_ipsec_siteconn_defaults(self,
                                                ipsec_sitecon,
                                                prev_conn=None):
        pass
