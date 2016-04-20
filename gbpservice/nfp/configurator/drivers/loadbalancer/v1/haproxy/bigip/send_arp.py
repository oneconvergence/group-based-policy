
#Before running this script do the following:
#Launch Big IP service, provide fixed IP and floating ip as arguments
#In BigIQ Add  StrictHostKeyChecking=no in /root/.ssh/config
#Make sure paramiko and pexpect are installed on the node where this script is triggered

import sys
import os
import re
import commands
import json
import subprocess
import time
import paramiko
import ConfigParser
from oslo_log import log as logging
#from license_management.key_management import *

LOG = logging.getLogger(__name__)

def ping_parse(ping_op):
    LOG.info( "Evaluating Ping Result...")
    info = ping_op.split("\n")
    index = 0
    for i in range(len(info)):
        if "ping statistics" in info[i]:
            index = i
            break
        if "unknown host" in info[i]:
            index = -1
            break
    if index == -1:
        return info
    elif i > 0:
        ping_fields = info[i + 1].split(",")
        if "errors" not in ping_fields[2]:
            ping_dict = {'Transmitted': ping_fields[0], 'Received': ping_fields[
                1], 'Loss': ping_fields[2], 'Time': ping_fields[3]}

            return ping_dict
        else:
            ping_dict = {'Transmitted': ping_fields[0], 'Received': ping_fields[
                1], 'Loss': ping_fields[3], 'Time': ping_fields[4]}

            return ping_dict
    else:
        return info

def pingSend(dstIP):
    command = "ping " + dstIP + " -c 3"
    LOG.info( command + ".Sending Ping Packets...")
    status, output = commands.getstatusoutput(command)
    result = ping_parse(output)
    return result


def create_ssh_object(hostIP, user, passwd, sg=0):
    try:
        if sg == 1:
            i = 4
        else:
            i = 21
        flag = False
        #ping the hostIP before creating the sshObj for it.
        for attempt in range(1, i):
            ping_dict = pingSend(hostIP)
            LOG.info( "ping_dict: %s" % ping_dict)

            if "Loss" in ping_dict.keys():
                if "100%" in ping_dict['Loss']:
                    LOG.info( "Ping failed at attempt: %d. So retrying" % attempt)

                    flag = True
                    #time.sleep(15)
                else:
                    LOG.info( "Ping to ip: %s is successful." % hostIP)

                    flag = True
                    break
            else:
                LOG.info( "Problem while parsing the ping output.")


        if flag == False:
            LOG.info( "Several times ping to the hostIP: %s failed. So exiting"\
             % hostIP)
            flag = True
        for i in range(0,5):
            try:
                ssh = paramiko.SSHClient()
#               LOG.info( "In create_ssh_object function : %s, %s, %s, %s" %(hostIP, user, passwd, ssh))
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                #time.sleep(15)
                ssh.connect(hostIP, username=user, password=passwd, timeout=60)
                #time.sleep(15)
                return ssh
            except Exception as e:
                time.sleep(5)
                LOG.info( "We had an authentication exception! %s" %e)
                shell = None

    except Exception as e:

        LOG.info( "We had an authentication exception! %s" %e)
        shell = None

def run_cmd_on_server(sshObj, command):
    LOG.info( "Executing command : %s" %command)
    stdin, stdout, stderr = sshObj.exec_command(command)
    #time.sleep(10)
    stdin.flush()
    data = stdout.read()
    return data.rstrip(os.linesep)

def get_intf_name(ssh_obj_ip, provider_mac):
    intf_mac = '_'.join(provider_mac.split(':'))
    intf_info = run_cmd_on_server(ssh_obj_ip,
                                 "cat /etc/ethmap | grep %s" % intf_mac)
    intf_name = intf_info.split()[0]
    return intf_name

def send_garp(fip, vip_ip, provider_mac):
    ssh_obj_ip= create_ssh_object(fip, "root", "default")
    intf_name = get_intf_name(ssh_obj_ip, provider_mac)
    run_cmd_on_server(ssh_obj_ip, "python /home/admin/send_arp.py -i 1 -r 1 -p a %s %s %s ff:ff:ff:ff:ff:ff 255.255.255.255"  % (
                                        intf_name, vip_ip, provider_mac))

if __name__ == '__main__':
    send_garp('1.203.1.87', '120.0.0.223', 'fa:16:3e:65:8d:51')
    print 'sending'
