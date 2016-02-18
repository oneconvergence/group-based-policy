import os
import sys
import inspect


class LoadDrivers(object):
    def __init__(self):
        self.driver_objects = {}

    def load_drivers(self, drivers_dir):
        """
        @param drivers_dir : absolute path
        e.g drivers_dir = '/usr/lib/python2.7/dist-packages/gbpservice/
                           neutron/nsf/configurator/drivers/loadbalancer'
        """
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
                    if hasattr(class_obj, 'vendor'):
                        self.driver_objects[class_obj.vendor] = class_obj

        return self.driver_objects


