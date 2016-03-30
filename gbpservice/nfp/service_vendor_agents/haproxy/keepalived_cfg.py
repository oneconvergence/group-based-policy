# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2011 OpenStack Foundation.
# Copyright 2012, Red Hat, Inc.
#
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


import constants
import sys, traceback

conf = {
    "vrrp_script": {
        "check_haproxy": {
            "script": '/etc/keepalived/checkhealth.sh',
            "interval": '2',
            "weight": '2',
            "fall": '2',
            "rise": '4'
            }
    },
    "vrrp_instance": {
        "LB_1": {
            "interface": "",
            "state": "BACKUP",
            "virtual_router_id": '51',
            "priority": '',
            "unicast_src_ip": '',
            "unicast_peer": [],
            "virtual_ipaddress": [],
            "track_script": [],
            "track_interface": [],
            "notify_master": '\"/etc/keepalived/notify_state.sh MASTER\"',
            "notify_backup": '\"/etc/keepalived/notify_state.sh BACKUP\"',
            "notify_fault": '\"/etc/keepalived/notify_state.sh FAULT\"'
            }
    }
}

def dump_bool(prefix, key, out):
    out.write(prefix
              + ' ' + key)


def dump_list(prefix, l, out):
    for entry in l:
        out.write(prefix + entry)


def dump_dict(prefix, d, out):
    for k in d:
        v = d[k]
        if type(v) is bool:
            dump_bool(prefix, k, out)
        elif type(v) is list:
            dump_list(prefix
                      + ' ' + k,
                      v, out)
        elif type(v) is dict:
            dump_dict(prefix
                      + ' ' + k,
                      v, out)
        else:
            out.write(prefix
                      + ' ' + k
                      + ' ' + str(v))

def dump_values(prefix, d, out):
    for k in d:
        v = d[k]
        if k == 'unicast_peer':
            out.write('\n unicast_peer {')
            dump_list('\n  ', v, out)
            out.write('\n }')
        elif k == 'virtual_ipaddress':
            out.write('\n virtual_ipaddress {')
            dump_list('\n  ', v, out)
            out.write('\n }')
        elif k == 'track_interface':
            out.write('\n track_interface {')
            dump_list('\n  ', v, out)
            out.write('\n }')
        elif k == 'track_script':
            out.write('\n track_script {')
            dump_list('\n  ', v, out)
            out.write('\n }')
        else:
            dump_dict('\n', {k: v}, out)


def save_config(logical_config, config_file):
    out = open(config_file, "w")

    if 'vrrp_script' in logical_config:
        for k, v in logical_config['vrrp_script'].iteritems():
            out.write('\nvrrp_script %s {' % k)
            dump_dict('\n ', v, out)
            out.write('\n}\n')

    if 'vrrp_instance' in logical_config:
        for k, v in logical_config['vrrp_instance'].iteritems():
            out.write('\nvrrp_instance %s {' % k)
            dump_values('\n ', v, out)
            out.write('\n}')
    out.write('\n')
    out.close()

def _get_interfaces_list(vips_list, mgmt_interface):
    interfaces_list = []
    interfaces_list.append(mgmt_interface)
    for vip_str in vips_list:
        interface = vip_str.split('dev ')[1].strip()
        interfaces_list.append(interface)
    return interfaces_list

def get_virtual_ipaddress(vip_ip, interface):
        return '%s/32 dev %s' % (vip_ip, interface)

def _calculate_virtual_ipaddress(vip_str, vip_info):
    vip_ip = vip_str.split('/32')[0]
    if vip_ip in vip_info:
        interface = vip_info[vip_ip][1]
        new_vip_str = get_virtual_ipaddress(vip_ip, interface)
    return new_vip_str

def _get_resource_value(cfg_str_lines, res_name):
    for cfg_str in cfg_str_lines:
        if res_name in cfg_str:
            cfg_line = cfg_str.strip().split(res_name)
            if len(cfg_line) == 2:
                res_value = cfg_line[1].strip()
                break
    return res_value

def _get_resources_list(cfg_str_lines, res_name, vip_info):
    res_list = []
    for index, cfg_str in enumerate(cfg_str_lines):
        if res_name in cfg_str:
            for line in cfg_str_lines[index+1:]:    # index+1 to skip '{'
                if '}' in line:
                    break
                value = line.strip()
                if res_name == 'virtual_ipaddress':
                    # To solve interface reordering on reboot issue.
                    value = _calculate_virtual_ipaddress(value, vip_info)
                res_list.append(value)
    return res_list

def update_existing_config(logical_config, config_file, vip_info):
    vrrp_instance = logical_config["vrrp_instance"]['LB_1']
    with open(config_file, "r") as f:
        cfg_str_lines = f.readlines()
    try:
        for res_name in ['interface', 'priority', 'unicast_src_ip']:
            res_value = _get_resource_value(cfg_str_lines, res_name)
            vrrp_instance[res_name] = res_value

        for res_name in ['unicast_peer', 'virtual_ipaddress',
                         'track_script', 'track_interface']:
            if res_name != 'track_interface':
                res_value = _get_resources_list(cfg_str_lines, res_name, vip_info)
            else:
                vips_list = vrrp_instance['virtual_ipaddress']
                res_value = _get_interfaces_list(vips_list,
                                                 vrrp_instance['interface'])
            vrrp_instance[res_name] = res_value
    except Exception, e:
        ex_type, ex, tb = sys.exc_info()
        traceback.print_tb(tb)
    try:
        save_config(logical_config, config_file)
    except Exception, e:
        ex_type, ex, tb = sys.exc_info()
        traceback.print_tb(tb)

