
"""Implements base class for all service agents.

Common methods for service agents are implemented in this class. Configurator
module invokes these methods through the service agent's child class instance.

"""

class AgentBase(object):
    def __init__(self, sc, conf):
        self.sc = sc
        self.conf = conf
    
    def validate_request(self, sa_info_list, notification_data):
        if (isinstance(sa_info_list, list) and 
            isinstance(notification_data, list)):
            return True
        else:
            return False
        
    def forward_request(self, context, sa_info_list, notification_data):
        """Forwards the RPC message from configurator to service agents.
        
        Checks if the request message contains multiple data blobs. If multiple
        data blobs are found, a batch event is generated otherwise a single
        event.
        
        :param context: RPC context
        :param sa_info_list: List of data blobs prepared by de-multiplexer
        for service agents processing.
        :param notification_data: Notification blobs prepared by the service
        agents after processing requests blobs. Each request blob will have
        a corresponding notification blob.
        
        Returns: None
 
        """

        # In case of malformed input, send failure notification
        if not self.validate_request(sa_info_list, notification_data):
            # TODO: Need to send failure notification
            return
        
        # Multiple request data blobs needs batch processing. Send batch
        # processing event or do direct processing of single request data blob
        if (len(sa_info_list) > 1):
            args_dict = {'context': context,
                        'sa_info_list': sa_info_list,
                        'notification_data': notification_data}
            ev = self.sc.event(id='PROCESS_BATCH', data=args_dict)
            self.sc.rpc_event(ev)
        else:
            getattr(self, sa_info_list[0]['method'])(context,
                                            **sa_info_list[0]['kwargs'])

def init_agent_complete(cm, sc, conf):
    """Placeholder method to satisfy configurator module agent loading."""
    pass

def init_agent(cm, sc, conf):
    """Placeholder method to satisfy configurator module agent loading."""
    pass
