from neutron.db.vpn import vpn_db
from neutron import manager
from oslo.config import cfg
from oslo import messaging

from neutron.agent import rpc as agent_rpc
from neutron.common import exceptions
from neutron.services.vpn.common import topics
from neutron import context
from neutron.openstack.common import lockutils
from neutron.openstack.common import importutils
from neutron.openstack.common import log as logging
from neutron.openstack.common import loopingcall
from neutron.openstack.common import periodic_task
from neutron.plugins.common import constants
from neutron.services.vpn.common import constants as vpn_const
from neutron.services.vpn import RestClientOverUnix as rest_client

class UnknownSvcTypeException(exceptions.NeutronException):
    message = _("Unsupported rpcsvc_type '%(svc_type)s' from plugin ")

class UnknownResourceException(exceptions.NeutronException):
    message = _("Unsupported resource '%(resource)s' from plugin ")

class UnknownReasonException(exceptions.NeutronException):
    message = _("Unsupported rpcreason '%(reason)s' from plugin ")

class TenantNotFound(exceptions.NeutronException):
    message = _("Cannot Get context as tenant_id is not available")

LOG = logging.getLogger(__name__)

vpn_agent_opts = [
    cfg.MultiStrOpt(
        'vpn_device_driver',
        default=[],
        help=_("The vpn device drivers Neutron will use")),
]
cfg.CONF.register_opts(vpn_agent_opts, 'vpnagent')

REQUEST_METHOD = 'http' #can be http,https
SERVER_IP_ADDR = '192.168.2.68'

#class VpnAgentManager(periodic_task.PeriodicTasks, vpn_db.VPNPluginDb, vpn_db.VPNPluginRpcDbMixin):
class VpnAgentManager(vpn_db.VPNPluginDb, vpn_db.VPNPluginRpcDbMixin):
    def __init__(self, conf):
        super(VpnAgentManager, self).__init__()

        self.needs_sync = True
        self.conf = conf
        self.context = context.get_admin_context_without_session()
        self.agent_state = {
            'binary': 'oc-vpn-agent',
            'host': conf.host,
            'topic': topics.VPN_AGENT_TOPIC,
            'agent_type': vpn_const.AGENT_TYPE_VPN,
            'start_flag': True}
        self.admin_state_up = True
        self.state_rpc = agent_rpc.PluginReportStateAPI(
            topics.VPN_PLUGIN_TOPIC)
        report_interval = self.conf.AGENT.report_interval
        if report_interval:
            heartbeat = loopingcall.FixedIntervalLoopingCall(
                self._report_state)
            heartbeat.start(interval=report_interval)
        self.handlers = {
            vpn_const.SERVICE_TYPE_IPSEC :{
                'vpn_service': {
                    'create': self.create_vpn_service},
                'ipsec_site_connection': {
                    'create': self.create_ipsec_conn,
                    'update': self.update_ipsec_conn,
                    'delete': self.delete_ipsec_conn}},
            vpn_const.SERVICE_TYPE_OPENVPN : {
                'vpn_service': {
                    'create': self.create_vpn_service},
                'ssl_vpn_connection': {
                    'create': self.create_sslvpn_conn,
                    'update': self.update_sslvpn_conn,
                    'delete': self.delete_sslvpn_conn}}
            }
        self._core_plugin = None

    def _report_state(self):
        LOG.debug(_("[VPN Agent] Report state task invoked"))
        try:
            self.state_rpc.report_state(self.context, self.agent_state)
            self.agent_state.pop('start_flag', None)
        except Exception:
            LOG.exception(_("[VPN Agent] Failed reporting state!"))


    @property
    def core_plugin(self):
        if not self._core_plugin:
            self._core_plugin = manager.NeutronManager.get_plugin()
        return self._core_plugin

    def vpnservice_updated(self, context, **kwargs):
        LOG.debug(_("vpnservice_updated from server side"))
        resource = kwargs.get('resource')
        tenant_id = resource['tenant_id']
        @lockutils.synchronized(tenant_id)
        def _vpnservice_updated(context, **kwargs):
            svc_type = kwargs.get('svc_type')
            rsrc = kwargs.get('rsrc_type')
            reason = kwargs.get('reason')
            if svc_type not in self.handlers.keys():
                raise UnknownSvcTypeException(svc_type=svc_type)
            if rsrc not in self.handlers[svc_type].keys():
                raise UnknownResourceException(resource=driver)
            if reason not in self.handlers[svc_type][rsrc].keys():
                raise UnknownReasonException(reason=reason)

            self.handlers[svc_type][rsrc][reason](context,  **kwargs)
        return _vpnservice_updated(context, **kwargs)
    '''
    def _get_vpn_services(self, context, ids=None, filters=None):
        vpnservices = []
        if ids:
            for id in ids:
                vpnservice = super(VpnAgentManager, self).get_vpnservice(context,  id)
                vpnservices.append(vpnservice)
        else:
            if filters:
                vpnservices = super(VpnAgentManager, self).get_vpnservices(
                    context, filters=filters)

        return vpnservices
    '''
    def create_vpn_service(self, context, **kwargs):
        svc = kwargs.get('resource')
        filters = {'tenant_id': [context.tenant_id]}
        #t_vpnsvcs = self._get_vpn_services(
        #    context, filters=filters)
        data_context = self._get_all_context_for_given_tenant(context)
        body = {'resource_data': svc,
                'tenant_data': data_context}
        rest_client.send_request(REQUEST_METHOD,
                                 SERVER_IP_ADDR,
                                 'vpn/create_vpnservices',
                                 'POST',
                                 headers = 'application/json',
                                 body = body) 
    '''
    def _get_ipsec_conns(self, context, filters):
        ipsec_site_conns = super(VpnAgentManager, self).\
            get_ipsec_site_connections(
                context,
                filters=filters,
                fields=None)
        return ipsec_site_conns
    '''
    '''
    def _ipsec_get_tenant_conns(self, context, conn, on_delete=False):
        filters = {
            'tenant_id': [context.tenant_id],
            'peer_address': [conn['peer_address']]}
        tenant_conns = self._get_ipsec_conns(
            context, filters)
        if (not on_delete) and (tenant_conns):
            tenant_conns.remove(conn)
            copy_conns = copy.deepcopy(tenant_conns)
            for tconn in copy_conns:
                if tconn['status'] == vpn_const.STATE_PENDING:
                    tenant_conns.remove(tconn)
        return tenant_conns
    '''
    '''
    def _make_vpnservice_context(self, vpnservices):
        return vpnservices.values()
    '''
    '''
    def _get_ipsec_site2site_contexts(self, context,  filters=None):
        vpnservices = {}
        core_plugin = self.core_plugin
        s_filters = {}
        if 'tenant_id' in filters:
            s_filters['tenant_id'] = [filters['tenant_id']]
        if 'vpnservice_id' in filters:
            s_filters['vpnservice_id'] = [filters['vpnservice_id']]
        if 'siteconn_id' in filters:
            s_filters['id'] = [filters['siteconn_id']]
        if 'peer_address' in filters:
            s_filters['peer_address'] = [filters['peer_address']]

        ipsec_site_conns = super(VpnAgentManager, self).get_ipsec_site_connections(
            context,
            filters=s_filters,
            fields=None)

        for ipsec_site_conn in ipsec_site_conns:
            vpnservice = super(VpnAgentManager, self).get_vpnservice(
                context,
                ipsec_site_conn['vpnservice_id'])

            ikepolicy = super(VpnAgentManager, self).get_ikepolicy(
                context,
                ipsec_site_conn['ikepolicy_id'])

            ipsecpolicy = super(VpnAgentManager, self).get_ipsecpolicy(
                context,
                ipsec_site_conn['ipsecpolicy_id'])
            cidr = core_plugin.get_subnet(
                context,
                vpnservice['subnet_id'])['cidr']
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

        site2site_context = self._make_vpnservice_context(vpnservices)
        return site2site_context
    '''
    '''
    def _get_ssl_vpn_contexts(self, context, filters=None):
        vpnservices = {}

        core_plugin = self.core_plugin
        s_filters = {}

        if 'tenant_id' in filters:
                    s_filters['tenant_id'] = [filters['tenant_id']]
        if 'vpnservice_id' in filters:
                    s_filters['vpnservice_id'] = [filters['vpnservice_id']]
        if 'sslvpnconn_id' in filters:
                    s_filters['id'] = [filters['sslvpnconn_id']]

        ssl_vpn_conns = super(VpnAgentManager, self).get_ssl_vpn_connections(
            context,
            filters=s_filters,
            fields=None)

        for ssl_vpn_conn in ssl_vpn_conns:
            vpnservice = super(VpnAgentManager, self).get_vpnservice(
                context,
                ssl_vpn_conn['vpnservice_id'])

            cidr = core_plugin.get_subnet(
                context,
                vpnservice['subnet_id'])['cidr']

            vpnservice['cidr'] = cidr

            sslconn = {}
            sslconn['connection'] = ssl_vpn_conn
            sslconn['credential'] = None
            vpnserviceid = vpnservice['id']

            if vpnserviceid not in vpnservices.keys():
                vpnservices[vpnserviceid] = \
                    {'service': vpnservice, 'sslvpnconns': []}
            vpnservices[vpnserviceid]['sslvpnconns'].append(sslconn)

        sslvpn_context = self._make_vpnservice_context(vpnservices)
        return sslvpn_context
    '''
    '''
    def _get_vpn_servicecontext(self,  context,  svctype,  filters=None):
        if svctype == vpn_const.SERVICE_TYPE_IPSEC:
            return self._get_ipsec_site2site_contexts(context,  filters)
        elif svctype == vpn_const.SERVICE_TYPE_OPENVPN:
            return self._get_ssl_vpn_contexts(context, filters)
    '''
    '''
    def _get_ipsec_contexts(self, context, tenant_id=None,
                           vpnservice_id=None, conn_id=None,
                           peer_address=None):
        filters = {}
        if tenant_id:
            filters['tenant_id'] = tenant_id
        if vpnservice_id:
            filters['vpnservice_id'] = vpnservice_id
        if conn_id:
            filters['siteconn_id'] = conn_id
        if peer_address:
            filters['peer_address'] = peer_address

        return self.\
            _get_vpn_servicecontext(
                context,
                vpn_const.SERVICE_TYPE_IPSEC, filters)
    '''
    def create_ipsec_conn(self, context, **kwargs):
        conn = kwargs.get('resource')
        #vpnservice_id = conn['vpnservice_id']
        #tenant_conns = self._ipsec_get_tenant_conns(
        #    context, conn)
        #svc_contexts = self._get_ipsec_contexts(
        #    context, conn_id=conn['id'])
        data_context = self._get_all_context_for_given_tenant(context)
        body = {'resource_data': conn,
                'tenant_data': data_context}
        rest_client.send_request(REQUEST_METHOD,
                                 SERVER_IP_ADDR,
                                 'vpn/create_ipsec_conn',
                                 'POST',
                                 headers = 'application/json',
                                 body = body) 

    def update_ipsec_conn(self, context, **kwargs):
        update_conn = kwargs.get('resource')
        #svc_contexts = self._get_ipsec_contexts(
        #    context, conn_id=kwargs.get('id'))
        data_context = self._get_all_context_for_given_tenant(context)
        body = {'resource_data': update_conn,
                'tenant_data': data_context}
        rest_client.send_request(REQUEST_METHOD,
                                 SERVER_IP_ADDR,
                                 'vpn/update_ipsec_conn',
                                 'PUT',
                                 headers = 'application/json',
                                 body = body) 

    def delete_ipsec_conn(self, context, **kwargs):
        conn = kwargs.get('resource')
        #vpn_svcs = self._get_vpn_services(
        #    context, ids=[conn['vpnservice_id']])
        #tenant_conns = self._ipsec_get_tenant_conns(
        #    context, conn, on_delete=True)
        data_context = self._get_all_context_for_given_tenant(context)
        body = {'resource_data': update_conn,
                'tenant_data': data_context}
        rest_client.send_request(REQUEST_METHOD,
                                 SERVER_IP_ADDR,
                                 'vpn/delete_ipsec_conn',
                                 'DELETE',
                                 headers = 'application/json',
                                 body = body)
    '''
    def _get_ssl_vpn_conns(self, context, filters):
        ssl_vpn_conns = super(VpnAgentManager, self).\
            get_ssl_vpn_connections(
                context,
                filters=filters)
        return ssl_vpn_conns
    '''
    '''
    def _sslvpn_get_tenant_conns(self, context, conn, on_delete=False):
        filters = {'tenant_id': [context.tenant_id]}
        tenant_conns = self._get_ssl_vpn_conns(
            context, filters=filters)

        if not on_delete:
            tenant_conns.remove(conn)
            copy_conns = copy.deepcopy(tenant_conns)
            for tconn in copy_conns:
                if tconn['status'] == vpn_const.STATE_PENDING:
                    tenant_conns.remove(tconn)
        return tenant_conns
    '''
    '''
    def _get_sslvpn_contexts(self, context, tenant_id=None,
                            vpnservice_id=None, conn_id=None):
        filters = {}
        if tenant_id:
            filters['tenant_id'] = tenant_id
        if vpnservice_id:
            filters['vpnservice_id'] = vpnservice_id
        if conn_id:
            filters['sslvpnconn_id'] = conn_id

        return self.\
            _get_vpn_servicecontext(
                context,
                vpn_const.SERVICE_TYPE_OPENVPN, filters)
    '''
    def create_sslvpn_conn(self, context, **kwargs):
        conn = kwargs.get('resource')
        #t_conns = self._sslvpn_get_tenant_conns(
        #    context, conn)
        #svc_context = self._get_sslvpn_contexts(
        #    context, conn_id=conn['id'])

        data_context = self._get_all_context_for_given_tenant(context)
        body = {'resource_data': conn,
                'tenant_data': data_context}
        rest_client.send_request(REQUEST_METHOD,
                                 SERVER_IP_ADDR,
                                 'vpn/create_sslvpn_conn',
                                 'POST',
                                 headers = 'application/json',
                                 body = body)

    def update_sslvpn_conn(self, context, **kwargs):
        pass

    def delete_sslvpn_conn(self, context, **kwargs):
        conn = kwargs.get('resource')
        #vpn_svcs = self._get_vpn_services(
        #    context, [conn['vpnservice_id']])
        #t_conns = self._sslvpn_get_tenant_conns(
        #    context, conn, on_delete=True)

        data_context = self._get_all_context_for_given_tenant(context)
        body = {'resource_data': conn,
                'tenant_data': data_context}
        rest_client.send_request(REQUEST_METHOD,
                                 SERVER_IP_ADDR,
                                 'vpn/delete_sslvpn_conn',
                                 'DELETE',
                                 headers = 'application/json',
                                 body = body)

    def _get_vpn_context(self, context, filters):
        vpnservices = super(VpnAgentManager, self).get_vpnservices(
            context,
            filters)

        ikepolicies = super(VpnAgentManager, self).get_ikepolicies(
            context,
            filters)

        ipsecpolicies = super(VpnAgentManager, self).get_ipsecpolicies(
            context,
            filters)

        ipsec_site_conns = super(VpnAgentManager, self).get_ipsec_site_connections(
            context,
            filters=s_filters)

        ssl_vpn_conns = super(VpnAgentManager, self).get_ssl_vpn_connections(
            context,
            filters=s_filters)

        return {'vpnservices': vpnservices,
                'ikepolicies': ikepolicies,
                'ipsecpolicies': ipsecpolicies,
                'ipsec_site_conns': ipsec_site_conns,
                'ssl_vpn_conns': ssl_vpn_conns}

    def _get_core_context(self, context, filters):
        core_plugin = self.core_plugin
        subnets = core_plugin.get_subnets(
                      context,
                      filters)

        routers = core_plugin.get_routers(
                      context,
                      filters)
        return {'subnets':subnets,
                'routers':routers}


    def _get_all_context_for_given_tenant(self, context, tenant_id=None):
        if tenant_id == None and context.is_admin :
            tenant_id = context.tenant_id
        if tenant_id == None :
            raise TenantNotFound() 
        filters = {'tenant_id':tenant_id}
        data_context = self._get_vpn_context(context, filters)
        data_context.update(self._get_core_context(context, filters))
        return data_context

