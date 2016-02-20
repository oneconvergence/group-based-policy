
class AgentBase(object):
    def __init__(self, sc, conf):
        self._sc = sc
        self._conf = conf
    
    def process_request(self, context, sa_info_list, notification_data):
        if not isinstance(sa_info_list, list):
            return None
        if not isinstance(notification_data, list):
            return None
        if len(sa_info_list) > 1:
            args_dict = {'context': context,
                        'sa_info_list': sa_info_list,
                        'notification_data': notification_data}
            ev = self._sc.event(id='PROCESS_BATCH', data=args_dict)
            self._sc.rpc_event(ev)
        else:
            getattr(self, sa_info_list[0]['method'])(context,
                                            **sa_info_list[0]['kwargs'])

def init_agent_complete(cm, sc, conf):
    pass

def init_agent(cm, sc, conf):
    pass
