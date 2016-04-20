#!/usr/bin/env python

import sys
import base64
import os
import subprocess
import traceback
import optparse
import ansible.utils.vars as utils_vars
from ansible.parsing.dataloader import DataLoader
from ansible.parsing.utils.jsonify import jsonify
from ansible.parsing.splitter import parse_kv
import ansible.executor.module_common as module_common
import ansible.constants as C
from oslo_log import log as logging
LOG = logging.getLogger(__name__)

try:
    import json
except ImportError:
    import simplejson as json


def write_argsfile(argstring, json=False):
    """ Write args to a file for old-style module's use. """
    argspath = os.path.expanduser("~/.ansible_test_module_arguments")
    argsfile = open(argspath, 'w')
    if json:
        args = parse_kv(argstring)
        argstring = jsonify(args)
    argsfile.write(argstring)
    argsfile.close()
    return argspath

def boilerplate_module(modfile, args, interpreter, check, destfile):
    """ simulate what ansible does with new style modules """
    loader = DataLoader()
    complex_args = {}
    if args.startswith("@"):
        # Argument is a YAML file (JSON is a subset of YAML)
        complex_args = utils_vars.combine_vars(complex_args, loader.load_from_file(args[1:]))
        args=''
    elif args.startswith("{"):
        # Argument is a YAML document (not a file)
        complex_args = utils_vars.combine_vars(complex_args, loader.load(args))
        args=''

    if args:
        parsed_args = parse_kv(args)
        complex_args = utils_vars.combine_vars(complex_args, parsed_args)

    task_vars = {}
    if interpreter:
        if '=' not in interpreter:
            LOG.info("interpreter must by in the form of ansible_python_interpreter=/usr/bin/python")
            sys.exit(1)
        interpreter_type, interpreter_path = interpreter.split('=')
        if not interpreter_type.startswith('ansible_'):
            interpreter_type = 'ansible_%s' % interpreter_type
        if not interpreter_type.endswith('_interpreter'):
            interpreter_type = '%s_interpreter' % interpreter_type
        task_vars[interpreter_type] = interpreter_path

    if check:
         complex_args['_ansible_check_mode'] = True

    (module_data, module_style, shebang) = module_common.modify_module(
        modfile,
        complex_args,
        task_vars=task_vars
    )

    modfile2_path = os.path.expanduser(destfile)
    LOG.info("*** F5-LICIENSING STARTED***")
    modfile2 = open(modfile2_path, 'w')
    modfile2.write(module_data)
    modfile2.close()
    modfile = modfile2_path

    return (modfile, module_style)

def runtest( modfile, argspath):
    """Test run a module, piping it's output for reporting."""

    os.system("chmod +x %s" % modfile)

    invoke = "%s" % (modfile)
    if argspath is not None:
        invoke = "%s %s" % (modfile, argspath)

    cmd = subprocess.Popen(invoke, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (out, err) = cmd.communicate()
    try:
        LOG.info("***********************************")
        LOG.info("RAW OUTPUT")
        LOG.info("%s" %out)
        LOG.info("%s" %err)
        results = json.loads(out)
    except:
        LOG.info("***********************************")
        LOG.info("INVALID OUTPUT FORMAT")
        LOG.info("%s" %out)
        traceback.print_exc()

    LOG.info("***********************************")
    LOG.info("PARSED OUTPUT")
    LOG.info(jsonify(results,format=True))
    return results


def f5_install_license(module_path, module_args, interpreter='python={}'.format(sys.executable), check=None, filename="~/.ansible_module_generated"):
    '''Driver program to liciense f5 big-ip machine'''
    (modfile, module_style) = boilerplate_module(module_path, module_args, interpreter, check, filename)
    argspath = None
    if module_style != 'new':
        if module_style == 'non_native_want_json':
            argspath = write_argsfile(options.module_args, json=True)
        elif module_style == 'old':
            argspath = write_argsfile(options.module_args, json=False)
        else:
            raise Exception("internal error, unexpected module style: %s" % module_style)

    return runtest(modfile, argspath)


