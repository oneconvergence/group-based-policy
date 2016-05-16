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
import threading
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

logging.setLoggerClass(WrappedLogger)

if '_LI' in globals().keys():
    globals()['_LI'] = _LI
if '_LE' in globals().keys():
    globals()['_LE'] = _LE

logging_context_store = threading.local()

class NfpLogContext(object):

    def __init__(self, **kwargs):
        self.meta_id = kwargs.get('meta_id', '')

    def emit(self):
        return "[LogMetaID:%s]" % (self.meta_id)

    def to_dict(self):
        return {'meta_id': self.meta_id}

class NfpLogger(object):

    def __init__(self, name):
        self.logger = oslo_logging.getLogger(name)

    def _prep_log_str(self, message, largs):
        message = message % (largs)
        context = _context()
        if context:
            _prefix = context.emit()
            return "%s - %s" % (_prefix, message)
        else:
            return "%s" % (message)

    def debug(self, message, largs={}):
        self.logger.debug(self._prep_log_str(message, largs))

    def info(self, message, largs={}):
        self.logger.info(self._prep_log_str(message, largs))

    def error(self, message, largs={}):
        self.logger.error(self._prep_log_str(message, largs))

    def warn(self, message, largs={}):
        self.logger.warn(self._prep_log_str(message, largs))

    def exception(self, message, largs={}):
        self.logger.exception(self._prep_log_str(message, largs))

def getLogger(name):
    return NfpLogger(name)

def store_logging_context(**kwargs):
    context = NfpLogContext(**kwargs)
    logging_context_store.context = context

def _context():
    return getattr(logging_context_store, 'context', None)

def get_logging_context():
    context = getattr(logging_context_store, 'context', None)
    if context:
        return context.to_dict()
    return {}


def _LI(message):
    return message


def _LE(message):
    return message

