#!/usr/bin/env python

import commands
import datetime
import json
import os
import subprocess
import sys

conf = {}
cur_dir = ''

def parse_json(j_file):
    global conf

    with open(j_file) as json_data:
        conf = json.load(json_data)
    return


def create_configurator_docker():

    docker_images = cur_dir + '/docker-images/'
    docker_images = os.path.realpath(docker_images)

    # create a docker image
    os.chdir(cur_dir)
    # build configuratro docker
    docker_args = ['docker', 'build', '-t', 'configurator-docker', '.']
    ret = subprocess.call(docker_args)
    if(ret):
        print "Failed to build docker image [configurator-docker]"
        return -1

    if not os.path.isdir(docker_images):
        os.mkdir(docker_images)

    os.chdir(docker_images)
    del(docker_args)
    # save the docker image
    docker_args = ['docker', 'save', '-o', 'configurator-docker', 'configurator-docker']
    ret = subprocess.call(docker_args)
    if(ret):
        print "Failed to save docker image [configurator-docker]"
        return -1
    # set environment variable, needed by 'extra-data.d'
    os.environ['DOCKER_IMAGES'] = docker_images

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
    image_name = conf['ubuntu_release']['release']
    # element for creating configurator image
    if 'configurator' in dib['elements']:
        if(create_configurator_docker()):
            return
        # for bigger size images
        if not "--no-tmpfs" in dib_args:
            dib_args.append('--no-tmpfs')
        # append docker-opt element
        if not "docker-opt" in dib_args:
            dib_args.append("docker-opt")
        
    for element in dib['elements']:
        image_name = image_name + '_' + element
        dib_args.append(element)

    # offline mode, assuming the image cache (tar) already exists
    if(dib['offline']):
        dib_args.append('--offline')
    # set the image build cache dir
    dib_args.append('--image-cache')
    dib_args.append(dib['cache_dir'])
    # set image size
    dib_args.append('--image-size')
    dib_args.append(str(dib['image_size']))
    timestamp = datetime.datetime.now().strftime('%I%M%p-%d-%m-%Y')
    image_name = image_name + '_' + timestamp
    dib_args.append('-o')
    dib_args.append(str(image_name))

    os.chdir(cur_dir)
    out_dir = 'output'
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    os.chdir(out_dir)
    print "DIB-ARGS: ", dib_args
    ret = subprocess.call(dib_args)
    if not ret:
        output_path = os.path.realpath('./')
        print "Output path: ", output_path
        output_image = output_path + '/' + image_name + '.qcow2'
        return output_image
    
    return 0


if __name__ == "__main__":

    if os.geteuid():
        sys.exit("ERROR: Script should be run as sudo/root")
    if len(sys.argv) != 2:
        print "ERROR: Invalid Usage"
        print "Usage:\n\t%s <json config file>" % sys.argv[0]
	print "\twhere: <json config file> contains all the configuration"
        exit()
    # save PWD
    cur_dir = os.path.dirname(__file__)
    cur_dir = os.path.realpath(cur_dir)
    if not cur_dir:
        # if script is executed from current dir, get abs path
        cur_dir = os.path.realpath('./')

    # parse args from json file
    try:
        parse_json(sys.argv[1])
    except Exception as e:
        print "ERROR parsing json file"
        print e
        exit()

    # run Disk Image Builder to create VM image
    dib()
