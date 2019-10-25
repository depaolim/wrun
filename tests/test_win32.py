import json
import unittest

from wrun import Config, client

from tests.test_config import *


class WinServiceTestBase(LogTestMixin, unittest.TestCase):
    SERVICE_NAME = 'TestWRUN'
    PORT = 3333
    CONFIG = {
        "EXECUTABLE_PATH": EXECUTABLE_PATH,
        "HOST": "localhost",
        "PORT": PORT,
    }

    def assertJsonEqual(self, result, **kwargs):
        self.assertEqual(json.loads(result), kwargs)

    def setUp(self):
        config = dict(self.CONFIG)
        config["LOG_PATH"] = self.initLog("win_service")
        self.settings_file = os.path.join(CWD, "settings_test.py")
        Config.store(self.settings_file, **config)
        subprocess_check_call([sys.executable, "wrun_server.py", "install", self.SERVICE_NAME, self.settings_file])

    def tearDown(self):
        subprocess_check_call(["sc", "stop", self.SERVICE_NAME], ignore_errors=True)
        subprocess_check_call(["sc", "delete", self.SERVICE_NAME], ignore_errors=True)
        os.remove(self.settings_file)


@unittest.skipIf(sys.platform != 'win32', "Windows Service tests need Windows")
class WinServiceTest(WinServiceTestBase):
    def test_start(self):
        subprocess_check_call(["sc", "start", self.SERVICE_NAME])
        self.assertLogContains("win_service", "INFO:wrun:settings \"{'")
        self.assertLogContains("win_service", "INFO:wrun.win32_service:WinService.__init__ BEGIN")
        self.assertLogContains("win_service", "INFO:wrun.win32_service:WinService.SvcDoRun BEGIN")

    def test_stop(self):
        subprocess_check_call(["sc", "start", self.SERVICE_NAME])
        subprocess_check_call(["sc", "stop", self.SERVICE_NAME])
        self.assertLogContains("win_service", "INFO:wrun.win32_service:WinService.SvcStop BEGIN")
        self.assertLogContains("win_service", "INFO:wrun.win32_service:WinService.SvcStop END")

    def test_client_connection_error(self):
        self.assertRaises(Exception, client, ("localhost", self.PORT), "NO_MATTER")

    def test_client_request(self):
        subprocess_check_call(["sc", "start", self.SERVICE_NAME])
        result = client(("localhost", self.PORT), json.dumps([EXECUTABLE_NAME, ["P1"], ""]))
        self.assertJsonEqual(result, stdout=os.linesep.join([EXECUTABLE_PATH, "hello P1", ""]), returncode=0)

    def test_client_request_error(self):
        subprocess_check_call(["sc", "start", self.SERVICE_NAME])
        result = client(("localhost", self.PORT), json.dumps([EXECUTABLE_NAME, ["ERROR"], ""]))
        self.assertJsonEqual(result, stdout=os.linesep.join([EXECUTABLE_PATH, ""]), returncode=1)


@unittest.skipIf(sys.platform != 'win32', "Windows Service tests need Windows")
class WinServiceSecureTest(WinServiceTestBase):
    CONFIG = {
        **WinServiceTestBase.CONFIG,
        "SECURE": {
            "cafile": os.path.join(SSL_PATH, "server.crt"),
            "keyfile": os.path.join(SSL_PATH, "server.key"),
        }
    }

    def test_start(self):
        subprocess_check_call(["sc", "start", self.SERVICE_NAME])
        self.assertLogContains("win_service", "INFO:wrun:settings \"{'")
        self.assertLogContains("win_service", "INFO:wrun.win32_service:WinService.__init__ BEGIN")
        self.assertLogContains("win_service", "INFO:wrun.win32_service:WinService.SvcDoRun BEGIN")

    def test_stop(self):
        subprocess_check_call(["sc", "start", self.SERVICE_NAME])
        subprocess_check_call(["sc", "stop", self.SERVICE_NAME])
        self.assertLogContains("win_service", "INFO:wrun.win32_service:WinService.SvcStop BEGIN")
        self.assertLogContains("win_service", "INFO:wrun.win32_service:WinService.SvcStop END")

    def test_client_request(self):
        subprocess_check_call(["sc", "start", self.SERVICE_NAME])
        result = client(
            ("localhost", self.PORT), json.dumps([EXECUTABLE_NAME, ["P1"], ""]),
            cafile=os.path.join(SSL_PATH, "server.crt"))
        self.assertJsonEqual(result, stdout=os.linesep.join([EXECUTABLE_PATH, "hello P1", ""]), returncode=0)


@unittest.skipIf(sys.platform != 'win32', "Windows Service tests need Windows")
class WinServiceTestWithStderr(WinServiceTestBase):
    def setUp(self):
        log_path = self.initLog("win_service")
        self.settings_file = os.path.join(CWD, "settings_test.py")
        Config.store(
            self.settings_file, LOG_PATH=log_path, COLLECT_STDERR=True,
            EXECUTABLE_PATH=EXECUTABLE_PATH, HOST="localhost", PORT=self.PORT)
        subprocess_check_call([sys.executable, "wrun_server.py", "install", self.SERVICE_NAME, self.settings_file])

    def test_client_request_error(self):
        subprocess_check_call(["sc", "start", self.SERVICE_NAME])
        result = client(("localhost", self.PORT), json.dumps([EXECUTABLE_NAME, ["ERROR"], ""]))
        self.assertJsonEqual(
            result, stdout=os.linesep.join([EXECUTABLE_PATH, ""]),
            stderr=os.linesep.join(["err_msg ERROR ", ""]), returncode=1)


@unittest.skipIf(sys.platform != 'win32', "Windows Service tests need Windows")
class DoubleWinServiceTest(LogTestMixin, unittest.TestCase):
    EXECUTABLE_PATH_2 = os.path.join(CWD, "test_executables_2")

    def assertJsonEqual(self, result, **kwargs):
        self.assertEqual(json.loads(result), kwargs)

    def setUp(self):
        log_path_1 = self.initLog("win_service_1")
        log_path_2 = self.initLog("win_service_2")
        self.settings_file_1 = os.path.join(CWD, "settings_test_1.py")
        Config.store(
            self.settings_file_1, LOG_PATH=log_path_1,
            EXECUTABLE_PATH=EXECUTABLE_PATH, HOST="localhost", PORT=3333)
        self.settings_file_2 = os.path.join(CWD, "settings_test_2.py")
        Config.store(
            self.settings_file_2, LOG_PATH=log_path_2,
            EXECUTABLE_PATH=self.EXECUTABLE_PATH_2, HOST="localhost", PORT=3334)
        subprocess_check_call([sys.executable, "wrun_server.py", "install", "TestWRUN_1", self.settings_file_1])
        subprocess_check_call([sys.executable, "wrun_server.py", "install", "TestWRUN_2", self.settings_file_2])

    def tearDown(self):
        subprocess_check_call(["sc", "stop", "TestWRUN_1"], ignore_errors=True)
        subprocess_check_call(["sc", "delete", "TestWRUN_1"], ignore_errors=True)
        subprocess_check_call(["sc", "stop", "TestWRUN_2"], ignore_errors=True)
        subprocess_check_call(["sc", "delete", "TestWRUN_2"], ignore_errors=True)
        os.remove(self.settings_file_1)
        os.remove(self.settings_file_2)

    def test_double_client_request(self):
        subprocess_check_call(["sc", "start", "TestWRUN_1"])
        subprocess_check_call(["sc", "start", "TestWRUN_2"])
        result_1 = client(("localhost", 3333), json.dumps([EXECUTABLE_NAME, ["P1"], ""]))
        self.assertJsonEqual(result_1, stdout=os.linesep.join([EXECUTABLE_PATH, "hello P1", ""]), returncode=0)
        result_2 = client(("localhost", 3334), json.dumps([EXECUTABLE_NAME, ["P1"], ""]))
        self.assertJsonEqual(result_2, stdout=os.linesep.join([self.EXECUTABLE_PATH_2, "mandi P1", ""]), returncode=0)
