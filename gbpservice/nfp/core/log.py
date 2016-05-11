from oslo_log import log as oslo_logging

class NfpLogger(object):
    def __init__(self, name):
        self.logger = oslo_logging.getLogger(__name__)

    def _msg(self, msg, context):
        if 'log_meta' in context.keys():
            return "[%s] - %s" %(context['log_meta'], msg)
        return msg

    def debug(self, msg, context={}):
        self.logger.debug("%s" %(self._msg(msg, context)))

    def error(self, msg, context={}):
        self.logger.error("%s" %(self._msg(msg, context)))

    def warn(self, msg, context={}):
        self.logger.warn("%s" %(self._msg(msg, context)))

    def info(self, msg, context={}):
        self.logger.info("%s" %(self._msg(msg, context)))

    def exception(self, msg, context={}):
        self.logger.exception("%s" %(self._msg(msg, context)))

def getLogger(name):
    return NfpLogger(name)
