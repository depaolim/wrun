from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import os
from ConfigParser import ConfigParser

import win32serviceutil
import win32service

import wrun

CWD = os.path.dirname(os.path.realpath(__file__))
config = ConfigParser()
config.read(os.path.join(CWD, "test.ini"))
SERVICE_NAME = config.get('DEFAULT', 'SERVICE_NAME')
EXECUTABLE_PATH = config.get('DEFAULT', 'EXECUTABLE_PATH')
PORT = config.get('DEFAULT', 'PORT')


class WRUNService(win32serviceutil.ServiceFramework):
    _svc_name_ = SERVICE_NAME
    _svc_display_name_ = SERVICE_NAME

    def SvcDoRun(self):
        self.ReportServiceStatus(win32service.SERVICE_START_PENDING)
        self.service = wrun.Server(EXECUTABLE_PATH, PORT)
        self.ReportServiceStatus(win32service.SERVICE_RUNNING)
        self.service.start()

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.service.stop()
        self.ReportServiceStatus(win32service.SERVICE_STOPPED)


if __name__ == '__main__':
    win32serviceutil.HandleCommandLine(WRUNService)
