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
import json as jsonutils
import logging
import netifaces
import os
import signal
import sys
import time

from os.path import abspath
from os.path import dirname

from edit_persistent_rule import EditPersistentRule
from flask import Flask
from flask import jsonify
from flask import request
from fw_module import VyosFWConfig
from log_forwarder import APIHandler as apihandler
from static_ip import StaticIp
from vpn_api_server import VPNHandler as vpnhandler
from vyos_exception import VyosException
from vyos_policy_based_routes import RoutesConfigHandler as routes_handler
from vyos_session.utils import init_logger

sys.path.insert(0, dirname(dirname(abspath(__file__))))

logger = logging.getLogger(__name__)
init_logger(logger)

app = Flask(__name__)

fw_module = None
e = EditPersistentRule()

error_msgs = {
    'unexpected': 'Unexpected VYOS ERROR occurred while %s %s '
}


@app.route('/auth-server-config', methods=['POST'])
def auth_server_config():
    data = jsonutils.loads(request.data)
    f = open("/usr/share/vyos/auth_server.conf", 'w')
    f.write(data['auth_uri'])
    f.write('\n')
    f.write(data['admin_tenant_name'])
    f.write('\n')
    f.write(data['admin_user'])
    f.write('\n')
    f.write(data['admin_password'])
    f.write('\n')
    f.write(data['remote_vpn_role_name'])
    f.write("\n")
    f.write(data['project_id'])
    f.write("\n")

    try:
        host_ip = data['host_mapping'].split()[0] + "/32"
        command = ('grep "new_routers" /var/lib/dhcp3/dhclient_eth0_lease'
                   ' |tail -1| cut -d: -d "=" -f2')
        gateway_ip = os.popen(command).read().strip().strip("'")
        vpnhandler().configure_static_route("set", host_ip, gateway_ip)

    except Exception as ex:
        err = ("Error in adding rvpn route. Reason: %s" % ex)
        logger.error(err)
        return jsonutils.dumps(dict(status=False, reason=err))
    try:
        if data['host_mapping'].split()[1]:
            os.system("sudo chown vyos:users /etc/hosts")
            os.system("sudo echo '\n%s' >> /etc/hosts" % data['host_mapping'])
            os.system("sudo chown root:root /etc/hosts")
    except Exception as e:
        logger.error("Error in writing host mapping in /etc/hosts - %s" % e)

    return jsonutils.dumps(dict(status=True))


@app.route('/create-ipsec-site-conn', methods=['POST'])
def create_ipsec_site_conn():
    """
    Open a "configure" session with vyos
    "Set" all the parameters
    "commit" the changes
    """
    try:
        data = jsonutils.loads(request.data)
        status = vpnhandler().create_ipsec_site_conn(data)
        return jsonutils.dumps(dict(status=status))
    except Exception as ex:
        err = "Error in configuring ipsec_site_conection. Reason: %s" % ex
        logger.error(err)
        return jsonutils.dumps(dict(status=False, reason=err))


@app.route('/create-ipsec-site-tunnel', methods=['POST'])
def create_ipsec_site_tunnel():
    """
    Open a "configure" session with vyos
    "Set" all the parameters
    "commit" the changes
    """
    try:
        tunnel = jsonutils.loads(request.data)
        pcidrs = tunnel['peer_cidrs']
        for pcidr in pcidrs:
            tunnel['peer_cidr'] = pcidr
            status = vpnhandler().create_ipsec_site_tunnel(tunnel)
        return jsonutils.dumps(dict(status=status))
    except Exception as ex:
        err = ("Error in configuring ipsec_site_tunnel. Reason: %s" % ex)
        logger.error(err)
        return jsonutils.dumps(dict(status=False, reason=err))


@app.route('/delete-ipsec-site-tunnel', methods=['DELETE'])
def delete_ipsec_site_tunnel():
    try:
        pcidrs = request.args.get('peer_cidrs')
        peer_address = request.args.get('peer_address')
        local_cidr = request.args.get('local_cidr')
        pcidrs = ast.literal_eval(pcidrs)
        for pcidr in pcidrs:
            tunnel = {}
            tunnel['peer_address'] = peer_address
            tunnel['local_cidr'] = local_cidr
            tunnel['peer_cidr'] = pcidr
            status = vpnhandler().delete_ipsec_site_tunnel(tunnel)
        return jsonutils.dumps(dict(status=status))
    except Exception as ex:
        err = ("Error in deleting ipsec_site_tunnel. Reason: %s" % ex)
        logger.error(err)
        return jsonutils.dumps(dict(status=False, reason=err))


@app.route('/delete-ipsec-site-conn', methods=['DELETE'])
def delete_ipsec_site_conn():
    try:
        peer_address = request.args.get('peer_address')
        status = vpnhandler().delete_ipsec_site_conn(peer_address)
        return jsonutils.dumps(dict(status=status))
    except Exception as ex:
        err = ("Error in deleting ipsec_site_connection. Reason: %s" % ex)
        logger.error(err)
        return jsonutils.dumps(dict(status=False, reason=err))


@app.route('/get-ipsec-site-tunnel-state', methods=['GET'])
def get_ipsec_site_tunnel_state():
    try:
        peer_address = request.args.get('peer_address')
        lcidr = request.args.get('local_cidr')
        pcidr = request.args.get('peer_cidr')
        tunnel = {}
        tunnel['peer_address'] = peer_address
        tunnel['local_cidr'] = lcidr
        tunnel['peer_cidr'] = pcidr
        status, state = vpnhandler().get_ipsec_site_tunnel_state(tunnel)
        return jsonutils.dumps(dict(state=state))
    except Exception as ex:
        err = ("Error in get_ipsec_site_tunnel_state. Reason: %s" % ex)
        logger.error(err)
        return jsonutils.dumps(dict(status=False, reason=err))


@app.route('/create-ssl-vpn-conn', methods=['POST'])
def create_ssl_vpn_conn():
    try:
        data = jsonutils.loads(request.data)
        status = vpnhandler().create_ssl_vpn_conn(data)
        return jsonutils.dumps(dict(status=status))
    except Exception as ex:
        err = ("Error in create_ssl_vpn_connection. Reason: %s" % ex)
        logger.error(err)
        return jsonutils.dumps(dict(status=False, reason=err))


@app.route('/ssl-vpn-push-route', methods=['POST'])
def ssl_vpn_push_route():
    try:
        data = jsonutils.loads(request.data)
        status = vpnhandler().ssl_vpn_push_route(data)
        return jsonutils.dumps(dict(status=status))
    except Exception as ex:
        err = ("Error in ssl_vpn_push_route. Reason: %s" % ex)
        logger.error(err)
        return jsonutils.dumps(dict(status=False, reason=err))


@app.route('/delete-ssl-vpn-conn', methods=['DELETE'])
def delete_ssl_vpn_conn():
    try:
        tunnel_name = request.args.get('tunnel')
        status = vpnhandler().delete_ssl_vpn_conn(tunnel_name)
        return jsonutils.dumps(dict(status=status))
    except Exception as ex:
        err = ("Error in delete_ssl_vpn_conn. Reason: %s" % ex)
        logger.error(err)
        return jsonutils.dumps(dict(status=False, reason=err))


@app.route('/delete-ssl-vpn-route', methods=['DELETE'])
def delete_ssl_vpn_route():
    try:
        route = request.args.get('route')
        status = vpnhandler().delete_ssl_vpn_route(route)
        return jsonutils.dumps(dict(status=status))
    except Exception as ex:
        err = ("Error in delete_ssl_vpn_route. Reason: %s" % ex)
        logger.error(err)
        return jsonutils.dumps(dict(status=False, reason=err))


@app.route('/get-ssl-vpn-conn-state', methods=['GET'])
def get_ssl_vpn_conn_state():
    try:
        tunnel_name = request.args.get('tunnel')
        status, state = vpnhandler().get_ssl_vpn_conn_state(tunnel_name)
        return jsonutils.dumps(dict(status=status, state=state))
    except Exception as ex:
        err = ("Error in get_ssl_vpn_conn_state. Reason: %s" % ex)
        logger.error(err)
        return jsonutils.dumps(dict(status=False, reason=err))


@app.route('/configure-firewall-rule', methods=['POST'])
def configure_firewall_rule():
    global fw_module
    firewall_data = request.data
    try:
        response = fw_module.set_up_rule_on_interfaces(firewall_data)
    except Exception as err:
        try:
            return send_error_response(VyosException(
                    err[0], status_code=err[1], payload=err[2]))
        except IndexError:
            return send_error_response(
                VyosException(str(err), status_code=500,
                              payload=dict(err=error_msgs['unexpected'] % (
                                                'configuring', 'firewall'))))
    else:
        return jsonify(**response)


@app.route('/delete-firewall-rule', methods=['DELETE'])
def delete_firewall_rule():
    global fw_module
    try:
        response = fw_module.reset_firewall(request.data)
    except Exception as err:
        try:
            return send_error_response(VyosException(
                    err[0], status_code=err[1], payload=err[2]))
        except IndexError:
            return send_error_response(
                VyosException(str(err), status_code=500,
                              payload=dict(err=error_msgs['unexpected'] % (
                                                    'deleting', 'firewall'))))
    else:
        return jsonify(**response)


@app.route('/update-firewall-rule', methods=['PUT'])
def update_firewall_rule():
    global fw_module
    try:
        fw_module.reset_firewall(request.data)
        response = fw_module.set_up_rule_on_interfaces(request.data)
    except Exception as err:
        try:
            return send_error_response(VyosException(
                    err[0], status_code=err[1], payload=err[2]))
        except IndexError:
            return send_error_response(
                VyosException(str(err), status_code=500,
                              payload=dict(err=error_msgs['unexpected'] % (
                                                    'updating', 'firewall'))))
    else:
        return jsonify(**response)


@app.route('/add-source-route', methods=['POST'])
def add_source_route():
    try:
        return routes_handler().add_source_route(request.data)
    except Exception as ex:
        err = ("Exception in adding source route. %s" % ex)
        logger.error(err)
        return jsonutils.dumps(dict(status=False, reason=err))


@app.route('/delete-source-route', methods=['DELETE'])
def delete_source_route():
    try:
        return routes_handler().delete_source_route(request.data)
    except Exception as ex:
        err = ("Exception in deleting source route. %s" % ex)
        logger.error(err)
        return jsonutils.dumps(dict(status=False, reason=err))


@app.route('/add-stitching-route', methods=['POST'])
def add_stitching_route():
    try:
        gateway_ip = jsonutils.loads(request.data).get('gateway_ip')
        status = vpnhandler().configure_static_route("set", "0.0.0.0/0",
                                                     gateway_ip)
        return jsonutils.dumps(dict(status=status))
    except Exception as ex:
        err = ("Error in add_stitching_route. Reason: %s" % ex)
        logger.error(err)
        return jsonutils.dumps(dict(status=False, reason=err))


@app.route('/delete-stitching-route', methods=['DELETE'])
def delete_stitching_route():
    try:
        gateway_ip = request.args.get('gateway_ip')
        status = vpnhandler().configure_static_route(
            "delete", "0.0.0.0/0", gateway_ip)
        return jsonutils.dumps(dict(status=status))
    except Exception as ex:
        err = ("Error in delete_stitching_route. Reason: %s" % ex)
        logger.error(err)
        return jsonutils.dumps(dict(status=False, reason=err))


def send_error_response(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response


@app.route('/add_static_ip', methods=['POST'])
def add_static_ip():
    try:
        static_ip_obj = StaticIp()
        data = jsonutils.loads(request.data)
        static_ip_obj.configure(data)
    except Exception as err:
        msg = ("Error adding static IPs for hotplugged interfaces. "
               "Data: %r. Error: %r" % (data, str(err)))
        logger.error(msg)
        return jsonutils.dumps(dict(status=False, reason=msg))
    else:
        return jsonutils.dumps(dict(status=True))


@app.route('/del_static_ip', methods=['DELETE'])
def del_static_ip():
    try:
        static_ip_obj = StaticIp()
        data = jsonutils.loads(request.data)
        static_ip_obj.clear(data)
    except Exception as err:
        msg = ("Error clearing static IPs for hotplugged interfaces. "
               "Data: %r. Error: %r" % (data, str(err)))
        logger.error(msg)
        return jsonutils.dumps(dict(status=False, reason=msg))
    else:
        return jsonutils.dumps(dict(status=True))


@app.route('/add_rule', methods=['POST'])
def add_rule():
    # configuring sshd to listen on management ip address
    ip_addr = get_interface_to_bind()
    fw_module.run_sshd_on_mgmt_ip(ip_addr)

    data = jsonutils.loads(request.data)
    try:
        EditPersistentRule.add(e, data)
    except Exception as err:
        logger.error("Error adding persistent rule %r" % str(err))
        return jsonutils.dumps(dict(status=False))
    else:
        return jsonutils.dumps(dict(status=True))


@app.route('/delete_rule', methods=['DELETE'])
def del_rule():
    data = jsonutils.loads(request.data)
    try:
        EditPersistentRule.delete(e, data)
    except Exception as err:
        logger.error("Error deleting persistent rule %r" % str(err))
        return jsonutils.dumps(dict(status=False))
    else:
        return jsonutils.dumps(dict(status=True))


@app.route('/configure-rsyslog-as-client', methods=['POST'])
def configure_rsyslog_as_client():
    try:
        config_data = jsonutils.loads(request.data)
        status = apihandler().configure_rsyslog_as_client(config_data)
        return jsonutils.dumps(dict(status=status))
    except Exception as ex:
        err = ("Error while conifiguring rsyslog client. Reason: %s" % ex)
        logger.error(err)
        return jsonutils.dumps(dict(status=False, reason=err))


def handler(signum, frame):
    if signum in [2, 3, 9, 11, 15]:
        sys.exit(0)
    else:
        pass


def add_management_pbr():
    command = ('grep "new_routers" /var/lib/dhcp3/dhclient_eth0_lease'
               ' |tail -1| cut -d: -d "=" -f2')
    gateway_ip = os.popen(command).read().strip().strip("'")
    command = ('grep "new_ip_address" /var/lib/dhcp3/dhclient_eth0_lease'
               ' |tail -1| cut -d: -d "=" -f2')
    src_ip = os.popen(command).read().strip().strip("'")
    routes_info = [{'source_cidr': src_ip, 'gateway_ip': gateway_ip}]
    routes_handler().add_source_route(jsonutils.dumps(routes_info))


def getipaddr():
    # This is an assumption that service management will always gets
    # configured on eth0 interface.
    return netifaces.ifaddresses('eth0')[2][0]['addr']


def get_interface_to_bind():
    while True:
        try:
            ip_addr = getipaddr()
            logger.info("Management interface up on - %r " %
                        ''.join([netifaces.ifaddresses('eth0')[17][0][
                            'addr'][:2],
                            netifaces.ifaddresses('eth0')[17][0][
                            'addr'][-2:],
                            netifaces.ifaddresses('eth0')[2][0][
                            'addr'].split('.')[-1]
                        ]))
        except ValueError:
            logger.error("Management Interface not UP")
            time.sleep(5)
        except KeyError:
            logger.error("Management Interface not FOUND")
            time.sleep(5)
        else:
            break
    return ip_addr


def main():
    """

    :type ip_addr: Server listen address
    """
    global fw_module
    fw_module = VyosFWConfig()
    ip_addr = get_interface_to_bind()
    signal.signal(signal.SIGTERM, handler)
    signal.signal(signal.SIGINT, handler)
    app.run(ip_addr, 8888)
    logger.info("VYOS Agent started ..... ")


if __name__ == '__main__':
    main()