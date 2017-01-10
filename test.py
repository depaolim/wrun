import json
import logging
import multiprocessing
import os
import signal
import subprocess
import sys
import time
import unittest

from wrun import Config, Proxy, client, daemon, executor

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

    def assertLogMatch(self, action, expected):
        path = self._log_path(action)
        self.assertRegexpMatches(self._get_log(path), expected)


def ProcessFunc_target(q, f, args):
    q.put(f(*args))


class ProcessFunc(object):
    def _kill(self):
        if sys.platform == 'win32':
            self._process.terminate()
        else:
            os.kill(self._process.pid, signal.SIGINT)

    def __init__(self, func, *args):
        self._queue = multiprocessing.Queue()
        self._process = multiprocessing.Process(target=ProcessFunc_target, args=(self._queue, func, args))
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


def TestClientServer_revert(request):
    return request[::-1]


class TestClientServer(TestCommunication):
    def setUp(self):
        self.s = self._run_process_func(daemon, self.SERVER_ADDRESS, TestClientServer_revert)

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
        self.assertLogMatch(daemon, "SERVER: received (b')?prova'?")
        self.assertLogMatch(daemon, "SERVER: received (b'')?")
        self.assertLogContains(daemon, "SERVER: no more data to receive")
        self.assertLogContains(daemon, "SERVER: sending 'avorp'")
        self.assertLogContains(daemon, "SERVER: sent")
        self.assertLogContains(daemon, "SERVER: closing client socket")
        self.assertLogContains(daemon, "SERVER: closed client socket")
        self.assertLogMatch(client, "CLIENT: received (b')?avorp'?")
        self.assertLogMatch(client, "CLIENT: received (b'')?")
        self.assertLogContains(client, "CLIENT: no more data to receive")
        self.assertLogContains(client, "CLIENT: closing")
        self.assertLogContains(client, "CLIENT: closed")


class TestExecutor(unittest.TestCase):
    def test_run_P1(self):
        command = [EXECUTABLE_NAME, ["P1"]]
        result = executor(EXECUTABLE_PATH, json.dumps(command))
        expected = {"stdout": os.linesep.join([EXECUTABLE_PATH, "hello P1", ""]), "returncode": 0}
        self.assertEqual(json.loads(result), expected)

    def test_run_P2(self):
        command = [EXECUTABLE_NAME, ["P2"]]
        result = executor(EXECUTABLE_PATH, json.dumps(command))
        expected = {"stdout": os.linesep.join([EXECUTABLE_PATH, "hello P2", ""]), "returncode": 0}
        self.assertEqual(json.loads(result), expected)

    def test_run_ERROR(self):
        command = [EXECUTABLE_NAME, ["ERROR"]]
        result = executor(EXECUTABLE_PATH, json.dumps(command))
        expected = {"stdout": os.linesep.join([EXECUTABLE_PATH, ""]), "returncode": 1}
        self.assertEqual(json.loads(result), expected)


class TestProxy(unittest.TestCase):
    def _mock_client(self, *args):
        self._mock_client_calls.append(args)
        return json.dumps(self._mock_client_return_value)

    def setUp(self):
        self._mock_client_calls = []

    def test_run(self):
        p = Proxy("HOST", "PORT", self._mock_client)
        self._mock_client_return_value = {"stdout": "OUTPUT", "returncode": 0}
        result = p.run("SAMPLE_EXE")
        self.assertEqual(result, {"stdout": "OUTPUT", "returncode": 0})
        self.assertEqual(self._mock_client_calls, [(('HOST', 'PORT'), '["SAMPLE_EXE", []]')])


def TestAcceptance_target_executor(command):
    return executor(EXECUTABLE_PATH, command)


class TestAcceptance(TestCommunication):
    def setUp(self):
        self.s = self._run_process_func(daemon, self.SERVER_ADDRESS, TestAcceptance_target_executor)
        self.p = Proxy(*self.SERVER_ADDRESS)

    def tearDown(self):
        self.s.stop(ignore_errors=True)

    def test_client_request(self):
        c = self._run_process_func(self.p.run, EXECUTABLE_NAME, "P1")
        c.join()
        self.assertEqual(
            c.result, {
                "stdout": os.linesep.join([EXECUTABLE_PATH, "hello P1", ""]),
                "returncode": 0})

    def test_client_request_error(self):
        c = self._run_process_func(self.p.run, EXECUTABLE_NAME, "ERROR")
        c.join()
        self.assertEqual(
            c.result, {
                "stdout": os.linesep.join([EXECUTABLE_PATH, ""]),
                "returncode": 1})


class TestConfig(unittest.TestCase):
    def setUp(self):
        self.config_file = os.path.join(CWD, "settings_test.py")
        Config.store(self.config_file, OPTION1="OPT1_VALUE", OPTION2="OPT2_VALUE")
        self.config = Config(self.config_file)

    def tearDown(self):
        os.remove(self.config_file)

    def test_specified_option(self):
        self.assertEqual(self.config.OPTION1, 'OPT1_VALUE')

    def test_unspecified_option(self):
        self.assertRaises(AttributeError, getattr, self.config, 'OTHER_OPTION')

    def test_unspecified_option_with_default(self):
        self.assertEqual(getattr(self.config, 'OTHER_OPTION', 'other_default'), 'other_default')


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
        log_path = self.initLog("win_service")
        self.settings_file = os.path.join(CWD, "settings_test.py")
        Config.store(
            self.settings_file, LOG_PATH=log_path,
            EXECUTABLE_PATH=EXECUTABLE_PATH, HOST="localhost", PORT=self.PORT)
        self._call(sys.executable, "wrun_service.py", self.SERVICE_NAME, self.settings_file)

    def tearDown(self):
        self._call("sc", "stop", self.SERVICE_NAME, ignore_errors=True)
        self._call("sc", "delete", self.SERVICE_NAME, ignore_errors=True)
        os.remove(self.settings_file)

    def test_start(self):
        self._call("sc", "start", self.SERVICE_NAME)
        self.assertLogContains("win_service", "INFO:wrun_service:WRUNService.__init__ BEGIN")
        self.assertLogContains(
            "win_service", "INFO:wrun_service:param EXECUTABLE_PATH '{}'".format(EXECUTABLE_PATH))
        self.assertLogContains("win_service", "INFO:wrun_service:param HOST 'localhost'")
        self.assertLogContains("win_service", "INFO:wrun_service:WRUNService.SvcDoRun BEGIN")

    def test_stop(self):
        self._call("sc", "start", self.SERVICE_NAME)
        self._call("sc", "stop", self.SERVICE_NAME)
        self.assertLogContains("win_service", "INFO:wrun_service:WRUNService.SvcStop BEGIN")
        self.assertLogContains("win_service", "INFO:wrun_service:WRUNService.SvcStop END")

    def test_client_connection_error(self):
        self.assertRaises(Exception, client, ("localhost", self.PORT), "NO_MATTER")

    def test_client_request(self):
        self._call("sc", "start", self.SERVICE_NAME)
        result = client(("localhost", self.PORT), json.dumps([EXECUTABLE_NAME, ["P1"]]))
        self.assertJsonEqual(result, stdout=os.linesep.join([EXECUTABLE_PATH, "hello P1", ""]), returncode=0)

    def test_client_request_error(self):
        self._call("sc", "start", self.SERVICE_NAME)
        result = client(("localhost", self.PORT), json.dumps([EXECUTABLE_NAME, ["ERROR"]]))
        self.assertJsonEqual(result, stdout=os.linesep.join([EXECUTABLE_PATH, ""]), returncode=1)


@unittest.skipIf(sys.platform != 'win32', "Windows Service tests need Windows")
class DoubleWinServiceTest(CommandTestMixin, LogTestMixin, unittest.TestCase):
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
        self._call(sys.executable, "wrun_service.py", "TestWRUN_1", self.settings_file_1)
        self._call(sys.executable, "wrun_service.py", "TestWRUN_2", self.settings_file_2)

    def tearDown(self):
        self._call("sc", "stop", "TestWRUN_1", ignore_errors=True)
        self._call("sc", "delete", "TestWRUN_1", ignore_errors=True)
        self._call("sc", "stop", "TestWRUN_2", ignore_errors=True)
        self._call("sc", "delete", "TestWRUN_2", ignore_errors=True)
        os.remove(self.settings_file_1)
        os.remove(self.settings_file_2)

    def test_double_client_request(self):
        self._call("sc", "start", "TestWRUN_1")
        self._call("sc", "start", "TestWRUN_2")
        result_1 = client(("localhost", 3333), json.dumps([EXECUTABLE_NAME, ["P1"]]))
        self.assertJsonEqual(result_1, stdout=os.linesep.join([EXECUTABLE_PATH, "hello P1", ""]), returncode=0)
        result_2 = client(("localhost", 3334), json.dumps([EXECUTABLE_NAME, ["P1"]]))
        self.assertJsonEqual(result_2, stdout=os.linesep.join([self.EXECUTABLE_PATH_2, "mandi P1", ""]), returncode=0)


if __name__ == '__main__':
    unittest.main()
