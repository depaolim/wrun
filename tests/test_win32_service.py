import os
import pydoc
import sys
import time
import threading
import unittest

try:
    import winreg
    from wrun.win32_service import WinService
except ModuleNotFoundError:
    pass

from tests.test_config import *

LOG_FILE = os.path.join(os.path.dirname(__file__), "win.log")


def log(*msgs):
    with open(LOG_FILE, "a") as fo:
        fo.write("{}.{}: {}\n".format(os.getpid(), threading.get_ident(), " - ".join(msgs)))


def log_read():
    with open(LOG_FILE) as fi:
        return fi.read()


def log_clean():
    try:
        os.remove(LOG_FILE)
    except FileNotFoundError:
        pass


class MockService:

    def __init__(self, settings_file):
        log("__init__", settings_file)
        self.settings_file = settings_file
        self.is_running = threading.Event()

    def start(self):
        log("START")
        self.is_running.set()

    def run(self):
        log("RUN begin", self.settings_file)
        while self.is_running.is_set():
            time.sleep(0.1)
            log("RUN step {}".format(self.is_running.is_set()))
        log("RUN end")

    def stop(self):
        self.is_running.clear()
        log("STOP begin")
        time.sleep(0.5)
        log("STOP end")


class TestLog(unittest.TestCase):
    def tearDown(self):
        log_clean()

    def test(self):
        log_clean()
        ms = MockService("SETTINGS")
        self.assertIn("__init__", log_read())
        ms.start()
        self.assertIn("START", log_read())

    def test_load(self):
        service_class = pydoc.locate("tests.test_win32_service.MockService")
        self.assertTrue(service_class)
        ms = service_class("SETTINGS")
        self.assertIn("__init__", log_read())
        ms.start()
        self.assertIn("START", log_read())


@unittest.skipIf(sys.platform != 'win32', "Windows Service tests need Windows")
class TestAcceptance(unittest.TestCase):
    def assertLogged(self, msg):
        self.assertIn(msg, log_read())

    def tearDown(self):
        subprocess_check_call(["sc", "stop", "wrun_test_service"], ignore_errors=True)
        subprocess_check_call(["sc", "delete", "wrun_test_service"], ignore_errors=True)
        log_clean()

    def test_install(self):
        WinService.install(MockService, "wrun_test_service", "A:\\sample_path")
        self.assertLogged("A:\\sample_path")
        reg = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)
        with winreg.OpenKey(reg, "SYSTEM\CurrentControlSet\Services\wrun_test_service\Parameters") as key:
            value, type = winreg.QueryValueEx(key, "class_path")
        self.assertEqual(value, "tests.test_win32_service.MockService")

    def test_start(self):
        WinService.install(MockService, "wrun_test_service", "A:\\sample_path")
        subprocess_check_call(["sc", "start", "wrun_test_service"])
        self.assertLogged("START\n")

    def test_stop(self):
        WinService.install(MockService, "wrun_test_service", "A:\\sample_path")
        subprocess_check_call(["sc", "start", "wrun_test_service"])
        subprocess_check_call(["sc", "stop", "wrun_test_service"])
        self.assertLogged("STOP begin\n")
        self.assertLogged("RUN end\n")
        self.assertLogged("STOP end\n")


@unittest.skipIf(sys.platform != 'win32', "Windows Service tests need Windows")
class WinServiceInstall(unittest.TestCase):
    SERVICE_NAME = "TestWRUN"

    def setUp(self):
        with open("dummy_settings.py", "w") as fo:
            fo.write("LOG_PATH = 'test_install.log'")

    def tearDown(self):
        subprocess_check_call(["sc", "delete", self.SERVICE_NAME], ignore_errors=True)
        os.remove("dummy_settings.py")

    def test_install_with_absolute_path(self):
        subprocess_check_call([sys.executable, "wrun_server.py", "install", self.SERVICE_NAME, "dummy_settings.py"])
        reg = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)
        with winreg.OpenKey(reg, "SYSTEM\CurrentControlSet\Services\TestWRUN\Parameters") as key:
            value, type = winreg.QueryValueEx(key, "settings_file")
        self.assertEqual(value, os.path.abspath("dummy_settings.py"))

