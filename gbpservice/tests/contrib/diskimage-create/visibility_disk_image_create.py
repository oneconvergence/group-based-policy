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


def create_visibility_docker():
    '''
    1. git pull of visibility
    2. create docker image
    3. save docker image
    '''

    git = conf['git']
    # verify the 'visibility' git directory is present parallel to 'service-controller'
    vis_dir = git['git_path_visibility']

    docker_images = "%s/output/docker_images/" % cur_dir
    if not os.path.exists(docker_images):
        os.makedirs(docker_images)

    # create a docker image
    os.chdir(vis_dir)
    docker_args = ['docker', 'build',  '-f', 'visibility/docker/UI/Dockerfile', '-t', 'visibility-docker', '.']
    ret = subprocess.call(docker_args)
    if(ret):
        print "Failed to build docker image [visibility-docker]"
        return -1

    os.chdir(docker_images)
    del(docker_args)
    # save the docker image
    docker_args = ['docker', 'save', '-o', 'visibility-docker', 'visibility-docker']
    ret = subprocess.call(docker_args)
    if(ret):
        print "Failed to save docker image [visibility-docker]"
        return -1

    # set environment variable, needed by 'extra-data.d'
    os.environ['VISIBILITY_GIT_PATH'] = vis_dir
    os.environ['DOCKER_IMAGES_PATH'] = docker_images

    return 0


def create_configurator_docker():
    configurator_dir = "%s/../../../nfp/configurator" % cur_dir
    docker_images = "%s/output/docker_images/" % cur_dir
    if not os.path.exists(docker_images):
        os.makedirs(docker_images)
 
    # create a docker image
    os.chdir(configurator_dir)
    docker_args = ['docker', 'build', '-t', 'configurator-docker', '.']
    ret = subprocess.call(docker_args)
    if(ret):
        print "Failed to build docker image [configurator-docker]"
        return -1

    os.chdir(docker_images)
    del(docker_args)
    # save the docker image
    docker_args = ['docker', 'save', '-o', 'configurator-docker', 'configurator-docker']
    ret = subprocess.call(docker_args)
    if(ret):
        print "Failed to save docker image [configurator-docker]"
        return -1
    # set environment variable, needed by 'extra-data.d'
    os.environ['DOCKER_IMAGES_PATH'] = docker_images

    return 0


def create_apt_source_list():
    """
    Creates a file 00-haproxy-agent-debs, this will be executed by dib to
    create a file haproxy-agent-debs.list file inside VM at /etc/apt/sources.list.d/
    This file will contain entries for apt to fetch any debs from
    our local repo
    """
    elems = "%s/elements" % cur_dir

    # update repo_host ip in 00-haproxy-agent-debs file
    # this file will be copied to VM at /etc/apt/sources.list.d/
    os.chdir("%s/debs/pre-install.d/" % elems)
    f = open("00-haproxy-agent-debs", 'w')
    print >> f, "#!/bin/bash\n\n"
    print >> f, "set -eu"
    print >> f, "set -o xtrace"
    print >> f, "apt-get install ubuntu-cloud-keyring"

    if 'haproxy' in conf['dib']['elements']:
        tmp_str = ('echo "deb http://%s/ /haproxy/"'
                   ' > /etc/apt/sources.list.d/haproxy-agent-debs.list'
                   % 'localhost')
        print >> f, tmp_str


def update_haproxy_repo():
    haproxy_vendor_dir = ("%s/../../../nfp/service_vendor_agents/haproxy"
                          % cur_dir)
    service = 'haproxy-agent' 
    version = '1'
    release = '1'
    subprocess.call(['rm', '-rf',
                     "%s/%s/deb-packages" % (haproxy_vendor_dir, service)])
    os.chdir(haproxy_vendor_dir)
    ret = subprocess.call(['bash',
                           'build_haproxy_agent_deb.sh',
                           service,
                           version, release])
    if(ret):
        print "ERROR: Unable to generate haproxy-agent deb package"
        return 1

    subprocess.call(["rm", "-rf", "/var/www/html/haproxy"])
    out = subprocess.call(["mkdir", "-p", "/var/www/html/haproxy/"])
    haproxy_agent_deb = ("%s/%s/deb-packages/%s-%s-%s.deb"
                         % (haproxy_vendor_dir, service,
                            service, version, release))
    subprocess.call(["cp", haproxy_agent_deb, "/var/www/html/haproxy/"])

    os.chdir("/var/www/html")
    out = commands.getoutput("dpkg-scanpackages haproxy/ /dev/null"
                             " | gzip -9c > haproxy/Packages.gz")
    print out

    return 0


def dib():
    dib = conf['dib']
    elems = "%s/elements/" % cur_dir

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
            service_dir = "%s/../nfp_service/" % cur_dir
            service_dir = os.path.realpath(service_dir)
            os.environ['SERVICE_GIT_PATH'] = service_dir
        if element == 'configurator':
            image_name = 'configurator'
            create_configurator_docker()
            # for bigger size images
            dib_args.append('--no-tmpfs')
        if element == 'visibility':
            image_name = 'visibility'
            # create a docker image
            create_visibility_docker()
            create_configurator_docker()
            # for bigger size images
            dib_args.append('--no-tmpfs')
        if element == 'haproxy':
            image_name = 'haproxy'
            dib_args.append('debs')
            create_apt_source_list()

    # offline mode, assuming the image cache (tar) already exists
    dib_args.append('--offline')
    cache_path = dib['cache_path'].replace('~', os.environ.get('HOME', '-1'))
    dib_args.append('--image-cache')
    dib_args.append(cache_path)

    dib_args.append('--image-size')
    dib_args.append(str(dib['image_size_in_GB']))
    #timestamp = datetime.datetime.now().strftime('%I%M%p-%d-%m-%Y')
    #image_name = "%s_%s" % (image_name, timestamp)
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
        image_path = "%s/output/%s.qcow2" % (cur_dir, image_name)
        print("Image location: %s" % image_path)
        with open("/tmp/image_path", "w") as f:
            f.write(image_path)


def git_pull(git_path, https=None):
    """ Does a git pull in the local path mentioned """
    try:
        os.chdir(git_path)
    except Exception as e:
        print e
        return 1

    print "Doing 'git pull' in %s" % (git_path)
    if(https):
        ret = subprocess.call(["git", "pull", https])
    else:
        ret = subprocess.call(["git", "pull"])
    if ret:
        print "ERROR: 'git pull' failed in path: ", git_path
        return 1

    return 0


def check_app(app):
    """ checks if the particular package is installed """
    return subprocess.call(["which", app])


def validate_run():
    """ Validates the following:
        1. git paths mentioned in json file are git directories
        2. local apache server is running to act as a local repo host
        3. qemu-img application is installed, needed by dib
    """
    git = conf['git']
    elements = conf['dib']['elements']
    local_repo = False
    # check for element 'sc' configured
    if "sc" in elements:
        git_path = git['git_path_service-controller']
        https = 'https://%s:%s@github.com/oneconvergence/service-controller.git' % (git['username'], git['password'])
        if(git_pull(git_path, https)):
            return 1
        local_repo = True
    # check for element 'haproxy' configured
    if "haproxy" in elements:
        git_path = git['git_path_group-based-policy']
        # group-based-policy git is a public repo, doesn't need username/password
        if(git_pull(git_path)):
            return 1
        local_repo = True
    # check for element 'visibility' configured
    if "visibility" in elements or 'configurator' in elements:
        git_path = git['git_path_visibility']
        https = 'https://%s:%s@github.com/oneconvergence/visibility.git' % (git['username'], git['password'])
        if(git_pull(git_path, https)):
            return 1
        # find if 'docker' is installed
        if(check_app("docker")):
            print "ERROR: Please install package 'docker'"
            return 1

    # find if 'qemu-ing' is installed
    if(check_app("qemu-img")):
        print "ERROR: Please install package 'qemu-img'"
        return 1

    if(local_repo):
        # check if apache2 server is running
        res = subprocess.call(["service", "apache2", "status"])
        if(res):
            print "ERROR: Please install/start 'apache2'"
            return 1

    return 0


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

    # if password has '@'' then replace it with it's url encoded value: '%40'
    # else can't execute git clone/pull in single command with username/password
    conf['git']['password'] = conf['git']['password'].replace('@', '%40')
    git = conf['git']

    if(validate_run()):
        exit()

    elem = 'haproxy'
    if elem in elements:
        if(update_haproxy_repo()):
            exit()

    # run Disk Image Builder to create VM image
    dib()
