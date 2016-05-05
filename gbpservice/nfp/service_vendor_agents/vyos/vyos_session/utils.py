import ConfigParser
import subprocess
import os
import logging
import logging.handlers as handlers

# In production environment CONFIG_DIR should be /etc/pyatta/
CONFIG_DIR = "/usr/share/vyos-oc"
CONFIG_FILE_NAME = "oc-vyos.conf"
AVAILABLE_LOG_LEVELS = ['DEBUG','INFO','WARN','ERROR','CRITICAL']
DEFAULT_LOG_LEVEL = 'INFO'

logger = logging.getLogger(__name__)


def get_config_params(section, key):
    """
    To get specific parameters valuers from config file
    """
    config = ConfigParser.SafeConfigParser()
    config.readfp(open(os.path.join(CONFIG_DIR, CONFIG_FILE_NAME)))
    return config.get(section, key)


def get_log_level():
    """
    Get and check log level value from pyatta.conf file.
    """
    log_level = get_config_params('log', 'level')
    if log_level not in AVAILABLE_LOG_LEVELS:
        print('[ERROR] Unknown log level !')
        return DEFAULT_LOG_LEVEL
    return log_level


def get_log_filehandler():
    """
    Create file handler which logs messages.
    """
    log_dir = get_config_params('log', 'logdir')
    log_file = get_config_params('log', 'logfile')
    log_file_path = os.path.join(log_dir, log_file)
    if not os.path.exists(log_dir) or not os.path.exists(log_file_path):
        try:
            os.makedirs(log_dir)
            open(log_file_path, 'a').close()
        except OSError as exception:
            print exception
            return False
        print "[INFO] Create log file %s" % log_file_path
    # create file handler
    fh = logging.FileHandler(log_file_path,'a')
    fh.setLevel(eval('logging.{0}'.format(get_log_level())))
    return fh


def init_logger(logger):
    """
    Initialize logger object for logging application's activities to a
    specific file.
    """
    # create logger
    logger.setLevel(eval('logging.{0}'.format(get_log_level())))
    # create formatter and add it to the handlers
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - '
                                  '%(message)s')
    file_handler = get_log_filehandler()
    file_handler.setFormatter(formatter)
    # add the handlers to the logger
    logger.addHandler(file_handler)

    formatter = logging.Formatter('vyos %(name)s %(funcName)s() %(levelname)s '
                                  '%(message)s')
    sys_handler = handlers.SysLogHandler(address=('localhost', 514))
    sys_handler.setFormatter(formatter)
    sys_handler.setLevel(logging.DEBUG)
    logger.addHandler(sys_handler)


def _run(cmd, output=False):
    """
    To run command easier
    """
    # FIXME: This whole code taken from someones personal github implementation
    # is really messy !!!!
    if output:
        try:
            logger.debug('exec command: "%s"', cmd)
            exec_pipe = subprocess.Popen(cmd, shell=True,
                                         stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE)
        except Exception as err:
            message = 'Executing command %s failed with error %s' %(cmd, err)
            logger.error(message)
            return False

        cmd_output, cmd_error = exec_pipe.communicate()
	    # VPN commits succeed but we are getting perl locale warnings on stderr
        if exec_pipe.returncode != 0:
            message = 'Executing command %s failed with error %s. Output is: %s'%(cmd, cmd_error, cmd_output)
            logger.error(message)
            return False
        else:
            logger.debug('command output: %s', cmd_output)
            return True
    else:
        try:
            logger.debug('exec command: "%s"', cmd)
            out = subprocess.check_call(cmd, shell=True) # returns 0 for True
        except subprocess.CalledProcessError as err:
            logger.error('command execution failed with Error: %s', err)
            out = 1  # returns 1 for False
        logger.debug('command return code: %s', out)
        return out

# Alternate implementation for configuring vyos - The whole pyatta module
# is replaced with this one method. This was required top fix the following
# issue :http://vyatta38.rssing.com/chan-10627532/all_p7.html
# Not sure if the other commands also may fails or if there is an issue with
# the way the config module does things
def _alternate_set_and_commit(cmd):
    try:
        vyos_wrapper = "/opt/vyatta/sbin/vyatta-cfg-cmd-wrapper"
        begin_cmd = "%s begin" %(vyos_wrapper)
        set_cmd = "%s %s" %(vyos_wrapper, cmd)
        commit_cmd = "%s commit" %(vyos_wrapper)
        save_cmd = "%s save" % (vyos_wrapper)
        end_cmd = "%s end" %(vyos_wrapper)
        command = "%s;%s;%s;%s;%s" % (begin_cmd, set_cmd, commit_cmd, save_cmd,
                                      end_cmd)
        logger.debug('exec command: "%s"', command)
        exec_pipe = subprocess.Popen(command, shell=True,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE)
    except Exception as err:
        message = 'Executing command %s failed with error %s' %(command, err)
        logger.error(message)
        return False

    cmd_output, cmd_error = exec_pipe.communicate()
    # VPN commits succeed but we are getting perl locale warnings on stderr
    if exec_pipe.returncode != 0:
        message = 'Executing command %s failed with error %s' %(command, cmd_error)
        logger.error(message)
        return False
    else:
        logger.debug('command output: %s', cmd_output)
        return True

def clean_environ(env):
    """
    Delete some envionment variables from system.
    """
    for key in env.keys():
        if os.environ.get('key'): del os.environ[key]


def ip2network(ip):
    quads = ip.split('.')
    netw = 0
    for i in range(4):
        netw = (netw << 8) | int(len(quads) > i and quads[i] or 0)
    return netw


def get_ip_address_with_netmask(ip, netmask):
    prefix = bin(ip2network(netmask)).count('1')
    ip_addr = ip + "/" + str(prefix)
    return ip_addr


# initilize the logger for this module
init_logger(logger)
