import os
import sys
import inspect


class ConfiguratorUtils(object):
    def __init__(self):
        pass

    def load_drivers(self, drivers_dir):

        """
        @param drivers_dir : absolute path
        e.g drivers_dir = '/usr/lib/python2.7/dist-packages/gbpservice/
                           neutron/nsf/configurator/drivers/loadbalancer'
        """
        driver_objects = {}
        modules = []
        subdirectories = [x[0] for x in os.walk(drivers_dir)]
        for subd in subdirectories:
            syspath = sys.path
            sys.path = [subd] + syspath
            try:
                files = os.listdir(subd)
            except OSError:
                print "Failed to read files"
                files = []

            for fname in files:
                if fname.endswith(".py") and fname != '__init__.py':
                    modules += [__import__(fname[:-3])]
            sys.path = syspath

        for module in modules:
            for name, class_obj in inspect.getmembers(module):
                if inspect.isclass(class_obj):
                    key = ''
                    if hasattr(class_obj, 'service_type'):
                        key += class_obj.service_type
                    if hasattr(class_obj, 'vendor'):
                        key += class_obj.vendor
                    if key:
                        driver_objects[key] = class_obj

        return driver_objects

    def load_agents(self, pkg):
        """
        @param pkg : package
        e.g pkg = 'gbpservice.neutron.nsf.configurator.agents'
        """
        imported_service_agents = []
        base_agent = __import__(pkg,
                                globals(), locals(), ['agents'], -1)
        agents_dir = base_agent.__path__[0]
        syspath = sys.path
        sys.path = [agents_dir] + syspath
        try:
            files = os.listdir(agents_dir)
        except OSError:
            print "Failed to read files"
            files = []

        for fname in files:
            if fname.endswith(".py") and fname != '__init__.py':
                agent = __import__(pkg, globals(),
                                   locals(), [fname[:-3]], -1)
                imported_service_agents += [
                                eval('agent.%s' % (fname[:-3]))]
                # modules += [__import__(fname[:-3])]
        sys.path = syspath
        return imported_service_agents
