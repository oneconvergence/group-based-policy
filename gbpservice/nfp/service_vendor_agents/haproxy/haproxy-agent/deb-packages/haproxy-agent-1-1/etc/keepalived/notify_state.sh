#!/bin/bash

STATE=$1

case $STATE in
        "MASTER") /usr/sbin/haproxy -f /etc/haproxy/haproxy.cfg -p /var/run/haproxy.pid -sf `cat /var/run/haproxy.pid`
                  sudo bash /etc/dhcp/dhclient-exit-hooks.d/haproxy_routing
                  echo "State changed to $STATE" >> /root/role.txt
                  exit 0
                  ;;
        "BACKUP") sudo kill -9 `cat /var/run/haproxy.pid`
                  sudo bash /etc/dhcp/dhclient-exit-hooks.d/haproxy_routing
                  echo "State changed to $STATE" >> /root/role.txt
                  exit 0
                  ;;
        "FAULT")  sudo kill -9 `cat /var/run/haproxy.pid`
                  echo "State changed to $STATE" >> /root/role.txt
                  echo $STATE >> /root/role.txt
                  exit 0
                  ;;
        *)        echo "unknown state"
                  exit 1
                  ;;
esac


