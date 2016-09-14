from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import sys
from ConfigParser import ConfigParser

import win32serviceutil

import wrun


class ServiceParam:
    def __init__(self, service_name, param_name="ini_file"):
        self.service_name = service_name
        self.param_name = param_name

    def get(self):
        return win32serviceutil.GetServiceCustomOption(self.service_name, self.param_name)

    def set(self, value):
        win32serviceutil.SetServiceCustomOption(self.service_name, self.param_name, value)


class WRUNService(win32serviceutil.ServiceFramework):

    def __init__(self, args):
        self._svc_name_, = args
        ini_file = ServiceParam(self._svc_name_).get()
        config = ConfigParser()
        config.read(ini_file)
        self.executable_path = config.get('DEFAULT', 'EXECUTABLE_PATH')
        self.port = config.get('DEFAULT', 'PORT')
        win32serviceutil.ServiceFramework.__init__(self, args)

    def SvcDoRun(self):
        self.service = wrun.Server(self.executable_path, self.port)
        self.service.start()

    def SvcStop(self):
        self.service.stop()


if __name__ == '__main__':
    # Service Installation
    service_name, ini_file, = sys.argv[1:]
    serviceClassString = win32serviceutil.GetServiceClassString(WRUNService)
    win32serviceutil.InstallService(serviceClassString, service_name, service_name)
    ServiceParam(service_name).set(ini_file)
