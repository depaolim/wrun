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
        config = Config(settings_file)
        log_path = getattr(config, 'LOG_PATH', self._svc_name_ + ".log")
        logging.basicConfig(filename=log_path, level=logging.DEBUG, filemode='a')
        log.info("WRUNService.__init__ BEGIN")
        log.info("settings_file '%s'", settings_file)
        log.info("param LOG_PATH '%s'", log_path)
        self.executable_path = config.EXECUTABLE_PATH
        log.info("param EXECUTABLE_PATH '%s'", self.executable_path)
        self.host = getattr(config, 'HOST', "localhost")
        log.info("param HOST '%s'", self.host)
        self.port = config.PORT
        log.info("param PORT '%s'", self.port)
        win32serviceutil.ServiceFramework.__init__(self, args)
        log.info("WRUNService.__init__ END")

    def SvcDoRun(self):
        log.info("WRUNService.SvcDoRun BEGIN")
        self.ReportServiceStatus(win32service.SERVICE_START_PENDING)
        # put any start-up code here
        self.ReportServiceStatus(win32service.SERVICE_RUNNING)
        daemon((self.host, self.port), lambda command: executor(self.executable_path, command))
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
    serviceClassString = win32serviceutil.GetServiceClassString(WRUNService)
    win32serviceutil.InstallService(serviceClassString, service_name, service_name)
    ServiceParam(service_name).set(settings_file)
