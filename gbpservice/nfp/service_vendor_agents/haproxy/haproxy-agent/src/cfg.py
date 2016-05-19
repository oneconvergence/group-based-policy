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
import commands
import netifaces
import sys, traceback

STATS_MAP = {
    constants.STATS_ACTIVE_CONNECTIONS:'scur',
    constants.STATS_MAX_CONNECTIONS:'smax',
    constants.STATS_CURRENT_SESSIONS:'scur',
    constants.STATS_MAX_SESSIONS:'smax',
    constants.STATS_TOTAL_CONNECTIONS:'stot',
    constants.STATS_TOTAL_SESSIONS:'stot',
    constants.STATS_IN_BYTES:'bin',
    constants.STATS_OUT_BYTES:'bout',
    constants.STATS_CONNECTION_ERRORS:'econ',
    constants.STATS_RESPONSE_ERRORS:'eresp'}


def dump_bool(prefix, key, out):
    out.write(prefix
              + ' ' + key)


def dump_list(prefix, l, out):
    out.write(prefix
              + ' ' + ' '.join(l))


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


def save_config(logical_config, config_file):
    out = open(config_file, "w")

    if 'global' in logical_config:
        out.write('\nglobal')
        dump_dict('\n ', logical_config['global'], out)
    if 'defaults' in logical_config:
        out.write('\ndefaults')
        dump_dict('\n ', logical_config['defaults'], out)
    if 'listen' in logical_config:
        for k, v in logical_config['listen'].iteritems():
            out.write('\nlisten %s' % k)
            dump_dict('\n ', v, out)
    if 'frontends' in logical_config:
        for k, v in logical_config['frontends'].iteritems():
            out.write('\nfrontend %s' % k)
            dump_dict('\n ', v, out)
    if 'backends' in logical_config:
        for k, v in logical_config['backends'].iteritems():
            out.write('\nbackend %s' % k)
            dump_dict('\n ', v, out)

    out.write('\n')
    out.close()



def _get_server_dict(server_cfg_str):
    server_dict = {}
    server_cfg_line = server_cfg_str.split('server ')[1].strip().split(' ')
    server_id = server_cfg_line.pop(0)
    server_dict[server_id] = []
    server_dict[server_id].append(server_cfg_line[0])
    server_dict[server_id].append(' '.join([server_cfg_line[1],
                                            server_cfg_line[2]]))
    server_dict[server_id].append(' '.join(server_cfg_line[3:]))
    return server_dict

def _get_backend_dict(backend_cfg_lines):
    backend = {
            'mode': '',
            'balance': '',
            'option': {},
            'timeout': {},
            'server': {}
    }
    for cfg_str in backend_cfg_lines:
        cfg_line = cfg_str.strip().split(' ')
        backend_cfg_key = cfg_line[0]
        backend_cfg_value = cfg_line[1]

        if 'backend' in cfg_str:
            backend_id = backend_cfg_value
            continue

        if 'http-check' in cfg_str:
            backend_cfg_key = 'http-check expect'
            backend_cfg_value = cfg_str.split('http-check expect')[1].strip()

        if 'option' in cfg_str:
            if 'forwardfor' in cfg_str:
                backend['option']['forwardfor'] = True
            if 'httpchk' in cfg_str:
                option_values = cfg_line[1:]
                backend['option'][option_values[0]] = ' '.join(option_values[1:])
        elif 'timeout' in cfg_str:
            timeout_values = cfg_line[1:]
            backend['timeout'][timeout_values[0]] = ' '.join(timeout_values[1:])
        elif 'server' in cfg_str:
            backend['server'].update(_get_server_dict(cfg_str))
        else:
            backend[backend_cfg_key] = backend_cfg_value
    return {backend_id: backend}

def _get_frontend_dict(backend_cfg_lines):
    frontend = {
            'mode': '',
            'bind': '',
            'option': {},
            'default_backend': '',
            '#provider_interface_mac': 'None',
            '#standby_provider_interface_mac': 'None'
    }
    for cfg_str in backend_cfg_lines:
        cfg_line = cfg_str.strip().split(' ')
        backend_cfg_key = cfg_line[0]
        backend_cfg_value = cfg_line[1]
        if 'frontend frnt:' in cfg_str:
            frontend_id = backend_cfg_value
            continue
        if 'option' in cfg_str:
            if 'forwardfor' in cfg_str:
                frontend['option']['forwardfor'] = True
            if 'tcplog' in cfg_str:
                frontend['option']['tcplog'] = True
            if 'httplog' in cfg_str:
                frontend['option']['httplog'] = True
        else:
            frontend[backend_cfg_key] = backend_cfg_value
    return {frontend_id: frontend}

def _get_existing_frontends(cfg_lines):
    frontends = {}
    for index, line in enumerate(cfg_lines):
        if 'frontend frnt:' in line:
            frontend_cfg_lines = []
            frontend_cfg_lines.append(line)
            for frnt_line in cfg_lines[index+1:]:
                print frnt_line
                if 'default_backend' not in frnt_line and (
                    'frontend frnt:' in frnt_line or 'backend bck:' in frnt_line):
                    break
                frontend_cfg_lines.append(frnt_line)
            frontends.update(_get_frontend_dict(frontend_cfg_lines))
    print frontends
    return frontends

def _get_existing_backends(cfg_lines):
    backends = {}
    for index, line in enumerate(cfg_lines):
        if ('default_backend bck:' not in line and 'backend bck:' in line):
            backend_cfg_lines = []
            backend_cfg_lines.append(line)
            for bck_line in cfg_lines[index+1:]:
                if 'backend bck:' in bck_line:
                    break
                backend_cfg_lines.append(bck_line)
            backends.update(_get_backend_dict(backend_cfg_lines))
    return backends

def get_existing_config(config_file):
    with open(config_file, "r") as f:
        cfg_str_lines = f.readlines()
    try:
        frontends = _get_existing_frontends(cfg_str_lines)
        print 'frontends = ', frontends
        backends = _get_existing_backends(cfg_str_lines)
        print 'backends = ', backends
    except Exception, e:
        print 'exception'
        ex_type, ex, tb = sys.exc_info()
        traceback.print_tb(tb)
    return dict(frontends=frontends, backends=backends)

def get_existing_frontends(config_file):
    with open(config_file, "r") as f:
        cfg_str_lines = f.readlines()
    try:
        frontends = _get_existing_frontends(cfg_str_lines)
    except Exception, e:
        ex_type, ex, tb = sys.exc_info()
        traceback.print_tb(tb)
    return frontends

def update_sshd_listen_ip(ip_addr):
    sshd_config_file = "/etc/ssh/sshd_config"
    #ip_addr = get_interface_to_bind()
    cmd1 = "sed -i '/^ListenAddress/d' %s" % sshd_config_file
    status, output = commands.getstatusoutput(cmd1)
    print("command : %s, status: %s, output: %s" % (cmd1, status, output))
    cmd2 = "echo \"ListenAddress %s\" >> %s" % (ip_addr, sshd_config_file)
    status, output = commands.getstatusoutput(cmd2)
    print("command : %s, status: %s, output: %s" % (cmd2, status, output))
    cmd3 = "service ssh restart"
    status, output = commands.getstatusoutput(cmd3)
    print("command : %s, status: %s, output: %s" % (cmd3, status, output))


def getipaddr():
    # This is an assumption that service management will always gets
    # configured on eth0 interface.
    return netifaces.ifaddresses('eth0')[2][0]['addr']


def get_interface_to_bind():
    while True:
        try:
            ip_addr = getipaddr()
        except ValueError:
            print "Management Interface not UP"
            time.sleep(5)
        except KeyError:
            print "Management Interface not FOUND"
            time.sleep(5)
        else:
            break
    return ip_addr


if __name__ == '__main__':
    """
    conf = {
        "global": {
            "daemon": True,
            "user": "nobody",
            "group": "nogroup",
            "log": {
                "/dev/log": {
                    "local0": [
                    ],
                    "local1": [
                        "notice"
                    ]
                }
            }
        },
        "defaults": {
            "log": "global",
            "retries": 3,
            "option": {
                "redispatch": True
            },
            "timeout": {
                "connect": 5000,
                "client": 50000,
                "server": 50000
            },
        },
        "listen": {
            "stats *:1936": {
                "stats": {
                    "enable": True,
                    "uri": "/",
                    "hide-version": True,
                    "auth": "admin:haproxy"
                },
                "mode": "http"
            }
        },
        "frontends": {
            "frnt:a3b4f148-8b24-4281-95ab-5cb7c1e7fa7a": {
                "bind": "10.0.0.10:80",
                "mode": "http",
                "default_backend": "bck:5ec664ae-3bc0-4018-8252-d314526cb79e",
                "option": {
                    "forwardfor": True,
                    "tcplog": True
                }
            },
            "frnt:b3b4f148-8b24-4281-95ab-5cb7c1e7fa7a": {
                "bind": "10.0.0.11:80",
                "mode": "http",
                "default_backend": "bck:6ec664ae-3bc0-4018-8252-d314526cb79e",
                "option": {
                    "forwardfor": True,
                    "tcplog": True
                }
            }
        },
        "backends": {
            "bck:5ec664ae-3bc0-4018-8252-d314526cb79e": {
                "mode": "http",
                "balance": "roundrobin",
                "option": {
                    "forwardfor": True,
                    "httpchk": "GET /"
                },
                "timeout": {
                    "check": "10s"
                },
                "http-check expect": "rstatus 200",
                "server": {
                    "srvr:4883787e-4ed7-45dc-8860-cd8519695a5d": [
                        "10.0.0.11:80",
                        "weight 1",
                        "check inter 20s fall 3"
                    ],
                    "srvr:562d9d18-8b3e-46c5-a3ad-e6f624a112ac": [
                        "10.0.0.12:80",
                        "weight 1",
                        "check inter 20s fall 3"
                    ]
                }
            },
            "bck:6ec664ae-3bc0-4018-8252-d314526cb79e": {
                "mode": "http",
                "balance": "roundrobin",
                "option": {
                    "forwardfor": True,
                    "httpchk": "GET /"
                },
                "timeout": {
                    "check": "10s"
                },
                "http-check expect": "rstatus 200",
                "server": {
                    "srvr:5883787e-4ed7-45dc-8860-cd8519695a5d": [
                        "10.0.0.12:80",
                        "weight 1",
                        "check inter 20s fall 3"
                    ],
                    "srvr:662d9d18-8b3e-46c5-a3ad-e6f624a112ac": [
                        "10.0.0.13:80",
                        "weight 1",
                        "check inter 20s fall 3"
                    ]
                }
            }
        }
    }

    save_config(conf, "./haproxy.conf")
    """
