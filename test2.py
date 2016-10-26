import configparser
import json
import logging
import multiprocessing
import os
import signal
import subprocess
import sys
import time
import unittest

from wrun2 import client, daemon, executor

if sys.platform == 'win32':
    EXECUTABLE_NAME = "sample.bat"
else:
    EXECUTABLE_NAME = "sample.sh"

CWD = os.path.dirname(os.path.realpath(__file__))
EXECUTABLE_PATH = os.path.join(CWD, "test_executables")


class LogTestMixin(object):
    CWD = CWD

    @staticmethod
    def _get_log(path):
        with open(path) as f:
            return f.read()

    @classmethod
    def _log_path(cls, action):
        if not isinstance(action, str):
            action = action.__name__
        return os.path.join(cls.CWD, "test_" + action + ".log")

    @staticmethod
    def _init_log_file(path):
        logging.basicConfig(filename=path, level=logging.DEBUG, filemode='a')
        logging.FileHandler(path, mode='w').close()  # log cleanup

    @classmethod
    def logged_func(cls, func, *args):
        cls._init_log_file(cls._log_path(func))
        return func(*args)

    def initLog(self, action):
        path = self._log_path(action)
        self._init_log_file(path)
        return path

    def assertLogContains(self, action, expected):
        path = self._log_path(action)
        self.assertIn(expected, self._get_log(path))


class ProcessFunc(object):
    def _kill(self):
        if sys.platform == 'win32':
            self._process.terminate()
        else:
            os.kill(self._process.pid, signal.SIGINT)

    @staticmethod
    def _target(q, f, args):
        q.put(f(*args))

    def __init__(self, func, *args):
        self._queue = multiprocessing.Queue()
        self._process = multiprocessing.Process(target=self._target, args=(self._queue, func, args))
        self._process.start()
        time.sleep(0.5)

    def join(self):
        self._process.join()

    def stop(self, ignore_errors=False):
        if not ignore_errors or self._process.is_alive():
            self._kill()
        self.join()

    @property
    def result(self):
        return self._queue.get()


class TestCommunication(LogTestMixin, unittest.TestCase):
    SERVER_ADDRESS = ('localhost', 3333)

    def _run_process_func(self, func, *args):
        return ProcessFunc(self.logged_func, func, *args)


class TestClientServer(TestCommunication):
    @staticmethod
    def revert(request):
        return request[::-1]

    def setUp(self):
        self.s = self._run_process_func(daemon, self.SERVER_ADDRESS, self.revert)

    def tearDown(self):
        self.s.stop(ignore_errors=True)

    def test_server_is_listening(self):
        self.assertLogContains(daemon, "waiting for a connection...")

    @unittest.skipIf(sys.platform == 'win32', "no clean shutdown on Windows")
    def test_server_shutdown(self):
        self.s.stop()
        self.assertLogContains(daemon, "closing server socket...")
        self.assertLogContains(daemon, "closed server socket")

    def test_client_request(self):
        c = self._run_process_func(client, self.SERVER_ADDRESS, "prova")
        c.join()
        self.assertEqual(c.result, "avorp")
        self.assertLogContains(client, "CLIENT: connecting '('localhost', 3333)' ...")
        self.assertLogContains(client, "CLIENT: connected")
        self.assertLogContains(client, "CLIENT: sending 'prova'")
        self.assertLogContains(client, "CLIENT: sent")
        self.assertLogContains(client, "CLIENT: receiving...")
        self.assertLogContains(daemon, "SERVER: connection from ('127.0.0.1', ")
        self.assertLogContains(daemon, "SERVER: receiving...")
        self.assertLogContains(daemon, "SERVER: received b'prova'")
        self.assertLogContains(daemon, "SERVER: received b''")
        self.assertLogContains(daemon, "SERVER: no more data to receive")
        self.assertLogContains(daemon, "SERVER: sending 'avorp'")
        self.assertLogContains(daemon, "SERVER: sent")
        self.assertLogContains(daemon, "SERVER: closing client socket")
        self.assertLogContains(daemon, "SERVER: closed client socket")
        self.assertLogContains(client, "CLIENT: received b'avorp'")
        self.assertLogContains(client, "CLIENT: received b''")
        self.assertLogContains(client, "CLIENT: no more data to receive")
        self.assertLogContains(client, "CLIENT: closing")
        self.assertLogContains(client, "CLIENT: closed")


class TestExecutor(unittest.TestCase):
    def test_run_P1(self):
        command = [EXECUTABLE_NAME, ["P1"]]
        result = executor(EXECUTABLE_PATH, json.dumps(command))
        expected = {"output": os.linesep.join([EXECUTABLE_PATH, "hello P1", ""]), "returncode": 0}
        self.assertEqual(json.loads(result), expected)

    def test_run_P2(self):
        command = [EXECUTABLE_NAME, ["P2"]]
        result = executor(EXECUTABLE_PATH, json.dumps(command))
        expected = {"output": os.linesep.join([EXECUTABLE_PATH, "hello P2", ""]), "returncode": 0}
        self.assertEqual(json.loads(result), expected)

    def test_run_ERROR(self):
        command = [EXECUTABLE_NAME, ["ERROR"]]
        result = executor(EXECUTABLE_PATH, json.dumps(command))
        expected = {"output": os.linesep.join([EXECUTABLE_PATH, ""]), "returncode": 1}
        self.assertEqual(json.loads(result), expected)


class TestAcceptance(TestCommunication):
    @staticmethod
    def target_executor(command):
        return executor(EXECUTABLE_PATH, command)

    def setUp(self):
        self.s = self._run_process_func(daemon, self.SERVER_ADDRESS, self.target_executor)

    def tearDown(self):
        self.s.stop(ignore_errors=True)

    def test_client_request(self):
        c = self._run_process_func(client, self.SERVER_ADDRESS, json.dumps([EXECUTABLE_NAME, ["P1"]]))
        c.join()
        expected = {"output": os.linesep.join([EXECUTABLE_PATH, "hello P1", ""]), "returncode": 0}
        result_dict = json.loads(c.result)
        self.assertEqual(result_dict, expected)

    def test_client_request_error(self):
        c = self._run_process_func(client, self.SERVER_ADDRESS, json.dumps([EXECUTABLE_NAME, ["ERROR"]]))
        c.join()
        expected = {"output": os.linesep.join([EXECUTABLE_PATH, ""]), "returncode": 1}
        result_dict = json.loads(c.result)
        self.assertEqual(result_dict, expected)


def write_config(filepath, **kwargs):
    config = configparser.ConfigParser()
    for k, v in kwargs.items():
        config.set('DEFAULT', k, str(v))
    with open(filepath, "w") as f:
        config.write(f)


class TestConfigParser(unittest.TestCase):
    def setUp(self):
        self.ini_file = os.path.join(CWD, "test.ini")
        write_config(self.ini_file, OPTION1="OPT1_VALUE", OPTION2="OPT2_VALUE")
        self.config = configparser.ConfigParser()
        self.config.read(self.ini_file)

    def tearDown(self):
        os.remove(self.ini_file)

    def test_specified_option(self):
        self.assertEqual(self.config.get('DEFAULT', 'OPTION1'), 'OPT1_VALUE')

    def test_unspecified_option(self):
        self.assertRaises(configparser.NoOptionError, self.config.get, 'DEFAULT', 'OTHER_OPTION')

    def test_unspecified_option_with_default(self):
        self.assertEqual(self.config.get('DEFAULT', 'OTHER_OPTION', fallback='other_default'), 'other_default')


class CommandTestMixin(object):
    def _call(self, *args, **kwargs):
        ignore_errors = kwargs.pop("ignore_errors", False)
        try:
            subprocess.check_call(args)
            time.sleep(0.5)
        except subprocess.CalledProcessError:
            if not ignore_errors:
                raise


@unittest.skipIf(sys.platform != 'win32', "Windows Service tests need Windows")
class WinServiceTest(CommandTestMixin, LogTestMixin, unittest.TestCase):
    SERVICE_NAME = 'TestWRUN'
    PORT = 3333

    def assertJsonEqual(self, result, **kwargs):
        self.assertEqual(json.loads(result), kwargs)

    def setUp(self):
        log_path = self.initLog("win_service2")
        self.ini_file = os.path.join(CWD, "test.ini")
        write_config(
            self.ini_file, LOG_PATH=log_path,
            EXECUTABLE_PATH=EXECUTABLE_PATH, HOST="localhost", PORT=self.PORT)
        self._call(sys.executable, "win_service2.py", self.SERVICE_NAME, self.ini_file)

    def tearDown(self):
        self._call("sc", "stop", self.SERVICE_NAME, ignore_errors=True)
        self._call("sc", "delete", self.SERVICE_NAME, ignore_errors=True)
        os.remove(self.ini_file)

    def test_start(self):
        self._call("sc", "start", self.SERVICE_NAME)
        self.assertLogContains("win_service2", "INFO:win_service2:WRUNService.__init__ BEGIN")
        self.assertLogContains(
            "win_service2", "INFO:win_service2:param EXECUTABLE_PATH '{}'".format(EXECUTABLE_PATH))
        self.assertLogContains("win_service2", "INFO:win_service2:param HOST 'localhost'")
        self.assertLogContains("win_service2", "INFO:win_service2:WRUNService.SvcDoRun BEGIN")

    def test_stop(self):
        self._call("sc", "start", self.SERVICE_NAME)
        self._call("sc", "stop", self.SERVICE_NAME)
        self.assertLogContains("win_service2", "INFO:win_service2:WRUNService.SvcStop BEGIN")
        self.assertLogContains("win_service2", "INFO:win_service2:WRUNService.SvcStop END")

    def test_client_connection_error(self):
        self.assertRaises(ConnectionRefusedError, client, ("localhost", self.PORT), "NO_MATTER")

    def test_client_request(self):
        self._call("sc", "start", self.SERVICE_NAME)
        result = client(("localhost", self.PORT), json.dumps([EXECUTABLE_NAME, ["P1"]]))
        self.assertJsonEqual(result, output=os.linesep.join([EXECUTABLE_PATH, "hello P1", ""]), returncode=0)

    def test_client_request_error(self):
        self._call("sc", "start", self.SERVICE_NAME)
        result = client(("localhost", self.PORT), json.dumps([EXECUTABLE_NAME, ["ERROR"]]))
        self.assertJsonEqual(result, output=os.linesep.join([EXECUTABLE_PATH, ""]), returncode=1)

if __name__ == '__main__':
    unittest.main()
