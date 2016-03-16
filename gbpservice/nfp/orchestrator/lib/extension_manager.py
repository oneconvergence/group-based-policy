from neutron.common import exceptions as n_exc
from oslo_config import cfg
from oslo_log import log as logging
import stevedore

cfg.CONF.register_opt(cfg.StrOpt('drivers'),
                      'oneconvergence_orchestration_drivers')

LOG = logging.getLogger(__name__)


class ExtensionManager(stevedore.named.NamedExtensionManager):
    """

    """

    def __init__(self, sc_context, conf):
        super(ExtensionManager, self).__init__(
            'gbpservice.nfp.orchestrator.drivers',
            cfg.CONF.oneconvergence_orchestration_drivers.drivers,
            invoke_on_load=True,
            invoke_args=(sc_context, conf))
        self.drivers = dict()
        LOG.debug(_("Loaded extension driver names: %s"), self.names())
        self._register_drivers()

    def _register_drivers(self):
        """Register all extension drivers.

        This method should only be called once in the ExtensionManager
        constructor.
        """
        for ext in self:
            # self.ordered_ext_drivers.append(ext)
            driver_type = ext.name
            if driver_type in self.drivers:
                pass
            else:
                self.drivers[driver_type] = ext.obj

    def initialize(self):
        for _, driver in self.drivers.iteritems():
            # LOG.debug(_("Initializing extension driver '%s'"), driver.name)
            driver.obj.initialize()

