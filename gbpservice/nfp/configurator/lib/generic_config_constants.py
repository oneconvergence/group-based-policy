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

DRIVERS_DIR = 'gbpservice.nfp.configurator.drivers'
SERVICE_TYPE = 'generic_config'
EVENT_CONFIGURE_INTERFACES = 'CONFIGURE_INTERFACES'
EVENT_CLEAR_INTERFACES = 'CLEAR_INTERFACES'
EVENT_CONFIGURE_ROUTES = 'CONFIGURE_ROUTES'
EVENT_CLEAR_ROUTES = 'CLEAR_ROUTES'
EVENT_PROCESS_BATCH = 'PROCESS_BATCH'
EVENT_CONFIGURE_HEALTHMONITOR = 'CONFIGURE_HEALTHMONITOR'
EVENT_CLEAR_HEALTHMONITOR = 'CLEAR_HEALTHMONITOR'

MAX_FAIL_COUNT = 12  # 5 secs delay * 12 = 60 secs
INITIAL = 'initial'
FOREVER = 'forever'
INITIAL_HM_RETRIES = 24  # 5 secs delay * 24 = 120 secs
