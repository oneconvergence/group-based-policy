from gbpservice.neutron.nsf.configurator.lib import (
    filter_constants as constants)


class Filter():

    def __init__(self, topic, default_version):
        pass

    def call(self, context, msg):
        """
        :param context
        :param msg e.g  {'args': {'key': value,..},'method': 'function_name'}}
        :returns data after applying filter on it
        """
        try:
            filters = msg['args']
            method = getattr(self, '%s' % (msg['method']))
            return method(context, filters)
        except Exception as e:
            raise e

    def make_msg(self, method, **kwargs):
        return {'method': method,
                'args': kwargs}

    def apply_filter(self, data, filters):
        """
        :param filter e.g  {k:[v],k:[v]}
        :param data e.g [{k:v,k:v,k:v},
                      {k:v,k:v,k:v},
                      {k:v,k:v}]
        """
        for fk, fv in filters.items():
            for d in data[:]:
                if d.get(fk) is None:
                    data.remove(d)
                if fk in d and d[fk] != fv[0]:
                    data.remove(d)
        return data

    def get_record(self, data, key, value):
        """Get single record based on key and value
        :param data
        :praam key
        :param value
        """
        for d in data:
            if key in d and d[key] == value:
                return d

    def get_vpn_services(self, context, filters):
        """
        :param filters e.g { 'ids' : [list vpn service ids],
                              'filters': filters
                            }
        """
        vpn_ids = None
        if 'ids' in filters and filters['ids']:
            vpn_ids = filters['ids']
        service_info = context['service_info']
        vpnservices = service_info['vpnservices']
        filtered_vpns = []
        if vpn_ids:
            for vpn_id in vpn_ids:
                filtered_vpns.append(
                    self.get_record(vpnservices, 'id', vpn_id))
            return filtered_vpns
        else:
            return self.apply_filter(vpnservices, filters['filters'])

    def get_ipsec_conns(self, context, filters):
        """
        :param filters e.g { 'tenant_id': [tenant_id],
                             'peer_address': [conn['peer_address']]
                           }
        """
        service_info = context['service_info']
        ipsec_conns = service_info['ipsec_site_conns']
        return self.apply_filter(ipsec_conns, filters)

    def get_ssl_vpn_conns(self, context, filters):
        """
        :param filters e.g { 'tenant_id': [tenant_id] }
        """

        service_info = context['service_info']
        ssl_vpn_conns = service_info['ssl_vpn_conns']
        return self.apply_filter(ssl_vpn_conns, filters)

    def get_vpn_servicecontext(self, context, svctype, filters):
        if svctype == constants.SERVICE_TYPE_IPSEC:
            return self._get_ipsec_site2site_contexts(context, filters)
        elif svctype == constants.SERVICE_TYPE_OPENVPN:
            return self._get_ssl_vpn_contexts(context, filters)

    def _get_ipsec_site2site_contexts(self, context, filters=None):
        """
        :param filters e.g   {   'tenant_id': <value>,
                               'vpnservice_id': <value>,
                               'siteconn_id': <value>
                            }
        'tenant_id' - To get s2s conns of that tenant
        'vpnservice_id' - To get s2s conns of that vpn service
        'siteconn_id' - To get a specific s2s conn

        :returns vpnservices
            e.g { 'vpnserviceid':
                    { 'service': <VPNService>,
                  'siteconns':[ {
                                'connection': <IPSECsiteconnections>,
                                'ikepolicy': <IKEPolicy>,
                                'ipsecpolicy': <IPSECPolicy>
                                }
                              ]
                    }
                }
        """
        service_info = context['service_info']

        vpnservices = {}
        s_filters = {}

        if 'tenant_id' in filters:
            s_filters['tenant_id'] = [filters['tenant_id']]
        if 'vpnservice_id' in filters:
            s_filters['vpnservice_id'] = [filters['vpnservice_id']]
        if 'siteconn_id' in filters:
            s_filters['id'] = [filters['siteconn_id']]
        if 'peer_address' in filters:
            s_filters['peer_address'] = [filters['peer_address']]

        ipsec_site_conns = self.apply_filter(service_info['ipsec_site_conns'],
                                             s_filters)

        for conn in ipsec_site_conns:

            vpnservice = [vpn for vpn in service_info['vpnservices']
                          if vpn['id'] == conn['vpnservice_id']][0]

            ikepolicy = [ikepolicy for ikepolicy in service_info['ikepolicies']
                         if ikepolicy['id'] == conn['ikepolicy_id']][0]

            ipsecpolicy = [ipsecpolicy for ipsecpolicy in
                           service_info['ipsecpolicies']
                           if ipsecpolicy['id'] == conn['ipsecpolicy_id']][0]
            """
            Get the local subnet cidr
            """
            subnet = [subnet for subnet in service_info['subnets']
                      if subnet['id'] == vpnservice['subnet_id']][0]
            cidr = subnet['cidr']
            vpnservice['cidr'] = cidr

            siteconn = {}
            siteconn['connection'] = conn
            siteconn['ikepolicy'] = ikepolicy
            siteconn['ipsecpolicy'] = ipsecpolicy
            vpnserviceid = vpnservice['id']

            if vpnserviceid not in vpnservices.keys():
                vpnservices[vpnserviceid] = \
                    {'service': vpnservice, 'siteconns': []}

            vpnservices[vpnserviceid]['siteconns'].append(siteconn)

        site2site_context = self._make_vpnservice_context(vpnservices)
        return site2site_context

    def _get_ssl_vpn_contexts(self, context, filters=None):
        """
        :param filters e.g   { 'tenant_id': <value>,
                                'vpnservice_id': <value>,
                                'sslvpnconn_id': <value> }

        :returns vpnservices
            e.g { 'vpnserviceid':
                    { 'service': <VPNService>,
                      'sslvpnconns': [
                                { 'connection': <SSLVPNConnection>,
                                  'credential': <VPNCredential,
                                }
                            ],
                    }
                 }
        """
        service_info = context['service_info']
        vpnservices = {}
        s_filters = {}

        if 'tenant_id' in filters:
            s_filters['tenant_id'] = [filters['tenant_id']]
        if 'vpnservice_id' in filters:
            s_filters['vpnservice_id'] = [filters['vpnservice_id']]
        if 'sslvpnconn_id' in filters:
            s_filters['id'] = [filters['sslvpnconn_id']]

        ssl_vpn_conns = self.apply_filter(service_info['ssl_vpn_conns'],
                                          s_filters)

        for conn in ssl_vpn_conns:

            vpnservice = [vpn for vpn in service_info['vpnservices']
                          if vpn['id'] == conn['vpnservice_id']][0]

            subnet = [subnet for subnet in service_info['subnets']
                      if subnet['id'] == vpnservice['subnet_id']][0]
            cidr = subnet['cidr']
            vpnservice['cidr'] = cidr

            sslconn = {}
            sslconn['connection'] = conn
            sslconn['credential'] = None
            vpnserviceid = vpnservice['id']

            if vpnserviceid not in vpnservices.keys():
                vpnservices[vpnserviceid] = \
                    {'service': vpnservice, 'sslvpnconns': []}

            vpnservices[vpnserviceid]['sslvpnconns'].append(sslconn)

        sslvpn_context = self._make_vpnservice_context(vpnservices)
        return sslvpn_context

    def _make_vpnservice_context(self, vpnservices):
        """Generate vpnservice context from the dictionary of vpnservices.
        See, if some values are not needed by agent-driver, do not pass them.
        As of now, passing everything.
        """

        return vpnservices.values()

    def get_logical_device(self, context, filters):
        """
        :param filters e.g {'pool_id': [pool_id]}
        """
        service_info = context['service_info']
        pool_id = filters.get('pool_id')
        pool = self.get_record(service_info['pools'], 'id', pool_id[0])

        '''
        pool will be in the following format

        pool = {"status": "ACTIVE", "lb_method": "ROUND_ROBIN",
        "protocol": "HTTP", "description": "Haproxy pool from teplate",
        "health_monitors": ["eaf1f1b9-ca61-41ea-ab0f-c794d8881fbb"],
        "members": ["356c52ee-ae16-494e-b16a-521876e94ca3",
                    "ec01cb97-936a-45a4-b983-ae6e7e555a71"],
         "status_description": null,
         "id": "d4b6ea3c-1f80-4705-8ea0-d53de8e90233",
         "vip_id": "8da1f096-660b-428f-b877-6267494a55b3",
         "name": "Haproxy pool-lb-provider", "admin_state_up": true,
         "subnet_id": "5de09e43-0eec-4407-ae97-40103bffad65",
         "tenant_id": "c13efc8d70164b5caba6526d7d1b37ed",
         "health_monitors_status":
              [{"monitor_id": "eaf1f1b9-ca61-41ea-ab0f-c794d8881fbb",
              "status": "ACTIVE", "status_description": null}],
          "provider": "haproxy_on_vm"}
        '''

        retval = {}
        retval['pool'] = pool  # self._make_pool_dict(pool)

        if 'vip_id' in pool and pool['vip_id'] is not None:
            vip = self.get_record(
                service_info['vips'], 'id', pool['vip_id'])
            retval['vip'] = vip  # self._make_vip_dict(vip)


            port = self.get_record(service_info['ports'],
                                   'id', vip['port_id'])
            retval['vip']['port'] = port  # self._make_port_dict(port)

            subnets = service_info['subnets']
            for fixed_ip in retval['vip']['port']['fixed_ips']:
                fixed_ip['subnet'] = self.get_record(
                    subnets, 'id',
                    fixed_ip['subnet_id'])

        pool_members = pool['members']
        retval['members'] = []

        for pm in pool_members:
            member = self.get_record(service_info['members'], 'id', pm)
            if (member['status'] in constants.ACTIVE_PENDING_STATUSES or
                    member['status'] == constants.INACTIVE):
                retval['members'].append(member)

        pool_health_monitors = pool['health_monitors_status']
        retval['healthmonitors'] = []

        for phm in pool_health_monitors:
            if phm['status'] in constants.ACTIVE_PENDING_STATUSES:
                health_monitor = self.get_record(
                    service_info['health_monitor'],
                    'id', phm['monitor_id'])
                retval['healthmonitors'].append(health_monitor)

        retval['driver'] = pool['provider']
        return retval

