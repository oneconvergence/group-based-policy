import ast
import json

import requests
from gbpservice.nfp.configurator.lib import fw_constants as const
from neutron._i18n import _LE
from oslo_log import log as logging
from vyos_fw_driver import FwaasDriver


LOG = logging.getLogger(__name__)

SUCCESS_CODES = [200, 201, 202]
VYOS_PORT = '8888'


class NeutronVYOSFWDriver(FwaasDriver):
    service_type = "firewall"
    service_vendor = "neutron vyos"

    def __init__(self):
        super(FwaasDriver, self).__init__()

    def create_firewall(self, context, firewall, host):
        """
        """
        configured_services, config_erred_services = list(), list()
        services_to_configure = firewall['services_to_configure']
        fw_desc = firewall['description']
        for service in services_to_configure:
            desc = ast.literal_eval(service['description'])
            # revisit(VK) wacky wacky !!!
            firewall['description'] = str({'provider_ptg_info': [desc[
                "provider_mac"]]})
            config_ip = desc['fip']
            try:
                resp = self.do_call(config_ip, firewall, 'create')
            except Exception, err:
                config_erred_services.append(service)
                LOG.error(_LE("Failed to CONFIGURE Service - (service_id)%s "
                              "of Tenant - (tenant_id)%s "),
                          {'service_id': service['id'], 'tenant_id':
                              firewall['tenant_id']})
            else:
                if resp.status_code not in SUCCESS_CODES:
                    config_erred_services.append(service)
                else:
                    configured_services.append(service)

        firewall.update(config_erred_services=config_erred_services,
                        configured_services=configured_services,
                        description=fw_desc)
        status = "ACTIVE" if configured_services else "ERROR"
        return status, firewall

    def delete_firewall(self, context, firewall, host):
        """
        """
        config_deleted_services, delete_erred_services = list(), list()
        services_to_configure = firewall['services_to_delete']
        fw_desc = firewall['description']
        for service in services_to_configure:
            desc = ast.literal_eval(service['description'])
            firewall['description'] = str({'provider_ptg_info': [desc[
                "provider_mac"]]})
            config_ip = desc['fip']
            try:
                resp = self.do_call(config_ip, firewall, 'delete')
            except Exception, err:
                delete_erred_services.append(service)
                LOG.error(_LE("Failed to DELETE Service - (service_id)%s "
                              "of Tenant - (tenant_id)%s "),
                          {'service_id': service['id'], 'tenant_id':
                              firewall['tenant_id']})
            else:
                if resp.status_code not in SUCCESS_CODES:
                    delete_erred_services.append(service)
                else:
                    config_deleted_services.append(service)

        firewall.update(delete_erred_services=delete_erred_services,
                        config_deleted_services=config_deleted_services,
                        description=fw_desc)
        status = "ERROR" if delete_erred_services else "SUCCESS"
        return status, firewall

    def do_call(self, config_ip, firewall, method_name):
        api = {'create': 'configure-firewall-rule',
               'delete': 'delete-firewall-rule'}
        url = const.request_url % (config_ip, VYOS_PORT,
                                   api[method_name])
        data = json.dumps(firewall)
        try:
            if method_name.lower() == 'delete':
                resp = requests.delete(url, data=data, timeout=self.timeout)
            else:
                resp = requests.post(url, data=data, timeout=self.timeout)
        except requests.exceptions.ConnectionError as err:
            self._print_exception('ConnectionError', err, url, 'create')
            raise requests.exceptions.ConnectionError()
        except requests.exceptions.RequestException as err:
            self._print_exception('RequestException', err, url, 'create')
            raise requests.exceptions.RequestException()
        return resp


