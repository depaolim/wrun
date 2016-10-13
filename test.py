from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

from ConfigParser import ConfigParser
import os
import socket
import subprocess
import sys
import time
import unittest

try:
    import win32serviceutil  # noqa
    pywin32_installed = True
except ImportError:
    pywin32_installed = False

import wrun

if sys.platform == 'win32':
    EXECUTABLE_NAME = "sample.bat"
else:
    EXECUTABLE_NAME = "sample.sh"

CWD = os.path.dirname(os.path.realpath(__file__))
EXECUTABLE_PATH = os.path.join(CWD, "test_executables")
HOST_NAME = socket.gethostname()
PORT = "3333"
HMACKEY = "supersecret"


def write_config(filepath, **kwargs):
    config = ConfigParser()
    for k, v in kwargs.items():
        config.set('DEFAULT', k, v)
    with open(filepath, "w") as f:
        config.write(f)


class LogTestMixin(object):
    LOG_PATH = "wrun.log"

    def _del_log(self):
        try:
            os.remove(self.LOG_PATH)
        except OSError:
            pass

    def _get_log(self):
        with open(self.LOG_PATH) as f:
            return f.read()

    def setUp(self):
        super(LogTestMixin, self).setUp()
        self._del_log()

    def tearDown(self):
        super(LogTestMixin, self).tearDown()
        self._del_log()

    def assertLogContains(self, expected):
        self.assertIn(expected, self._get_log())


class ProcessTestMixin(object):
    def setUp(self):
        super(ProcessTestMixin, self).setUp()
        self.ps = []

    def tearDown(self):
        super(ProcessTestMixin, self).tearDown()
        for p in self.ps:
            p.terminate()

    def run_process(self, *args):
        p = subprocess.Popen(args)
        self.ps.append(p)
        time.sleep(0.1)
        return len(self.ps) - 1

    def stop_process(self, idx):
        p = self.ps.pop(idx)
        p.terminate()
        time.sleep(0.1)


class LogTest(LogTestMixin, ProcessTestMixin, unittest.TestCase):
    def test_start(self):
        self.run_process("python", "wrun.py", EXECUTABLE_PATH, PORT)
        self.assertLogContains("Server starting")

    def test_stop(self):
        p_idx = self.run_process("python", "wrun.py", EXECUTABLE_PATH, PORT)
        self.stop_process(p_idx)
        self.assertLogContains("Server stopped")


class AcceptanceTest(LogTestMixin, ProcessTestMixin, unittest.TestCase):
    def setUp(self):
        super(AcceptanceTest, self).setUp()
        self.run_process("python", "wrun.py", EXECUTABLE_PATH, PORT)
        self.client = wrun.Client(HOST_NAME, PORT)

    def test_execute_with_param_P1(self):
        result = self.client.run(EXECUTABLE_NAME, "P1")
        expected = os.linesep.join([EXECUTABLE_PATH, "hello P1", ""])
        self.assertEqual(result, expected)

    def test_execute_with_param_P2(self):
        result = self.client.run(EXECUTABLE_NAME, "P2")
        expected = os.linesep.join([EXECUTABLE_PATH, "hello P2", ""])
        self.assertEqual(result, expected)

    def test_logging_P1(self):
        self.client.run(EXECUTABLE_NAME, "P1")
        self.assertLogContains("P1")

    def test_logging_P2(self):
        self.client.run(EXECUTABLE_NAME, "P2")
        self.assertLogContains("P2")


class AcceptanceSecureTest(ProcessTestMixin, unittest.TestCase):
    def setUp(self):
        super(AcceptanceSecureTest, self).setUp()
        self.run_process("python", "wrun.py", EXECUTABLE_PATH, PORT, "--hmackey", HMACKEY)

    def test_can_not_comunicate_without_hmackey(self):
        client = wrun.Client(HOST_NAME, PORT)
        self.assertRaises(
            wrun.CommunicationError, client.run, EXECUTABLE_NAME, "P1")

    def test_can_not_comunicate_with_wrong_hmackey(self):
        client = wrun.Client(HOST_NAME, PORT, "wronghmackey")
        self.assertRaises(
            wrun.CommunicationError, client.run, EXECUTABLE_NAME, "P1")

    def test_can_comunicate_only_with_correct_hmackey(self):
        client = wrun.Client(HOST_NAME, PORT, HMACKEY)
        result = client.run(EXECUTABLE_NAME, "P1")
        expected = os.linesep.join([EXECUTABLE_PATH, "hello P1", ""])
        self.assertEqual(result, expected)


@unittest.skipIf(not pywin32_installed, "only with PyWin32 installed")
class WinServiceTest(unittest.TestCase):
    SERVICE_NAME = 'TestWRUN'

    def setUp(self):
        self.ini_file = os.path.join(CWD, "test.ini")
        write_config(self.ini_file, EXECUTABLE_PATH=EXECUTABLE_PATH, PORT=PORT)
        subprocess.check_call(
            ["python", "win_service.py", self.SERVICE_NAME, self.ini_file])
        subprocess.check_call(["sc", "start", self.SERVICE_NAME])

    def tearDown(self):
        subprocess.check_call(["sc", "stop", self.SERVICE_NAME])
        subprocess.check_call(["sc", "delete", self.SERVICE_NAME])
        os.remove(self.ini_file)

    def test(self):
        client = wrun.Client(HOST_NAME, PORT)
        result = client.run(EXECUTABLE_NAME, "P1")
        expected = os.linesep.join([EXECUTABLE_PATH, "hello P1", ""])
        self.assertEqual(result, expected)
        # !!! check log


@unittest.skipIf(not pywin32_installed, "only with PyWin32 installed")
class DoubleWinServiceTest(unittest.TestCase):
    def setUp(self):
        self.ini_1 = os.path.join(CWD, "test_1.ini")
        self.ini_2 = os.path.join(CWD, "test_2.ini")
        write_config(
            self.ini_1,
            EXECUTABLE_PATH=os.path.join(CWD, "test_executables"),
            PORT="3331", HMACKEY=HMACKEY)
        write_config(
            self.ini_2,
            EXECUTABLE_PATH=os.path.join(CWD, "test_executables_2"),
            PORT="3332")

    def tearDown(self):
        subprocess.check_call(["sc", "stop", "TestWRUN1"])
        subprocess.check_call(["sc", "stop", "TestWRUN2"])
        subprocess.check_call(["sc", "delete", "TestWRUN1"])
        subprocess.check_call(["sc", "delete", "TestWRUN2"])
        os.remove(self.ini_1)
        os.remove(self.ini_2)

    def test(self):
        subprocess.check_call(
            ["python", "win_service.py", "TestWRUN1", self.ini_1])
        subprocess.check_call(
            ["python", "win_service.py", "TestWRUN2", self.ini_2])
        subprocess.check_call(
            ["sc", "start", "TestWRUN1"])
        subprocess.check_call(["sc", "start", "TestWRUN2"])
        self.assertRaises(
            wrun.CommunicationError,
            wrun.Client(HOST_NAME, "3331").run, EXECUTABLE_NAME, "P1")
        self.assertEqual(
            wrun.Client(HOST_NAME, "3331", HMACKEY).run(EXECUTABLE_NAME, "P1"),
            os.linesep.join(
                [os.path.join(CWD, "test_executables"), "hello P1", ""]))
        self.assertEqual(
            wrun.Client(HOST_NAME, "3332").run(EXECUTABLE_NAME, "P1"),
            os.linesep.join(
                [os.path.join(CWD, "test_executables_2"), "mandi P1", ""]))


if __name__ == '__main__':
    unittest.main()
