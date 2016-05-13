#!/bin/bash

service rabbitmq-server start
cd /tmp
echo "Cleaning Local Repository ....."
sudo rm -rf *
sudo rm -rf /usr/local/lib/python2.7/dist-packages/gbpservice
sudo rm -rf /usr/local/lib/python2.7/dist-packages/neutron
sudo rm -rf /usr/local/lib/python2.7/dist-packages/neutron-lib
git clone -b stable/mitaka --single-branch https://github.com/openstack/neutron-lib.git neutron_lib
git clone -b stable/mitaka --single-branch https://github.com/openstack/neutron.git neutron
git clone -b mitaka_21st_march_base --single-branch https://github.com/oneconvergence/group-based-policy.git mitaka_21st_march_base
cd /tmp/neutron
sudo python setup.py install
cd /tmp/neutron_lib
sudo pip install -r requirements.txt --allow-all-external && sudo python setup.py install
cd /tmp
cp -r mitaka_21st_march_base/gbpservice/nfp/bin/nfp /usr/bin/
chmod +x /usr/bin/nfp
cp -r mitaka_21st_march_base/gbpservice/nfp/bin/nfp_configurator.ini /etc/
cp -r mitaka_21st_march_base/gbpservice/nfp/bin/policy.json /etc/
mkdir -p /var/log/nfp
touch /var/log/nfp/nfp_configurator.log
cd mitaka_21st_march_base/
sudo pip install -r requirements.txt --allow-all-external && sudo python setup.py install

screen -dmS "configurator" /usr/bin/python2 /usr/bin/nfp --config-file=/etc/nfp_configurator.ini --log-file=/var/log/nfp/nfp_configurator.log
cd /usr/local/lib/python2.7/dist-packages/gbpservice/nfp/configurator/api/

sudo python setup.py develop
screen -dmS  "pecan" pecan serve config.py
/bin/bash

