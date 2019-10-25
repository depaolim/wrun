import logging
import os
import pickle
import pydoc


import win32service
import win32serviceutil

log = logging.getLogger(__name__)


def get_class_path(cls):
    module_name = pickle.whichmodule(cls, cls.__name__)
    return module_name + "." + cls.__name__


class WinService(win32serviceutil.ServiceFramework):
    SETTINGS_FILE_PARAM = "settings_file"
    CLASS_PATH_PARAM = "class_path"

    @classmethod
    def log(cls, msg):
        log.info("%s.%s", cls.__name__, msg)

    def __init__(self, args):
        self._svc_name_, = args
        settings_file = win32serviceutil.GetServiceCustomOption(self._svc_name_, self.SETTINGS_FILE_PARAM)
        service_class_path = win32serviceutil.GetServiceCustomOption(self._svc_name_, self.CLASS_PATH_PARAM)
        service_class = pydoc.locate(service_class_path)
        self.service = service_class(settings_file)
        self.log("__init__ BEGIN")
        super().__init__(args)
        self.log("__init__ END")

    def SvcDoRun(self):
        self.log("SvcDoRun BEGIN")
        self.ReportServiceStatus(win32service.SERVICE_START_PENDING)
        self.service.start()
        self.ReportServiceStatus(win32service.SERVICE_RUNNING)
        self.service.run()
        self.log("SvcDoRun END")

    def SvcStop(self):
        self.log("SvcStop BEGIN")
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.service.stop()
        self.ReportServiceStatus(win32service.SERVICE_STOPPED)
        self.log("SvcStop END")

    @classmethod
    def install(cls, service_class, service_name, settings_file):
        settings_file = os.path.abspath(settings_file)
        service_class_path = get_class_path(service_class)
        service_class(settings_file)  # validate settings
        win32serviceutil.InstallService(get_class_path(cls), service_name, service_name)
        win32serviceutil.SetServiceCustomOption(service_name, cls.SETTINGS_FILE_PARAM, settings_file)
        win32serviceutil.SetServiceCustomOption(service_name, cls.CLASS_PATH_PARAM, service_class_path)
