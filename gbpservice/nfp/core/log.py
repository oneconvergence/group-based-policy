#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from oslo_log import log as oslo_logging
import logging
import inspect
import os
import sys


if hasattr(sys, 'frozen'):  # support for py2exe
    _srcfile = "logging%s__init__%s" % (os.sep, __file__[-4:])
elif __file__[-4:].lower() in ['.pyc', '.pyo']:
    _srcfile = __file__[:-4] + '.py'
else:
    _srcfile = __file__
_srcfile = os.path.normcase(_srcfile)


def currentframe():
    """Return the frame object for the caller's stack frame."""
    try:
        raise Exception
    except:
        return sys.exc_info()[2].tb_frame.f_back

if hasattr(sys, '_getframe'):
    currentframe = lambda: sys._getframe(3)


class WrappedLogger(logging.Logger):

    def __init__(self, name):
        logging.Logger.__init__(self, name)

    def findCaller(self):
        """
        Find the stack frame of the caller so that we can note the source
        file name, line number and function name.
        """
        f = currentframe()
        # On some versions of IronPython, currentframe() returns None if
        # IronPython isn't run with -X:Frames.
        if f is not None:
            f = f.f_back
            f = f.f_back
        rv = "(unknown file)", 0, "(unknown function)"
        while hasattr(f, "f_code"):
            co = f.f_code
            filename = os.path.normcase(co.co_filename)
            if filename == _srcfile:
                f = f.f_back
                continue
            rv = (co.co_filename, f.f_lineno, co.co_name)
            break
        return rv


class NfpLogMeta(object):

    def __init__(self, **kwargs):
        self.meta_id = kwargs.get('meta_id', '')

    def emit(self):
        if self.meta_id != '':
            return "[LogMetaid: %s]" % (self.meta_id)
        return ''

    def to_dict(self):
        return {'meta_id': self.meta_id}

    def from_dict(self, **kwargs):
        return NfpLogMeta(**kwargs)


class NfpLogger(object):

    def __init__(self):
        logging.setLoggerClass(WrappedLogger)
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
