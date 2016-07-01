import shlex
import subprocess

import netifaces


def initiate_dhclient():
    interfaces = netifaces.interfaces()
    for interface in interfaces:
        cmd = "sudo dhclient %s" % interface
        args = shlex.split(cmd)
        if not netifaces.ifaddresses(interface).get(netifaces.AF_INET):
            output, error = subprocess.Popen(
                args, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE).communicate()
            if error:
                raise
