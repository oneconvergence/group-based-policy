#!/bin/bash
CONFIGURATOR_PASS='oc@sc!23;)'
config_ip=$(nova list | grep configuratorVM_instance | cut -d'=' -f2 | cut -d' ' -f1)
user='root'
FROM='v1'
TO='v2'

