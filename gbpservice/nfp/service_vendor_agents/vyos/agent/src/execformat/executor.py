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

import logging
import os
import shlex
import subprocess

from vyos_session.configsession import ConfigSession
from vyos_session.configsession import SessionNotExists
from vyos_session import utils

logger = logging.getLogger(__name__)
utils.init_logger(logger)

try:
    session = ConfigSession()
except Exception as err:
    logger.error('A session exist already !')

VYOS_SBIN_DIR = utils.get_config_params('bin', 'vyos_sbin_dir')
VYOS_SHELL_API = utils.get_config_params('bin', 'shell_api_path')


class OperationFailed(Exception):
    pass


class OperationNameError(Exception):
    pass


class ConfigPathNotCorrect(Exception):
    pass


def check_operation_name(args):
    """ Check if operation/command name is correct. """
    if len(args) == 0:
        logger.error('Operation name required')
        raise OperationNameError('Operation name required.')
    elif args[0] not in ['show', 'set', 'delete', 'edit']:
        logger.error('Operation name "%s" not correct' % args[0])
        raise OperationNameError('Operation name not correct.')
    return True


def _runner(command):
    """
    Run shell commands via subprocess.Popen()
    """
    # NOTE:
    # if Popen(self.args, shell=True, ...) => Execution fails
    # if Popen(self.args, ...) => OSError: [Errno 2] No such file or directory
    # if self.args = ['/bin/cli-shell-api','showCfg', ...] and
    # Popen(self.args, ...) that works but actually we keep using '
    # '.join(self.args).
    proc = subprocess.Popen(command, shell=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # wait for the process to terminate and get stdout/stderr outputs
    out, err = proc.communicate()
    return out, err, proc.returncode


def _op_command(command=None):
    command = './op_commands.sh'
    command += " " + "\"run show vpn ipsec sa\""

    proc = subprocess.Popen(command, shell=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = proc.communicate()
    return out


class execUtils(object):
    """ Executes possible operations in a Vyos configure session."""

    def __init__(self, args):
        self.args = args

    def execmd(self, nonsession=False):
        """
        Performs execution of allowed config operations ['show','set','delete']
        """
        if check_operation_name(self.args):
            # prepare executable file to be called
            operation_name = self.args[0]
            logger.info('Perform operation "%s"' % operation_name)

            if not nonsession:
                if self.args[0] == 'show':
                    self.args[0] = '{0} showCfg'.format(
                        VYOS_SHELL_API)
                else:
                    self.args[0] = os.path.join(VYOS_SBIN_DIR,
                                                'my_{0}'.format(self.args[0]))
            logger.debug('exec command: "%s"' % ' '.join(self.args))

            if not nonsession and not session.session_exists():
                raise SessionNotExists('Configure session do not exists')

            if not nonsession:
                result = _runner(' '.join(self.args))
            else:
                result = _op_command()
                return (True, result)

            logger.debug('command return code: %s' % result[2])

            if result[2]:
                logger.info('command output: %s' %
                            ' '.join(result[0].splitlines()))
                logger.error('Failed executing operation "%s"' %
                             operation_name)
                raise OperationFailed('Operation failed !')
            logger.debug('%s' % ' '.join(result[0].splitlines()))
            logger.info('Executing "%s" operation OK' % operation_name)
            return (True, result[0])

    def check_cmd_args(self):
        """
        Check that config path is correct before performing execmd()
        """
        logger.info('Check specified configuration path existance')
        config_path = ' '.join(self.args[1:])
        logger.info('config path: "%s"' % config_path)
        cmd = '{0} exists {1}'.format(VYOS_SHELL_API, config_path)
        logger.debug('exec command: "%s"' % cmd)
        result = _runner(cmd)
        logger.debug('command return code: %s' % result[2])
        if result[2]:
            logger.error('Configuration path is not correct')
            raise ConfigPathNotCorrect('Configuration path is not correct')
        logger.info('Configuration path is correct')
        return True

    def get_possible_options(self):
        """
        Returns list of nodes under specified configuration path
        """
        out = []
        try:
            self.check_cmd_args()  # check config path validation
        except ConfigPathNotCorrect:
            return False, out  # config path is not correct

        config_path = ' '.join(self.args[1:])
        logger.info('Get possible options of config path "%s"' % config_path)
        cmd = '{0} listNodes {1}'.format(VYOS_SHELL_API, config_path)
        logger.debug('exec command: "%s"' % cmd)
        result = _runner(cmd)  # rst = (stdout, stderr, errcode)
        logger.debug('command return code: %s' % result[2])
        if not result[0]:
            logger.info('No more options for the specified config path')
            return True, result[0]
        options = shlex.split(result[0])
        logger.debug('List of options : "%s"' % options)
        return True, options
