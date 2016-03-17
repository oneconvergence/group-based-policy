skip_kwargs_validation_for = ['firewall', 'vpn', 'loadbalancer']

request_data = {'info': {},
                'config': []
                }

request_data_info = {'version': "",
                     'service_type': ""
                     }

request_data_config = {'resource': "",
                       'kwargs': ""
                       }

interfaces = {'context': {},
              'request_info': {},
              'vm_mgmt_ip': "",
              'service_vendor': "",
              'provider_ip': "",
              'provider_cidr': "",
              'provider_interface_position': "",
              'stitching_ip': "",
              'stitching_cidr': "",
              'stitching_interface_position': "",
              'provider_mac': "",
              'stitching_mac': "",
              'rule_info': {'active_provider_mac': "",
                            'active_stitching_mac': "",
                            'active_fip': "",
                            'service_id': "",
                            'tenant_id': ""
                            },
              'service_type': ""
              }

interfaces_rule_info = {'active_provider_mac': "",
                        'active_stitching_mac': "",
                        'active_fip': "",
                        'service_id': "",
                        'tenant_id': ""
                        }

routes = {'context': {},
          'request_info': {},
          'vm_mgmt_ip': "",
          'service_vendor': "",
          'source_cidrs': "",
          'destination_cidr': "",
          'gateway_ip': "",
          'provider_interface_position': "",
          'service_type': "",
          }

healthmonitor = {'context': {},
                 'request_info': {},
                 'service_type': "",
                 'vmid': "",
                 'mgmt_ip': "",
                 'periodicity': "",
                 }
