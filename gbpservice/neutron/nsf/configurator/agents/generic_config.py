class GenericConfigRpcManager(object):
    def __init__(self, conf, sc):
        pass


class GenericConfigEventHandler():
    def __init__(self, sc):
        self._load_drivers()

    def handle_event(self, ev):
        pass

    def _load_drivers(self):
        # Driver load logic goes here
        pass
