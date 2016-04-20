# -*- coding: utf-8 -*-
import sys
import os
import re
import json
import time


from f5_init import *

class F5DetachAttach:
    ''' class for attach and detach VLAN
    '''
    def __init__(self, fip):
        self.fip = fip


    def detach(self, port_count=2):
        try:
            port_count = port_count - 1
            msg = ( "Logging into BigIP ...")
            #LOG.emit("info", msg)
            ssh_obj_ip= create_ssh_object(self.fip, "root", "default")
            if ssh_obj_ip == None:
                msg = ( "SSH to BigIP failed for fip = %s" % self.fip)
                #LOG.emit("error", msg)
                return

            run_cmd_on_server(ssh_obj_ip, "echo > /root/.ssh/authorized_keys")
            run_cmd_on_server(ssh_obj_ip, "mv -b /config/f5-rest-device-id /config/old.f5-rest-device-id")

            cmd_list = ["tmsh delete net self selfip_1."+str(port_count), "tmsh delete net vlan " + "Internal_1."\
                        +str(port_count), "rm –rf /var/db/mcpdb*",\
                        "touch /service/mcpd/forceload"]
            #cmd_list = ["tmsh delete net self selfip_1."+str(port_count), "tmsh delete net vlan " + "Internal_1."\
            #            +str(port_count)]

            for cmd in cmd_list:
                run_cmd_on_server(ssh_obj_ip, cmd)
                time.sleep(5)
            time.sleep(10)


        except Exception as err:
            msg = ("An exception occurred while deleting selfip and vlan %s"  % str(err).capitalize())
            #LOG.emit("error", msg)




