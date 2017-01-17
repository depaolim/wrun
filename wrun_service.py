import logging
import sys

import win32service
import win32serviceutil

from wrun import Config, daemon, executor

log = logging.getLogger(__name__)


class ServiceParam:
    def __init__(self, service_name, param_name="settings_file"):
        self.service_name = service_name
        self.param_name = param_name

    def get(self):
        return win32serviceutil.GetServiceCustomOption(self.service_name, self.param_name)

    def set(self, value):
        win32serviceutil.SetServiceCustomOption(self.service_name, self.param_name, value)


class WRUNService(win32serviceutil.ServiceFramework):

    def __init__(self, args):
        self._svc_name_, = args
        settings_file = ServiceParam(self._svc_name_).get()
        self.settings = Config(settings_file)
        log.info("WRUNService.__init__ BEGIN")
        win32serviceutil.ServiceFramework.__init__(self, args)
        log.info("WRUNService.__init__ END")

    def SvcDoRun(self):
        log.info("WRUNService.SvcDoRun BEGIN")
        self.ReportServiceStatus(win32service.SERVICE_START_PENDING)
        # put any start-up code here
        self.ReportServiceStatus(win32service.SERVICE_RUNNING)
        s = self.settings
        daemon((s.HOST, s.PORT), lambda command: executor(s.EXECUTABLE_PATH, command))
        log.info("WRUNService.SvcDoRun END")

    def SvcStop(self):
        log.info("WRUNService.SvcStop BEGIN")
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        # put any clean-up code here
        self.ReportServiceStatus(win32service.SERVICE_STOPPED)
        log.info("WRUNService.SvcStop END")


if __name__ == '__main__':
    # Service Installation
    service_name, settings_file, = sys.argv[1:]
    Config(settings_file)
    serviceClassString = win32serviceutil.GetServiceClassString(WRUNService)
    win32serviceutil.InstallService(serviceClassString, service_name, service_name)
    ServiceParam(service_name).set(settings_file)
