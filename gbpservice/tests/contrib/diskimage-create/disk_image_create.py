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

#! /usr/bin/python

import commands
import datetime
import os
from oslo_serialization import jsonutils
import subprocess
import sys


conf = []
cur_dir = ''


def parse_json(j_file):
    global conf

    with open(j_file) as json_data:
        conf = jsonutils.load(json_data)
    return


def update_haproxy_repo():
    haproxy_vendor_dir = (cur_dir +
                          '/../../../nfp/service_vendor_agents/haproxy')
    
    subprocess.call(['rm', '-rf',
                     haproxy_vendor_dir + '/haproxy-agent/deb-packages'])
    os.chdir(haproxy_vendor_dir)
    ret = subprocess.call(['bash',
                           'build_haproxy_agent_deb.sh',
                           'haproxy-agent',
                           git['tag'], str(git['rel'])])
    if(ret):
        print "ERROR: Unable to generate haproxy-agent deb package"
        return 1

    subprocess.call(["rm", "-rf", "/var/www/html/haproxy"])
    out = subprocess.call(["mkdir", "-p", "/var/www/html/haproxy/"])
    haproxy_agent_deb = (haproxy_vendor_dir +
                   '/haproxy-agent/deb-packages' +
                   'haproxy-agent-' +
                   git['tag'] + '-' + str(git['rel']) +
                   '.deb')
    subprocess.call(["cp", haproxy_agent_deb, "/var/www/html/haproxy/"])

    os.chdir("/var/www/html")
    out = commands.getoutput("dpkg-scanpackages haproxy/ /dev/null"
                             " | gzip -9c > haproxy/Packages.gz")
    print out

    return 0


def dib():
    dib = conf['dib']
    elems = cur_dir + '/elements/'

    # set the elements path in environment variable
    os.environ['ELEMENTS_PATH'] = elems
    # set the Ubuntu Release for the build in environment variable
    os.environ['DIB_RELEASE'] = conf['ubuntu_release']['release']

    # basic elements
    dib_args = ['disk-image-create', 'base', 'vm', 'ubuntu']

    # configures elements
    for element in dib['elements']:
        dib_args.append(element)
        # root login enabled, set password environment varaible
        if element == 'root-passwd':
            os.environ['DIB_PASSWORD'] = dib['root_password']
        if element == 'devuser':
            os.environ['DIB_DEV_USER_USERNAME'] = 'ubuntu'
            os.environ['DIB_DEV_USER_SHELL'] = '/bin/bash'
            os.environ['SSH_RSS_KEY'] = (
                "%s/output/%s" % (cur_dir, image_name))
            os.environ['DIB_DEV_USER_AUTHORIZED_KEYS'] = (
                "%s.pub" % os.environ['SSH_RSS_KEY'])
        if element == 'nfp-reference-configurator':
            image_name = 'nfp_reference_service'
            service_dir = cur_dir + '/../nfp_service/'
            service_dir = os.path.realpath(service_dir)
            os.environ['SERVICE_GIT_PATH'] = service_dir
        if element == 'haproxy':
            image_name = 'haproxy'

    # offline mode, assuming the image cache (tar) already exists
    dib_args.append('--offline')
    cache_path = dib['cache_path'].replace('~', os.environ.get('HOME', '-1'))
    dib_args.append('--image-cache')
    dib_args.append(cache_path)

    dib_args.append('--image-size')
    dib_args.append(str(dib['image_size_in_GB']))
    #timestamp = datetime.datetime.now().strftime('%I%M%p-%d-%m-%Y')
    #image_name = image_name + '_' + timestamp
    dib_args.append('-o')
    dib_args.append(str(image_name))

    os.chdir(cur_dir)
    out_dir = 'output'
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    os.chdir(out_dir)
    print("DIB-ARGS: %r" % dib_args)

    ret = subprocess.call(dib_args)
    if not ret:
        image_path = cur_dir + '/output/' + image_name + '.qcow2'
        print("Image location: %s" % image_path)
        with open("/tmp/image_path", "w") as f:
            f.write(image_path)


if __name__ == "__main__":

    if len(sys.argv) != 2:
        print("ERROR: Invalid Usage")
        print("Usage:\n\t%s <json config file>" % sys.argv[0])
        print("\twhere: <json config file> contains all the configuration")
        exit()

    # save PWD
    cur_dir = os.path.dirname(__file__)
    cur_dir = os.path.realpath(cur_dir)
    if not cur_dir:
        # if script is executed from current dir, get abs path
        cur_dir = os.path.realpath('./')

    # parse args from json file
    parse_json(sys.argv[1])
    elements = conf['dib']['elements']
    elem = 'haproxy'
    if elem in elements:
        if(update_haproxy_repo()):
            exit()

    # run Disk Image Builder to create VM image
    dib()
