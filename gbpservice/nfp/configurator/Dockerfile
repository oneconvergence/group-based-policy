FROM ubuntu:14.04 

RUN apt-get -y update

# dependencies
RUN apt-get -y --force-yes install vim\
 python2.7\
 python-pip\
 python2.7-dev\
 libyaml-dev\
 git\
 rabbitmq-server\
 unzip
 

# python dependencies
RUN pip install python-keystoneclient \
oslo.config==3.6.0 \
oslo.log==2.4.0 \
oslo.messaging==4.2.0 \
oslo.db==4.4.0 \
oslo.policy \
pecan==1.0.4 \
wsme


RUN git clone -b stable/mitaka --single-branch https://github.com/openstack/neutron-lib.git neutron_lib
RUN cp -r  /neutron_lib/neutron_lib /usr/local/lib/python2.7/dist-packages/
RUN git clone -b stable/mitaka --single-branch https://github.com/openstack/neutron.git neutron
RUN cp -r /neutron/neutron /usr/local/lib/python2.7/dist-packages/
RUN git clone -b mitaka_21st_march_base --single-branch https://github.com/oneconvergence/group-based-policy.git mitaka_21st_march_base
RUN cp -r /mitaka_21st_march_base/gbpservice /usr/local/lib/python2.7/dist-packages/
RUN cp /mitaka_21st_march_base/gbpservice/nfp/bin/nfp /usr/bin/
RUN chmod +x /usr/bin/nfp
RUN cp /mitaka_21st_march_base/gbpservice/nfp/bin/nfp_configurator.ini /etc/
RUN cp /mitaka_21st_march_base/gbpservice/nfp/bin/policy.json /etc/
RUN mkdir -p /var/log/nfp
RUN touch /var/log/nfp/nfp_configurator.log
RUN touch /var/log/nfp/nfp_pecan.log
RUN sed -i "/version = version.encode('utf-8')/a\    version = '1.8.0'" /usr/local/lib/python2.7/dist-packages/pbr/packaging.py
RUN apt-get -y --force-yes install screen
COPY  ./run.sh /run.sh
RUN chmod +777 /run.sh

EXPOSE 8070:8080
EXPOSE 5672:5672
ENV HOME /root
CMD ["/run.sh"]
