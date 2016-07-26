#!/usr/bin/env bash

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

 function enumerate_net_interfaces {

          echo `date` `ip addr` >> /var/log/oc/vyos_monitor
          echo "\n"
          echo `date` `sudo netstat -pantl | grep 8888` >>/var/log/oc/vyos_monitor
 }

 enumerate_net_interfaces

