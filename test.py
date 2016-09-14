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


class AcceptanceSecureTest(unittest.TestCase):
    def setUp(self):
        self.daemon = subprocess.Popen(
            ["python", "wrun.py", EXECUTABLE_PATH, PORT, "--hmackey", HMACKEY])
        time.sleep(0.1)

    def tearDown(self):
        self.daemon.terminate()

    def test_cant_comunicate_without_hmackey(self):
        client = wrun.Client(HOST_NAME, PORT)
        self.assertRaises(wrun.CommunicationError, client.run, EXECUTABLE_NAME, "P1")

    def test_cant_comunicate_with_wrong_hmackey(self):
        client = wrun.Client(HOST_NAME, PORT, "wronghmackey")
        self.assertRaises(wrun.CommunicationError, client.run, EXECUTABLE_NAME, "P1")

    def test_cant_comunicate_only_with_hmackey(self):
        client = wrun.Client(HOST_NAME, PORT, HMACKEY)
        result = client.run(EXECUTABLE_NAME, "P1")
        expected = os.linesep.join([EXECUTABLE_PATH, "hello P1", ""])
        self.assertEqual(result, expected)


@unittest.skipIf(sys.platform != 'win32', "only on Win platforms")
class WinServiceTest(unittest.TestCase):
    SERVICE_NAME = 'TestWRUN'
    
    def setUp(self):
        self.ini_file = os.path.join(CWD, "test.ini")
        write_config(self.ini_file, EXECUTABLE_PATH=EXECUTABLE_PATH, PORT=PORT)
        subprocess.check_call(["python", "win_service.py", self.SERVICE_NAME, self.ini_file])
        subprocess.check_call(["sc", "start", self.SERVICE_NAME])

    def tearDown(self):
        subprocess.check_call(["sc", "stop", self.SERVICE_NAME])
        subprocess.check_call(["sc", "delete", self.SERVICE_NAME])
        os.remove(self.ini_file)

    def test(self):
        # execute
        client = wrun.Client(HOST_NAME, PORT)
        result = client.run(EXECUTABLE_NAME, "P1")
        expected = os.linesep.join([EXECUTABLE_PATH, "hello P1", ""])
        self.assertEqual(result, expected)
        # !!! check log


@unittest.skipIf(sys.platform != 'win32', "only on Win platforms")
class DoubleWinServiceTest(unittest.TestCase):
    def setUp(self):
        self.ini_1 = os.path.join(CWD, "test_1.ini")
        self.ini_2 = os.path.join(CWD, "test_2.ini")
        write_config(
            self.ini_1,
            EXECUTABLE_PATH=os.path.join(CWD, "test_executables"), PORT="3331", HMACKEY=HMACKEY)
        write_config(
            self.ini_2,
            EXECUTABLE_PATH=os.path.join(CWD, "test_executables_2"), PORT="3332")

    def tearDown(self):
        subprocess.check_call(["sc", "stop", "TestWRUN1"])
        subprocess.check_call(["sc", "stop", "TestWRUN2"])
        subprocess.check_call(["sc", "delete", "TestWRUN1"])
        subprocess.check_call(["sc", "delete", "TestWRUN2"])
        os.remove(self.ini_1)
        os.remove(self.ini_2)

    def test(self):
        subprocess.check_call(["python", "win_service.py", "TestWRUN1", self.ini_1])
        subprocess.check_call(["python", "win_service.py", "TestWRUN2", self.ini_2])
        subprocess.check_call(["sc", "start", "TestWRUN1"])
        subprocess.check_call(["sc", "start", "TestWRUN2"])
        self.assertRaises(
            wrun.CommunicationError,
            wrun.Client(HOST_NAME, "3331").run, EXECUTABLE_NAME, "P1")
        self.assertEqual(
            wrun.Client(HOST_NAME, "3331", HMACKEY).run(EXECUTABLE_NAME, "P1"),
            os.linesep.join([os.path.join(CWD, "test_executables"), "hello P1", ""]))
        self.assertEqual(
            wrun.Client(HOST_NAME, "3332").run(EXECUTABLE_NAME, "P1"),
            os.linesep.join([os.path.join(CWD, "test_executables_2"), "mandi P1", ""]))


if __name__ == '__main__':
    unittest.main()
