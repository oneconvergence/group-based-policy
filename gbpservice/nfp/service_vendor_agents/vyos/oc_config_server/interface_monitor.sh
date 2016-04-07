#!/usr/bin/env bash

 function enumerate_net_interfaces {

          echo `date` `ip addr` >> /var/log/oc/vyos_monitor
          echo "\n"
          echo `date` `sudo netstat -pantl | grep 8888` >>/var/log/oc/vyos_monitor
 }

 enumerate_net_interfaces

