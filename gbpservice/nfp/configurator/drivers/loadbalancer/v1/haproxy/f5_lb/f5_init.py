
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
import f5_liciense_driver
from f5_constants import *
import ConfigParser
#from neutron.openstack.common import log as logging
from oslo_log import log as logging
from license_management.key_management import *

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


def is_vm_license(ssh_obj):
    license_output = run_cmd_on_server(ssh_obj, "tmsh show /sys license")
    if re.search("Licensed On", license_output):
        LOG.info( "BIG IP VM iS already licensed." )
        return True
    else:
        return False

def f5_license(fip, ssh_obj):
    # Check whether BigIP VM is licensed. If True then Skip the license part.
    if is_vm_license(ssh_obj):
        return 0

    key_used_count = 0
    try:
        KEY = getKey()
        while key_used_count < 4:
            ## If No Valid keys are left in database.
            if KEY==-1:
                LOG.info( "*****************NO KEYS ARE LEFT IN DATABASE.***********************")
                return -1

            json_result = f5_liciense_driver.f5_install_license(MODULE_PATH, \
	                    "server="+str(fip)+" key="+KEY+" user="+USER+" password="+PASSWORD)
            LOG.info( str(json_result))
            if json_result["failed"]==True:
                ## Key is already used update the status to True.
                updateKey(KEY, True)           
                key_used_count = key_used_count + 1
                KEY = getKey()
                continue
            else:
                break
            
        return 0
    except Exception as e:
        LOG.info( "**********************Exception Occured While Licensing**********************")
        LOG.info( "Exception")
	LOG.info( str(e))
	updateKey(KEY, False)
	return -1

def executeCurl(api):
    try:
        status, output = commands.getstatusoutput(api)
        return (status, output)
    except Exception as e:
        LOG.error( "Exception occured in Curl Command")
        return (-1,"")

def F5conf(fip, fixed_ip, vlan_port=2):
    start_time = time.time()
    #vlan_port = vlan_port + 1
    vlan_port = vlan_port - 1
    try:
        #####Initial configuration and Licensing###################
        LOG.info("mgmt_floating_ip: %s, data_ip: %s" %(fip, fixed_ip))

        #Login to Big IP , restart resjavad
        LOG.info( "Logging into BigIP ...")
        ssh_obj_ip= create_ssh_object(fip, "root",
                                       "default")
        if ssh_obj_ip == None:
            LOG.info( "SSH to BigIP failed")
        
        run_cmd_on_server(ssh_obj_ip, "echo > /root/.ssh/authorized_keys")
        run_cmd_on_server(ssh_obj_ip, "mv -b /config/f5-rest-device-id /config/old.f5-rest-device-id")

        ##Licensing BIG-IP SERVICE##
        f5_license_status = 0

        f5_license_status = f5_license(fip, ssh_obj_ip)
        if f5_license_status == 0:
            pass
        else:
            LOG.info( "*********************** VM IS NOT LICENSED. Continuing without License. ....................")

        ######################################################################################
        #VLAN Internal
        # Insert a sleep of 10 sec to avoid rest exception while executing CURL.
        time.sleep(10)
        vlan_name = "Internal_"+"1."+str(vlan_port)
        api = """curl  -sk -u admin:admin https://"""+fip+"""/mgmt/tm/net/vlan/ -H \
              'Content-Type: application/json' -X POST -d '{"name":"""+"\""+vlan_name+""""}'"""
        status, output = executeCurl(api)
        if status==0:
            print output
            LOG.info( str(output))
            LOG.info("VLAN Internal Created")
        else:
            raise Exception("VLAN Internal Failed")
        
        # Insert a sleep of 10 sec to avoid rest exception while executing CURL.
        time.sleep(10)
        ## VLAN Internal added to interface
        api = """curl -k -u "admin:admin" https://"""+fip+"""/mgmt/tm/net/vlan/"""+vlan_name+""" -H\
              "Content-Type:application/json" -X PUT -d '{"name":"interfaces",\
              "interfaces":[{"name":"1."""+str(vlan_port)+"\""+""", "tagged":false}]}'"""

        status, output = executeCurl(api)
        if status==0:
            print output
            LOG.info(output)
            LOG.info("VLAN Internal interface added to eth1")
        else:
            raise Exception("VLAN Internal interface failed to add")
        
        # Insert a sleep of 10 sec to avoid rest exception while executing CURL.
        time.sleep(10)
	############################################################################
        #Assign Self IP to VLAN group
        fixed_ip1=fixed_ip+'/26' 
        mydict = '{"name":"selfip_1.'+str(vlan_port)+'"'+',"fullPath":"selfip_1.'+str(vlan_port)+'"'+'\
                 ,"generation":4041,"address":"'+fixed_ip1+'", "floating":"disabled",\
                 "inheritedTrafficGroup":"false","trafficGroup":"/Common/traffic-group-local-only",\
               "unit":0,"vlan":"/Common/' + vlan_name + '","allowService":"all"}'
        LOG.info( "%s" %mydict)
        api = """curl -sk -u admin:admin https://"""+fip+"""/mgmt/tm/net/self/ -H \
              "Content-Type:application/json" -X POST -d '"""+mydict+"""'"""
     
        status, output = executeCurl(api)
        if status==0:
            print output
            LOG.info(output)
            LOG.info( "self ip configured! DONE")
        else:
            LOG.info("self ip not configured")
            raise Exception("self ip not configured, Quitting")
	
	    ## To modify the sys db
        res = run_cmd_on_server(ssh_obj_ip, "tmsh modify sys db provision.extramb value 600")
        LOG.info("%s" %res)

        config = ConfigParser.RawConfigParser()
    
        config.read(F5_AGENT_CONFIG_FILE)
        config.set('DEFAULT','icontrol_hostname',str(fip))
        with open(F5_AGENT_CONFIG_FILE, 'wb') as configfile:
            config.write(configfile)

    except Exception as e:
        LOG.info( "an exception occurred" + str(e))

    finish_time = time.time()
    LOG.info( "The Script Execution time is :- " + str(finish_time - start_time))



if __name__ == '__main__':
    try:
        inst=F5conf(sys.argv[1], sys.argv[2])
    except:
        inst=F5conf(sys.argv[1], None)
    LOG.info("%s" %inst)

