DRIVERS_DIR = '/usr/lib/python2.7/dist-packages/gbpservice/nfp/'\
              'configurator/drivers/vpn'

SERVICE_TYPE = 'vpn'

STATE_PENDING = 'PENDING_CREATE'
STATE_INIT = 'INIT'
STATE_ACTIVE = 'ACTIVE'
STATE_ERROR = 'ERROR'
NEUTRON = 'NEUTRON'

CONFIGURATION_SERVER_PORT = 8888
request_url = "http://%s:%s/%s"
SUCCESS_CODES = [200, 201, 202, 203, 204]
ERROR_CODES = [400, 404, 500]

VYOS = 'vyos'
SM_RPC_TOPIC = 'VPN-sm-topic'
VPN_RPC_TOPIC = "vpn_topic"
VPN_GENERIC_CONFIG_RPC_TOPIC = "vyos_vpn_topic"

VPN_PLUGIN_TOPIC = 'vpn_plugin'
VPN_AGENT_TOPIC = 'vpn_agent'

