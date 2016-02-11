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

<<<<<<< HEAD
from keystoneclient import auth as ks_auth
from keystoneclient import session as ks_session
from neutron.notifiers import nova as n_nova
from novaclient import client as nclient
from novaclient import exceptions as nova_exceptions
from oslo_config import cfg
from oslo_log import log as logging
=======
from neutron.openstack.common import log as logging
from novaclient import exceptions as nova_exceptions
import novaclient.v1_1.client as nclient
from oslo.config import cfg
>>>>>>> origin

LOG = logging.getLogger(__name__)


class NovaClient:

    def __init__(self):

<<<<<<< HEAD
        auth = ks_auth.load_from_conf_options(cfg.CONF, 'nova')
        endpoint_override = None

        if not auth:

            if cfg.CONF.nova_admin_tenant_id:
                endpoint_override = "%s/%s" % (cfg.CONF.nova_url,
                                               cfg.CONF.nova_admin_tenant_id)

            auth = n_nova.DefaultAuthPlugin(
                auth_url=cfg.CONF.nova_admin_auth_url,
                username=cfg.CONF.nova_admin_username,
                password=cfg.CONF.nova_admin_password,
                tenant_id=cfg.CONF.nova_admin_tenant_id,
                tenant_name=cfg.CONF.nova_admin_tenant_name,
                endpoint_override=endpoint_override)

        session = ks_session.Session.load_from_conf_options(
            cfg.CONF, 'nova', auth=auth)
        novaclient_cls = nclient.get_client_class(n_nova.NOVA_API_VERSION)

        self.nclient = novaclient_cls(
            session=session,
            region_name=cfg.CONF.nova.region_name)
=======
        bypass_url = "%s/%s" % (cfg.CONF.nova_url,
                                cfg.CONF.nova_admin_tenant_id)

        self.client = nclient.Client(
            username=cfg.CONF.nova_admin_username,
            api_key=cfg.CONF.nova_admin_password,
            project_id=None,
            tenant_id=cfg.CONF.nova_admin_tenant_id,
            auth_url=cfg.CONF.nova_admin_auth_url,
            cacert=cfg.CONF.nova_ca_certificates_file,
            insecure=cfg.CONF.nova_api_insecure,
            bypass_url=bypass_url,
            region_name=cfg.CONF.nova_region_name)
>>>>>>> origin

    def get_server(self, server_id):
        try:
            return self.client.servers.get(server_id)
        except nova_exceptions.NotFound:
            LOG.warning(_("Nova returned NotFound for server: %s"),
                        server_id)
        except Exception as e:
            LOG.exception(e)
