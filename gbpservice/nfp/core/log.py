from oslo_log import log as oslo_logging

import inspect


class NfpLogMeta(object):

    def __init__(self, **kwargs):
        self.meta_id = kwargs.get('meta_id', '')
        self.event = kwargs.get('event', '')

    def emit(self):
        return "[event=%s, log_meta_id=%s]" % (self.event, self.meta_id)

    def to_dict(self):
        return {'meta_id': self.meta_id,
                'event': self.event}

    def from_dict(self, **kwargs):
        return NfpLogMeta(**kwargs)


class NfpLogger(object):

    def __init__(self):
        self.logger = oslo_logging.getLogger(__name__)

    def _prep_log_str(self, message, largs, meta):
        message = message % (largs)
        if isinstance(meta.log_meta, dict):
            meta.log_meta = NfpLogMeta(**(meta.log_meta))
        _prefix = meta.log_meta.emit()
        return "%s - %s" % (_prefix, message)

    def debug(self, message, largs={}, meta={}):
        self.logger.debug(self._prep_log_str(message, largs, meta))

    def info(self, message, largs={}, meta={}):
        self.logger.info(self._prep_log_str(message, largs, meta))

    def error(self, message, largs={}, meta={}):
        self.logger.error(self._prep_log_str(message, largs, meta))

    def warn(self, message, largs={}, meta={}):
        self.logger.warn(self._prep_log_str(message, largs, meta))

    def exception(self, message, largs={}, meta={}):
        self.logger.exception(self._prep_log_str(message, largs, meta))


class NfpMetaLogger(object):

    def __init__(self, logger, meta={}):
        self.logger = logger
        self.meta = meta

    def debug(self, message, largs={}):
        self.logger.debug(message, largs=largs, meta=self.meta)

    def error(self, message, largs={}):
        self.logger.error(message, largs=largs, meta=self.meta)

    def info(self, message, largs={}):
        self.logger.info(message, largs=largs, meta=self.meta)

    def warn(self, message, largs={}):
        self.logger.warn(message, largs=largs, meta=self.meta)

    def exception(self, message, largs={}):
        self.logger.exception(message, largs=largs, meta=self.meta)


def use_nfp_logging(logger_name='LOG'):
    globals()['logger_name'] = logger_name
    # Reassign log symbols to NFP symbols
    globals()[logger_name] = NfpLogger()
    if '_LI' in globals().keys():
        globals()['_LI'] = _LI
    if '_LE' in globals().keys():
        globals()['_LE'] = _LE


def patch_class(clazz):
    _init = clazz.__init__

    def __init__wrapper(*args, **kwargs):
        if 'log_meta' in kwargs.keys():
            setattr(clazz, 'log_meta',
                    kwargs.get('log_meta'))
            del kwargs['log_meta']
        else:
            setattr(clazz, 'log_meta', {})

        _init(*args, **kwargs)

    clazz.__init__ = __init__wrapper
    return clazz


def patch_method(func):
    def func_wrapper(self, *args, **kwargs):
        name = globals()['logger_name']
        logger = globals()[logger_name]  # func.func_globals[name]
        func.func_globals[name] = NfpMetaLogger(logger, meta=self)
        return func(self, *args, **kwargs)
    return func_wrapper


def add_meta(decorated_clazz, **kwargs):
    meta = NfpLogMeta(**kwargs)
    setattr(decorated_clazz, 'log_meta', meta)
    # Adding to the inbuilt member class also
    for clazz_member in inspect.getmembers(decorated_clazz):
        if hasattr(clazz_member[1], 'log_meta'):
            add_meta(clazz_member[1], **kwargs)


def _LI(message):
    return message


def _LE(message):
    return message
