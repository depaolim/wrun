from configparser import ConfigParser
import logging
import sys
import time

import win32service
import win32serviceutil

from wrun2 import daemon, executor

log = logging.getLogger(__name__)


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
        log_path = config.get('DEFAULT', 'LOG_PATH', fallback=(self._svc_name_ + ".log"))
        logging.basicConfig(filename=log_path, level=logging.DEBUG, filemode='a')
        log.info("WRUNService.__init__ BEGIN")
        log.info("WRUNService.__init__ ini_file '%s'", ini_file)
        log.info("WRUNService.__init__ LOG_PATH '%s'", log_path)
        self.executable_path = config.get('DEFAULT', 'EXECUTABLE_PATH')
        self.port = int(config.get('DEFAULT', 'PORT'))
        win32serviceutil.ServiceFramework.__init__(self, args)
        log.info("WRUNService.__init__ END")

    def SvcDoRun(self):
        log.info("WRUNService.SvcDoRun BEGIN")
        self.ReportServiceStatus(win32service.SERVICE_START_PENDING)
        # put any start-up here
        self.ReportServiceStatus(win32service.SERVICE_RUNNING)
        daemon(("localhost", self.port), lambda command: executor(self.executable_path, command))
        log.info("WRUNService.SvcDoRun END")

    def SvcStop(self):
        log.info("WRUNService.SvcStop BEGIN")
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        # put any clean-up here
        self.ReportServiceStatus(win32service.SERVICE_STOPPED)
        log.info("WRUNService.SvcStop END")


if __name__ == '__main__':
    # Service Installation
    service_name, ini_file, = sys.argv[1:]
    serviceClassString = win32serviceutil.GetServiceClassString(WRUNService)
    win32serviceutil.InstallService(serviceClassString, service_name, service_name)
    ServiceParam(service_name).set(ini_file)