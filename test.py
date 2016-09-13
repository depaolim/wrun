from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import os
import socket
import subprocess
import sys
import time
import unittest

import wrun

if sys.platform == 'win32':
    EXECUTABLE_NAME = "sample.bat"
else:
    EXECUTABLE_NAME = "sample.sh"

CWD = os.path.dirname(os.path.realpath(__file__))
EXECUTABLE_PATH = os.path.join(CWD, "test_executables")
HOST_NAME = socket.gethostname()
PORT = "3333"


class AcceptanceTest(unittest.TestCase):
    def setUp(self):
        self.daemon = subprocess.Popen(
            ["python", "wrun.py", EXECUTABLE_PATH, PORT])
        time.sleep(0.1)
        self.client = wrun.Client(HOST_NAME, PORT)

    def tearDown(self):
        self.daemon.terminate()

    def test_execute_with_param_P1(self):
        result = self.client.run(EXECUTABLE_NAME, "P1")
        expected = os.linesep.join([EXECUTABLE_PATH, "hello P1", ""])
        self.assertEqual(result, expected)

    def test_execute_with_param_P2(self):
        result = self.client.run(EXECUTABLE_NAME, "P2")
        expected = os.linesep.join([EXECUTABLE_PATH, "hello P2", ""])
        self.assertEqual(result, expected)


@unittest.skipIf(sys.platform != 'win32', "only on Win platforms")
class WinServiceTest(unittest.TestCase):
    def setUp(self):
        subprocess.check_call(["python", "win_service.py", "install"])
        subprocess.check_call(["python", "win_service.py", "start"])

    def tearDown(self):
        subprocess.check_call(["python", "win_service.py", "stop"])
        subprocess.check_call(["python", "win_service.py", "remove"])

    def test(self):
        # execute
        client = wrun.Client(HOST_NAME, PORT)
        result = client.run(EXECUTABLE_NAME, "P1")
        expected = os.linesep.join([EXECUTABLE_PATH, "hello P1", ""])
        self.assertEqual(result, expected)
        # !!! check log


if __name__ == '__main__':
    unittest.main()
