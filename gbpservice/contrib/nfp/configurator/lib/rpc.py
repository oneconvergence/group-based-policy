import oslo_messaging
from oslo_service import service as oslo_service
from oslo_config import cfg as oslo_config

from gbpservice.nfp.core import log as nfp_logging

CONF = oslo_config.CONF
TRANSPORT = oslo_messaging.get_transport(CONF)

LOG = nfp_logging.getLogger(__name__)

def get_client(topic):
    target = oslo_messaging.Target(topic=topic)
    return oslo_messaging.RPCClient(TRANSPORT, target)


class RpcAgent(oslo_service.Service):
    def __init__(self, host=None, topic=None, manager=None):
        super(RpcAgent, self).__init__()
        self.host = host
        self.topic = topic
        self.manager = manager
        self.rpc_server = None

    def start(self):
        super(RpcAgent, self).start()
        target = oslo_messaging.Target(
            topic=self.topic,
            server=self.host)
        server = oslo_messaging.get_rpc_server(
            TRANSPORT, target, [self.manager],
            'eventlet')
        server.start()
        self.rpc_server = server
        

    def stop(self):
        try:
            self.rpc_server.stop()
            self.rpc_server.wait()
        except Exception as exc:
            LOG.error("Exception - %s" %(str(exc))

        super(RPCAgent, self).stop()
