#
# One Convergence, Inc. CONFIDENTIAL
# Copyright (c) 2012-2014, One Convergence, Inc., USA
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
#

import json
from urllib3 import PoolManager
from oslo.config import cfg
from neutron.openstack.common import log as logging
LOG = logging.getLogger(__name__)

"""Initialize the logging library.
    This library enables the Policy Flow Driver module to log messages in a
    specific format that is suitable for analytics.
"""

DEFAULT_OS_CONTROLLER_IP = "127.0.0.1"
DEFAULT_NETWORK_SERVER_PORT = 9696
DEFAULT_NETWORK_API_VERSION = "v2.0"

es_openstack_opts = [
    cfg.StrOpt('os_controller_ip',
               default=DEFAULT_OS_CONTROLLER_IP,
               help='Openstack controller IP Address'),
]


class PolicyFlowDriver():
    """Implements methods which interfaces with the Openstack
    For Policy Flow operations"""

    def __init__(self):
        """Initializes Openstack access URLs
        """

        self.urls = dict()
        self.conn_pool = PoolManager(num_pools=10)
        self.network_service = ("http://%s:%d/%s/" %
                                (cfg.CONF.os_controller_ip,
                                 DEFAULT_NETWORK_SERVER_PORT,
                                 DEFAULT_NETWORK_API_VERSION))

    def process_request(self, method, request_url, headers, data):
        """Invokes the REST API call.

        Arguments:
        :param method: Type of method (GET/POST/PUT/DELETE)
        :param request_url: Absolute URL of the REST call
        :param headers: HTML headers
        :param data: HTML body

        """

        try:
            conn = self.conn_pool
            response = conn.urlopen(method, request_url, body=data,
                                    headers=headers, release_conn=True)
        except Exception, err:
            print "error", "", "Failed to send HTTP request for method :: %s, URL :: %s, Error :: %s" % (method, request_url, err)
            raise

        try:
            response.release_conn()
        except Exception, err:
            print "error", "", "Failed to release URL LIB connection. Error :: %s" % err
            return

        if method == 'DELETE':
            return
        else:
            try:
                json_response = json.loads(response.data)
                return json_response
            except Exception, err:
                print "error", "", "Failed to get JSON object from dictionary format. Error :: %s" % err
                raise err

    def create_flow(self, token, policy_flow_id,tenant_id, left_group_id, right_group_id,
                     origin_port, target_port, protocol, vlans, flow_type,
                     l4_src_port, l4_dst_port,
                     left_group_type, right_group_type):
        request_url = self.network_service + "policyflows.json"
        _protocol = False
        _src_port = False
        _dst_port = False
        priority = 1

        request_headers = {'Content-type': 'application/json;charset=utf8',
           'Accept': 'application/json',
           'x-auth-token': token
           }

        data = {
                "policyflow":
                    {
                     "action_type": flow_type,
                     "target_segment": {"type": "vlan",
                                        "id": vlans},
                     }
                }

        if policy_flow_id:
            data['policyflow'].update({'id': policy_flow_id})

        if left_group_id:
            data['policyflow'].update({"pkt_src":
                                       {"type": left_group_type,
                                        "id": left_group_id}
                                       })

        if right_group_id:
            data['policyflow'].update({"pkt_dst":
                                       {"type": right_group_type,
                                        "id": right_group_id}
                                       })

        if origin_port:
            data["policyflow"].update({'origin_port': origin_port})

        if target_port:
            data["policyflow"].update({'target_port': target_port})

        if protocol:
            data["policyflow"].update({"rule":
                                        {"protocol": protocol.upper()
                                         }})
            _protocol = True

        if l4_src_port:
            _src_port = True
            if not "rule" in data["policyflow"]:
                data["policyflow"].update({"rule":
                                            {"l4_src_port": l4_src_port
                                             }})
            else:
                data["policyflow"]["rule"].update({"l4_src_port": l4_src_port})

        if l4_dst_port:
            _dst_port = True
            if not "rule" in data["policyflow"]:
                data["policyflow"].update({"rule":
                                            {"l4_dst_port": l4_dst_port
                                             }})
            else:
                data["policyflow"]["rule"].update({"l4_dst_port": l4_dst_port})
        # NC doesn't allow priority more than 5.
        if _protocol and _src_port and _dst_port:
            priority = 5
        elif _protocol and (_src_port or _dst_port):
            priority = 4
        elif _protocol and not (_src_port and _dst_port):
            priority = 3
        elif not _protocol and not (_src_port and  _dst_port):
            priority = 2

        data["policyflow"].update({"priority": priority})
        print "debug", tenant_id, "Data - %s " % data
        resp = self.process_request("POST", request_url,
                                request_headers, json.dumps(data))
        if resp.get('NeutronError'):
            raise Exception(resp.get('NeutronError')['message']
                            .encode('ascii', 'replace'))
        else:
            flow_id = resp['policyflow'].get('id')
            return flow_id
        
        

    def delete_policyflow(self, token, policyflow_id):
        """deletes a neutron policyflow
        @param token: Keystone auth Token
        @param policyflow_id: policyflow id to delete
        """
        request_url = (self.network_service + 'policyflows/%s.json' %
                                                    policyflow_id)

        request_headers = {'Content-type': 'application/json;charset=utf8',
                   'Accept': 'application/json',
                   'x-auth-token': token
                   }
        print "debug", "", "Request URL for delete policy flow request : %r" % request_url
        self.process_request('DELETE',
                     request_url,
                     request_headers,
                     None)
        return
