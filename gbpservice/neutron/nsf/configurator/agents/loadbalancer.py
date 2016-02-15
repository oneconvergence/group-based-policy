class LBaasRpcManager(object):
    def __init__(self, conf, sc):
        pass


class LBaasEventHandler():
    def __init__(self, sc):
        self._load_drivers()

    def handle_event(self, ev):
        pass

    def _load_drivers(self):
        # Driver load logic goes here
        pass
