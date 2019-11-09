import json
import time
import unittest

from wrun import Config, client

from tests.config import *


class TestTwoServers(LogTestMixin, unittest.TestCase):
    EXECUTABLE_PATH_2 = os.path.join(CWD, "test_executables_2")

    def assertJsonEqual(self, result, **kwargs):
        self.assertEqual(json.loads(result), kwargs)

    def setUp(self):
        log_path_1 = self._log_path("server_1")
        log_path_2 = self._log_path("server_2")
        self.settings_file_1 = os.path.join(CWD, "settings_test_1.py")
        Config.store(
            self.settings_file_1, LOG_PATH=log_path_1,
            EXECUTABLE_PATH=EXECUTABLE_PATH, HOST="localhost", PORT=3333)
        self.settings_file_2 = os.path.join(CWD, "settings_test_2.py")
        Config.store(
            self.settings_file_2, LOG_PATH=log_path_2,
            EXECUTABLE_PATH=self.EXECUTABLE_PATH_2, HOST="localhost", PORT=3334)
        self.proc_1 = subprocess.Popen([sys.executable, "wrun_server.py", "run", self.settings_file_1])
        self.proc_2 = subprocess.Popen([sys.executable, "wrun_server.py", "run", self.settings_file_2])

    def tearDown(self):
        self.proc_1.kill()
        self.proc_1.wait()
        self.proc_2.kill()
        self.proc_2.wait()
        os.remove(self.settings_file_1)
        os.remove(self.settings_file_2)
        os_remove(os.path.join(CWD, "test_server_1.log"))
        os_remove(os.path.join(CWD, "test_server_2.log"))

    def test_double_client_request(self):
        time.sleep(0.5)
        result_1 = client(("localhost", 3333), json.dumps([EXECUTABLE_NAME, ["P1"], ""]))
        self.assertJsonEqual(result_1, stdout=os.linesep.join([EXECUTABLE_PATH, "hello P1", ""]), returncode=0)
        result_2 = client(("localhost", 3334), json.dumps([EXECUTABLE_NAME, ["P1"], ""]))
        self.assertJsonEqual(result_2, stdout=os.linesep.join([self.EXECUTABLE_PATH_2, "mandi P1", ""]), returncode=0)
