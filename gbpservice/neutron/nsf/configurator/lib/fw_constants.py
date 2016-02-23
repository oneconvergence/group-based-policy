# One Convergence, Inc. CONFIDENTIAL
# Copyright (c) 2012-2016, One Convergence, Inc., USA
# All Rights Reserved.
#
# All information contained herein is, and remains the property of
# One Convergence, Inc. and its suppliers, if any. The intellectual and
# technical concepts contained herein are proprietary to One Convergence,
# Inc. and its suppliers.
#
# Dissemination of this information or reproduction of this material is
# strictly forbidden unless prior written permission is obtained from
# One Convergence, Inc., USA

DRIVERS_DIR = '/usr/lib/python2.7/dist-packages/gbpservice/neutron/nsf/'\
              'configurator/drivers/firewall'
SERVICE_TYPE = 'firewall'
VYOS = 'vyos'
NEUTRON = 'neutron'

CONFIGURATION_SERVER_PORT = '8888'

STATUS_ACTIVE = "ACTIVE"
STATUS_DELETED = "DELETED"
STATUS_UPDATED = "UPDATED"
STATUS_ERROR = "ERROR"
STATUS_SUCCESS = "SUCCESS"

request_url = "http://%s:%s/%s"
SUCCESS_CODES = [200, 201, 202, 203, 204]
ERROR_CODES = [400, 404, 500]

INTERFACE_NOT_FOUND = "INTERFACE NOT FOUND"

OC_FW_PLUGIN_TOPIC = 'q-firewall-plugin'
OC_FW_AGENT_BINARY = 'oc-fw-agent'
OC_AGENT_TYPE = 'OC FIREWALL AGENT'
OC_FIREWALL_DRIVER = 'VYOS FIREWALL DRIVER'

FIREWALL_RPC_TOPIC = "fwaas"
FIREWALL_GENERIC_CONFIG_RPC_TOPIC = "fwaas_generic_config"
