#!/bin/vbash
cmd1="$1"
source /opt/vyatta/etc/functions/script-template
eval "$cmd1"
echo $?
#run show vpn ipsec sa
