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

import sys
import os
import json
import signal
import logging
import ast
import time
from os.path import abspath, dirname

import netifaces

sys.path.insert(0, dirname(dirname(abspath(__file__))))
from vyos_session.utils import init_logger
from oc_fw_module import OCFWConfigClass
from edit_persistent_rule import EditPersistentRule
from static_ip import StaticIp
from flask import Flask, request
from os.path import abspath, dirname
from vpn_api_server import VPNHandler as vpnhandler
from vyos_policy_based_routes import RoutesConfigHandler as routes_handler
from ha_config import VYOSHAConfig
from vyos_exception import OCException
from flask import jsonify
from log_forwarder import APIHandler as apihandler
from stats_parser import APIHandler as stats_apihandler
# sys.path.insert(0, dirname(dirname(abspath(__file__))))
# sys.path.insert(0, (abspath(__file__)))

logger = logging.getLogger(__name__)
init_logger(logger)

app = Flask(__name__)

oc_fw_module = None
e = EditPersistentRule()

error_msgs = {
    'unexpected': 'Unexpected VYOS ERROR occurred while %s %s '
}


@app.route('/auth-server-config', methods=['POST'])
def auth_server_config():
    data = json.loads(request.data)
    f = open("/usr/share/vyos-oc/auth_server.conf", 'w')
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
        host_ip = data['host_mapping'].split()[0]+"/32"
        command = 'grep "new_routers" /var/lib/dhcp3/dhclient_eth0_lease |tail -1| cut -d: -d "=" -f2'
        gateway_ip = os.popen(command).read().strip().strip("'")
        status = vpnhandler().configure_static_route("set", host_ip, gateway_ip)

    except Exception as ex:
        err = ("Error in adding rvpn route. Reason: %s" % ex)
        logger.error(err)
        return json.dumps(dict(status=False, reason=err))
    try:
        if data['host_mapping'].split()[1]:
            os.system("sudo chown vyos:users /etc/hosts")
            os.system("sudo echo '\n%s' >> /etc/hosts" % data['host_mapping'])
            os.system("sudo chown root:root /etc/hosts")
            #with open('/etc/hosts', 'a') as hosts:
            #    hosts.write(data['host_mapping'])
    except Exception as e:
        logger.error("Error in writing host mapping in /etc/hosts - %s" % e)

    return json.dumps(dict(status=True))


@app.route('/create-ipsec-site-conn', methods=['POST'])
def create_ipsec_site_conn():
    """
    Open a "configure" session with vyos
    "Set" all the parameters
    "commit" the changes
    """
    try:
        data = json.loads(request.data)
        status = vpnhandler().create_ipsec_site_conn(data)
        return json.dumps(dict(status=status))
    except Exception as ex:
        err = "Error in configuring ipsec_site_conection. Reason: %s" % ex
        logger.error(err)
        return json.dumps(dict(status=False, reason=err))


@app.route('/create-ipsec-site-tunnel', methods=['POST'])
def create_ipsec_site_tunnel():
    """
    Open a "configure" session with vyos
    "Set" all the parameters
    "commit" the changes
    """
    try:
        tunnel = json.loads(request.data)
        pcidrs = tunnel['peer_cidrs']
        for pcidr in pcidrs:
            tunnel['peer_cidr'] = pcidr
            status = vpnhandler().create_ipsec_site_tunnel(tunnel)
        return json.dumps(dict(status=status))
    except Exception as ex:
        err = ("Error in configuring ipsec_site_tunnel. Reason: %s" % ex)
        logger.error(err)
        return json.dumps(dict(status=False, reason=err))


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
        return json.dumps(dict(status=status))
    except Exception as ex:
        err = ("Error in deleting ipsec_site_tunnel. Reason: %s" % ex)
        logger.error(err)
        return json.dumps(dict(status=False, reason=err))


@app.route('/delete-ipsec-site-conn', methods=['DELETE'])
def delete_ipsec_site_conn():
    try:
        peer_address = request.args.get('peer_address')
        status = vpnhandler().delete_ipsec_site_conn(peer_address)
        return json.dumps(dict(status=status))
    except Exception as ex:
        err = ("Error in deleting ipsec_site_connection. Reason: %s" % ex)
        logger.error(err)
        return json.dumps(dict(status=False, reason=err))


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
        return json.dumps(dict(state=state))
    except Exception as ex:
        err = ("Error in get_ipsec_site_tunnel_state. Reason: %s" % ex)
        logger.error(err)
        return json.dumps(dict(status=False, reason=err))


@app.route('/create-ssl-vpn-conn', methods=['POST'])
def create_ssl_vpn_conn():
    try:
        data = json.loads(request.data)
        status = vpnhandler().create_ssl_vpn_conn(data)
        return json.dumps(dict(status=status))
    except Exception as ex:
        err = ("Error in create_ssl_vpn_connection. Reason: %s" % ex)
        logger.error(err)
        return json.dumps(dict(status=False, reason=err))


@app.route('/ssl-vpn-push-route', methods=['POST'])
def ssl_vpn_push_route():
    try:
        data = json.loads(request.data)
        status = vpnhandler().ssl_vpn_push_route(data)
        return json.dumps(dict(status=status))
    except Exception as ex:
        err = ("Error in ssl_vpn_push_route. Reason: %s" % ex)
        logger.error(err)
        return json.dumps(dict(status=False, reason=err))


@app.route('/delete-ssl-vpn-conn', methods=['DELETE'])
def delete_ssl_vpn_conn():
    try:
        tunnel_name = request.args.get('tunnel')
        status = vpnhandler().delete_ssl_vpn_conn(tunnel_name)
        return json.dumps(dict(status=status))
    except Exception as ex:
        err = ("Error in delete_ssl_vpn_conn. Reason: %s" % ex)
        logger.error(err)
        return json.dumps(dict(status=False, reason=err))


@app.route('/delete-ssl-vpn-route', methods=['DELETE'])
def delete_ssl_vpn_route():
    try:
        route = request.args.get('route')
        status = vpnhandler().delete_ssl_vpn_route(route)
        return json.dumps(dict(status=status))
    except Exception as ex:
        err = ("Error in delete_ssl_vpn_route. Reason: %s" % ex)
        logger.error(err)
        return json.dumps(dict(status=False, reason=err))


@app.route('/get-ssl-vpn-conn-state', methods=['GET'])
def get_ssl_vpn_conn_state():
    try:
        tunnel_name = request.args.get('tunnel')
        status, state = vpnhandler().get_ssl_vpn_conn_state(tunnel_name)
        return json.dumps(dict(status=status, state=state))
    except Exception as ex:
        err = ("Error in get_ssl_vpn_conn_state. Reason: %s" % ex)
        logger.error(err)
        return json.dumps(dict(status=False, reason=err))


@app.route('/configure-firewall-rule', methods=['POST'])
def configure_firewall_rule():
    global oc_fw_module
    firewall_data = request.data
    try:
        response = oc_fw_module.set_up_rule_on_interfaces(firewall_data)
    except Exception as err:
        try:
            return send_error_response(OCException(err[0], status_code=err[1],
                                                   payload=err[2]))
        except IndexError:
            return send_error_response(
                OCException(str(err), status_code=500,
                            payload=dict(err=error_msgs['unexpected'] % (
                                'configuring', 'firewall'))))
    else:
        return jsonify(**response)


@app.route('/delete-firewall-rule', methods=['DELETE'])
def delete_firewall_rule():
    global oc_fw_module
    try:
        response = oc_fw_module.reset_firewall(request.data)
    except Exception as err:
        try:
            return send_error_response(OCException(err[0], status_code=err[1],
                                                   payload=err[2]))
        except IndexError:
            return send_error_response(
                OCException(str(err), status_code=500,
                            payload=dict(err=error_msgs['unexpected'] % (
                                'deleting', 'firewall'))))
    else:
        return jsonify(**response)


@app.route('/update-firewall-rule', methods=['PUT'])
def update_firewall_rule():
    global oc_fw_module
    try:
        oc_fw_module.reset_firewall(request.data)
        response = oc_fw_module.set_up_rule_on_interfaces(request.data)
    except Exception as err:
        try:
            return send_error_response(OCException(err[0], status_code=err[1],
                                                   payload=err[2]))
        except IndexError:
            return send_error_response(
                OCException(str(err), status_code=500,
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
        return json.dumps(dict(status=False, reason=err))


@app.route('/delete-source-route', methods=['DELETE'])
def delete_source_route():
    try:
        return routes_handler().delete_source_route(request.data)
    except Exception as ex:
        err = ("Exception in deleting source route. %s" % ex)
        logger.error(err)
        return json.dumps(dict(status=False, reason=err))


@app.route('/add-stitching-route', methods=['POST'])
def add_stitching_route():
    try:
        gateway_ip = json.loads(request.data).get('gateway_ip')
        status = vpnhandler().configure_static_route("set", "0.0.0.0/0", gateway_ip)
        return json.dumps(dict(status=status))
    except Exception as ex:
        err = ("Error in add_stitching_route. Reason: %s" % ex)
        logger.error(err)
        return json.dumps(dict(status=False, reason=err))


@app.route('/delete-stitching-route', methods=['DELETE'])
def delete_stitching_route():
    try:
        gateway_ip = request.args.get('gateway_ip')
        status = vpnhandler().configure_static_route(
                    "delete", "0.0.0.0/0", gateway_ip)
        return json.dumps(dict(status=status))
    except Exception as ex:
        err = ("Error in delete_stitching_route. Reason: %s" % ex)
        logger.error(err)
        return json.dumps(dict(status=False, reason=err))


@app.route('/configure_conntrack_sync', methods=['POST'])
def configure_conntrack_sync():
    global vyos_ha_config
    try:
        response = vyos_ha_config.configure_conntrack_sync(request.data)
    except Exception as err:
        # This flask version has issue in implicit way of registering
        # error handler.
        try:
            return send_error_response(OCException(err[0], status_code=err[1],
                                                   payload=err[2]))
        except IndexError:
            return send_error_response(
                OCException(str(err), status_code=500,
                            payload=dict(err=error_msgs['unexpected'] % (
                                'configuring', 'conntrack sync'))))
    else:
        return jsonify(**response)


@app.route('/configure_interface_ha', methods=['POST'])
def configure_interface_ha():
    global vyos_ha_config
    try:
        response = vyos_ha_config.set_vrrp_for_interface(request.data)
    except Exception as err:
        try:
            return send_error_response(OCException(err[0], status_code=err[1],
                                                   payload=err[2]))
        except IndexError:
            return send_error_response(
                OCException(str(err), status_code=500,
                            payload=dict(
                                err=error_msgs['unexpected'] % (
                                    'configuring', 'HA for the interface'))))
    else:
        return jsonify(**response)


@app.route('/delete_vrrp', methods=['DELETE'])
def delete_vrrp():
    global vyos_ha_config
    try:
        response = vyos_ha_config.delete_vrrp(request.data)
    except Exception as err:
        try:
            return send_error_response(OCException(err[0], status_code=err[1],
                                                   payload=err[2]))
        except IndexError:
            return send_error_response(
                OCException(str(err), status_code=500,
                            payload=dict(err=error_msgs['unexpected'] % (
                                'deleting', 'VRRP'))))
    else:
        return jsonify(**response)


# @app.errorhandler(OCException)
def send_error_response(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response


@app.route('/add_static_ip', methods=['POST'])
def add_static_ip():
    try:
        static_ip_obj = StaticIp()
        data = json.loads(request.data)
        static_ip_obj.configure(data)
    except Exception as err:
        msg = ("Error adding static IPs for hotplugged interfaces. "
               "Data: %r. Error: %r" % (data, str(err)))
        logger.error(msg)
        return json.dumps(dict(status=False, reason=msg))
    else:
        return json.dumps(dict(status=True))


@app.route('/del_static_ip', methods=['DELETE'])
def del_static_ip():
    try:
        static_ip_obj = StaticIp()
        data = json.loads(request.data)
        static_ip_obj.clear(data)
    except Exception as err:
        msg = ("Error clearing static IPs for hotplugged interfaces. "
               "Data: %r. Error: %r" % (data, str(err)))
        logger.error(msg)
        return json.dumps(dict(status=False, reason=msg))
    else:
        return json.dumps(dict(status=True))


@app.route('/add_rule', methods=['POST'])
def add_rule():
    # configuring sshd to listen on management ip address
    ip_addr = get_interface_to_bind()
    oc_fw_module.run_sshd_on_mgmt_ip(ip_addr)

    data = json.loads(request.data)
    try:
        EditPersistentRule.add(e, data)
    except Exception as err:
        logger.error("Error adding persistent rule %r" % str(err))
        return json.dumps(dict(status=False))
    else:
        return json.dumps(dict(status=True))


@app.route('/delete_rule', methods=['DELETE'])
def del_rule():
    data = json.loads(request.data)
    try:
        EditPersistentRule.delete(e, data)
    except Exception as err:
        logger.error("Error deleting persistent rule %r" % str(err))
        return json.dumps(dict(status=False))
    else:
        return json.dumps(dict(status=True))


@app.route('/configure-rsyslog-as-client', methods=['POST'])
def configure_rsyslog_as_client():
    try:
        config_data = json.loads(request.data)
        status = apihandler().configure_rsyslog_as_client(config_data)
        return json.dumps(dict(status=status))
    except Exception as ex:
        err = ("Error while conifiguring rsyslog client. Reason: %s" % ex)
        logger.error(err)
        return json.dumps(dict(status=False, reason=err))

@app.route('/get-fw-stats', methods=['GET'])
def get_fw_stats():
    try:
        mac_address = request.args.get('mac_address')
        fw_stats = stats_apihandler().get_fw_stats(mac_address)
        return json.dumps(dict(stats=fw_stats))
    except Exception as ex:
        err = ("Error while getting firewall stats. Reason: %s" % ex)
        logger.error(err)
        return json.dumps(dict(status=False, reason=err))

@app.route('/get-vpn-stats', methods=['GET'])
def get_vpn_stats():
    try:
        vpn_stats = stats_apihandler().get_vpn_stats()
        return json.dumps(dict(stats=vpn_stats))
    except Exception as ex:
        err = ("Error while getting vpn stats. Reason: %s" % ex)
        logger.error(err)
        return json.dumps(dict(status=False, reason=err))


def handler(signum, frame):
    if signum in [2, 3, 9, 11, 15]:
        sys.exit(0)
    else:
        pass


def add_management_pbr():
    command = 'grep "new_routers" /var/lib/dhcp3/dhclient_eth0_lease |tail -1| cut -d: -d "=" -f2'
    gateway_ip = os.popen(command).read().strip().strip("'")
    command = 'grep "new_ip_address" /var/lib/dhcp3/dhclient_eth0_lease |tail -1| cut -d: -d "=" -f2'
    src_ip = os.popen(command).read().strip().strip("'")
    routes_info = [{'source_cidr': src_ip, 'gateway_ip': gateway_ip}]
    routes_handler().add_source_route(json.dumps(routes_info))


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
    global oc_fw_module, vyos_ha_config
    oc_fw_module = OCFWConfigClass()
    vyos_ha_config = VYOSHAConfig()
    ip_addr = get_interface_to_bind()
    signal.signal(signal.SIGTERM, handler)
    signal.signal(signal.SIGINT, handler)
    app.run(ip_addr, 8888)
    logger.info("VYOS Agent started ..... ")


if __name__ == '__main__':
    main()

