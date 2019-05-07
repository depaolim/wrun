import json
import logging
import multiprocessing
import os
import signal
import subprocess
import sys
import time
import unittest

from wrun import BaseConfig, Config, Proxy, client, daemon, executor, log_config

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
    def logged_func(cls, func, *args, **kwargs):
        cls._init_log_file(cls._log_path(func))
        return func(*args, **kwargs)

    def initLog(self, action):
        path = self._log_path(action)
        self._init_log_file(path)
        return path

    def assertLogContains(self, action, expected):
        path = self._log_path(action)
        self.assertIn(expected, self._get_log(path))

    def assertLogMatch(self, action, expected):
        path = self._log_path(action)
        self.assertRegex(self._get_log(path), expected)


def ProcessFunc_target(q, f, args, kwargs):
    q.put(f(*args, **kwargs))


class ProcessFunc(object):
    @staticmethod
    def kill_process(process):
        if sys.platform == 'win32':
            process.terminate()
        else:
            os.kill(process.pid, signal.SIGINT)

    def _kill(self):
        self.kill_process(self._process)

    def __init__(self, func, *args, **kwargs):
        self._queue = multiprocessing.Queue()
        self._process = multiprocessing.Process(
            target=ProcessFunc_target, args=(self._queue, func, args, kwargs))
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

    def _run_process_func(self, func, *args, **kwargs):
        return ProcessFunc(self.logged_func, func, *args, **kwargs)


def TestClientServer_revert(request):
    if request == 'BOOM!!!':
        raise Exception('BOOM!!!')
    return request[::-1]


class TestClientServer(TestCommunication):
    def setUp(self):
        self.s = self._run_process_func(daemon, self.SERVER_ADDRESS, TestClientServer_revert)

    def tearDown(self):
        self.s.stop(ignore_errors=True)

    def test_server_is_listening(self):
        self.assertLogContains(daemon, "waiting for a connection on server socket...")

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
        self.assertLogContains(client, "CLIENT: sending b'prova'")
        self.assertLogContains(client, "CLIENT: sent")
        self.assertLogContains(client, "CLIENT: receiving...")
        self.assertLogContains(daemon, "SERVER: connection from ('127.0.0.1', ")
        self.assertLogContains(daemon, "SERVER: receiving...")
        self.assertLogContains(daemon, "SERVER: received b'prova'")
        self.assertLogContains(daemon, "SERVER: received b''")
        self.assertLogContains(daemon, "SERVER: no more data to receive")
        self.assertLogContains(daemon, "SERVER: sending b'avorp'")
        self.assertLogContains(daemon, "SERVER: sent")
        self.assertLogContains(daemon, "SERVER: closing client socket")
        self.assertLogContains(daemon, "SERVER: closed client socket")
        self.assertLogContains(client, "CLIENT: received b'avorp'")
        self.assertLogContains(client, "CLIENT: received b''")
        self.assertLogContains(client, "CLIENT: no more data to receive")
        self.assertLogContains(client, "CLIENT: closing")
        self.assertLogContains(client, "CLIENT: closed")

    def test_client_error_request(self):
        c = self._run_process_func(client, self.SERVER_ADDRESS, "BOOM!!!")
        c.join()
        self.assertEqual(c.result, "")
        self.assertLogContains(client, "CLIENT: connecting '('localhost', 3333)' ...")
        self.assertLogContains(client, "CLIENT: connected")
        self.assertLogContains(client, "CLIENT: sending b'BOOM!!!'")
        self.assertLogContains(client, "CLIENT: sent")
        self.assertLogContains(client, "CLIENT: receiving...")
        self.assertLogContains(daemon, "SERVER: connection from ('127.0.0.1', ")
        self.assertLogContains(daemon, "SERVER: receiving...")
        self.assertLogContains(daemon, "SERVER: received b'BOOM!!!'")
        self.assertLogContains(daemon, "SERVER: received b''")
        self.assertLogContains(daemon, "SERVER: no more data to receive")
        self.assertLogContains(daemon, "SERVER: exception in client request processing")
        self.assertLogContains(daemon, "SERVER: closing client socket")
        self.assertLogContains(daemon, "SERVER: closed client socket")
        self.assertLogContains(client, "CLIENT: received b''")
        self.assertLogContains(client, "CLIENT: no more data to receive")
        self.assertLogContains(client, "CLIENT: closing")
        self.assertLogContains(client, "CLIENT: closed")


class TestSecureClientServer(TestCommunication):
    SERVER_ADDRESS = ('localhost', 3333)
    CERFILE = os.path.join("demo_ssl", "server.crt")
    KEYFILE = os.path.join("demo_ssl", "server.key")

    def setUp(self):
        self.s = self._run_process_func(
            daemon, self.SERVER_ADDRESS, TestClientServer_revert, cafile=self.CERFILE, keyfile=self.KEYFILE)

    def tearDown(self):
        self.s.stop(ignore_errors=True)

    def test(self):
        response = client(self.SERVER_ADDRESS, 'ciao', cafile=self.CERFILE)
        self.assertEqual(response, 'oaic')


class TestExecutor(unittest.TestCase):
    def test_run_P1(self):
        command = [EXECUTABLE_NAME, ["P1"], ""]
        result = executor(EXECUTABLE_PATH, json.dumps(command))
        expected = {"stdout": os.linesep.join([EXECUTABLE_PATH, "hello P1", ""]), "returncode": 0}
        self.assertEqual(json.loads(result), expected)

    def test_run_P2(self):
        command = [EXECUTABLE_NAME, ["P2"], ""]
        result = executor(EXECUTABLE_PATH, json.dumps(command))
        expected = {"stdout": os.linesep.join([EXECUTABLE_PATH, "hello P2", ""]), "returncode": 0}
        self.assertEqual(json.loads(result), expected)

    def test_run_ERROR(self):
        command = [EXECUTABLE_NAME, ["ERROR"], ""]
        result = executor(EXECUTABLE_PATH, json.dumps(command))
        expected = {"stdout": os.linesep.join([EXECUTABLE_PATH, ""]), "returncode": 1}
        self.assertEqual(json.loads(result), expected)

    def test_run_P1_with_stderr(self):
        command = [EXECUTABLE_NAME, ["P1"], ""]
        result = executor(EXECUTABLE_PATH, json.dumps(command), True)
        expected = {
            "stdout": os.linesep.join([EXECUTABLE_PATH, "hello P1", ""]),
            "stderr": "",
            "returncode": 0}
        self.assertEqual(json.loads(result), expected)

    def test_run_ERROR_with_stderr(self):
        command = [EXECUTABLE_NAME, ["ERROR"], ""]
        result = executor(EXECUTABLE_PATH, json.dumps(command), True)
        expected = {
            "stdout": os.linesep.join([EXECUTABLE_PATH, ""]),
            "stderr": os.linesep.join(["err_msg ERROR ", ""]),
            "returncode": 1}
        self.assertEqual(json.loads(result), expected)

    def test_run_with_stdin(self):
        command = [EXECUTABLE_NAME, ["STDIN"], "INPUT_STDIN"]
        result = executor(EXECUTABLE_PATH, json.dumps(command))
        expected = {
            "stdout": os.linesep.join([EXECUTABLE_PATH, "INPUT_STDIN", ""]),
            "returncode": 0}
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
        result = p.run("SAMPLE_EXE", [])
        self.assertEqual(result, {"stdout": "OUTPUT", "returncode": 0})
        self.assertEqual(self._mock_client_calls, [(('HOST', 'PORT'), '["SAMPLE_EXE", [], ""]')])

    def test_run_with_args(self):
        p = Proxy("HOST", "PORT", self._mock_client)
        self._mock_client_return_value = {"stdout": "OUTPUT", "returncode": 0}
        result = p.run("SAMPLE_EXE", ["A1", "A2"])
        self.assertEqual(result, {"stdout": "OUTPUT", "returncode": 0})
        self.assertEqual(self._mock_client_calls, [(('HOST', 'PORT'), '["SAMPLE_EXE", ["A1", "A2"], ""]')])

    def test_run_with_stdin(self):
        p = Proxy("HOST", "PORT", self._mock_client)
        self._mock_client_return_value = {"stdout": "OUTPUT", "returncode": 0}
        result = p.run("SAMPLE_EXE", [], input_stdin="INPUT_STDIN")
        self.assertEqual(result, {"stdout": "OUTPUT", "returncode": 0})
        self.assertEqual(self._mock_client_calls, [(('HOST', 'PORT'), '["SAMPLE_EXE", [], "INPUT_STDIN"]')])


def TestAcceptance_target_executor(command):
    return executor(EXECUTABLE_PATH, command)


class TestAcceptance(TestCommunication):
    def setUp(self):
        self.s = self._run_process_func(daemon, self.SERVER_ADDRESS, TestAcceptance_target_executor)
        self.p = Proxy(*self.SERVER_ADDRESS)

    def tearDown(self):
        self.s.stop(ignore_errors=True)

    def test_client_request(self):
        c = self._run_process_func(self.p.run, EXECUTABLE_NAME, ["P1"])
        c.join()
        self.assertEqual(
            c.result, {
                "stdout": os.linesep.join([EXECUTABLE_PATH, "hello P1", ""]),
                "returncode": 0})

    def test_client_request_error(self):
        c = self._run_process_func(self.p.run, EXECUTABLE_NAME, ["ERROR"])
        c.join()
        self.assertEqual(
            c.result, {
                "stdout": os.linesep.join([EXECUTABLE_PATH, ""]),
                "returncode": 1})


class TestBaseConfig(unittest.TestCase):
    def setUp(self):
        self.config_file = os.path.join(CWD, "settings_test.py")
        BaseConfig.store(self.config_file, OPTION1="OPT1_VALUE", OPTION2="OPT2_VALUE")
        self.config = BaseConfig(self.config_file, OPTION1="OPT1_DEFAULT", BASE_OPTION="DEFAULT_VALUE")

    def tearDown(self):
        os.remove(self.config_file)

    def test_specified_option(self):
        self.assertEqual(self.config.OPTION1, 'OPT1_VALUE')

    def test_unspecified_option(self):
        self.assertRaises(AttributeError, getattr, self.config, 'OTHER_OPTION')

    def test_unspecified_option_with_default(self):
        self.assertEqual(getattr(self.config, 'OTHER_OPTION', 'other_default'), 'other_default')

    def test_default_option(self):
        self.assertEqual(self.config.BASE_OPTION, 'DEFAULT_VALUE')


class TestLogConfig(unittest.TestCase):
    class Mock:
        pass

    def setUp(self):
        self.calls = []
        self.mock_params = {
            "LOG_PATH": lambda p: self.calls.append(("1", p)),
            "LOG_FILECONFIG": lambda p: self.calls.append(("2", p)),
            "LOG_DICTCONFIG": None}

    def test_log_path(self):
        config = self.Mock()
        config.LOG_PATH = "dummy_log_path"
        log_config(config, self.mock_params)
        self.assertEqual(self.calls, [("1", "dummy_log_path")])

    def test_log_fileconfig(self):
        config = self.Mock()
        config.LOG_FILECONFIG = "dummy_log_fileconfig"
        log_config(config, self.mock_params)
        self.assertEqual(self.calls, [("2", "dummy_log_fileconfig")])

    def test_xor_on_log_settings(self):
        config = self.Mock()
        config.LOG_PATH = "dummy_path"
        config.LOG_FILECONFIG = "dummy_fileconfig"
        self.assertRaises(AssertionError, log_config, config, self.mock_params)


class TestConfig(unittest.TestCase):
    def setUp(self):
        self.config_file = os.path.join(CWD, "settings_test.py")
        open(self.config_file, "w").close()  # reset settings file
        self.log_file = os.path.join(CWD, "test.log")
        open(self.log_file, "w").close()  # reset log file
        self.log_fileconfig = os.path.join(CWD, "log_fileconfig.ini")
        with open(self.log_fileconfig, "w") as f:
            f.write("""
[loggers]
keys=root, wrun

[handlers]
keys=hand01

[formatters]
keys=form01

[logger_root]
level=NOTSET
handlers=hand01

[logger_wrun]
level=NOTSET
handlers=hand01
qualname=wrun

[handler_hand01]
class=FileHandler
level=NOTSET
formatter=form01
args=('{}', 'w')

[formatter_form01]
format=%(levelname)s-%(name)s %(message)s
datefmt=
                """.format(self.log_file.replace('\\', '/')))

    def tearDown(self):
        os.remove(self.config_file)
        os.remove(self.log_fileconfig)
        root = logging.root
        for h in root.handlers[:]:
            h.close()
            root.removeHandler(h)

    def assertLogContains(self, msg):
        with open(self.log_file) as f:
            self.assertIn(msg, f.read())

    def test_log_path(self):
        Config.store(self.config_file, LOG_PATH=self.log_file)
        config = Config(self.config_file)
        self.assertTrue(config.LOG_PATH)
        self.assertLogContains("INFO:wrun:settings")

    def test_log_fileconfig(self):
        Config.store(self.config_file, LOG_FILECONFIG=self.log_fileconfig)
        config = Config(self.config_file)
        self.assertTrue(config.LOG_FILECONFIG)
        self.assertLogContains("INFO-wrun settings \"{\'")

    def test_log_dictconfig(self):
        Config.store(self.config_file, LOG_DICTCONFIG={
            "version": 1,
            'disable_existing_loggers': True,
            'formatters': {
                'standard': {
                    'format': '[%(levelname)s] %(name)s: %(message)s'
                },
            },
            'handlers': {
                'default': {
                    'level': 'DEBUG',
                    'formatter': 'standard',
                    'class': 'logging.FileHandler',
                    'filename': self.log_file.replace('\\', '/'),
                    'mode': 'a',
                },
            },
            'loggers': {
                '': {
                    'handlers': ['default'],
                    'level': 'DEBUG',
                    'propagate': True
                },
                'wrun': {
                    'handlers': ['default'],
                    'level': 'DEBUG',
                    'propagate': True
                },
            }
        })
        config = Config(self.config_file)
        self.assertTrue(config.LOG_DICTCONFIG)
        self.assertLogContains("[INFO] wrun: settings \"{\'")

    def test_xor_on_log_settings(self):
        Config.store(self.config_file, LOG_PATH=self.log_file, LOG_FILECONFIG=self.log_fileconfig)
        self.assertRaises(AssertionError, Config, self.config_file)


class CommandTestMixin(object):
    def _call(self, *args, **kwargs):
        ignore_errors = kwargs.pop("ignore_errors", False)
        try:
            subprocess.check_call(args)
            time.sleep(0.5)
        except subprocess.CalledProcessError:
            if not ignore_errors:
                raise


class WinServiceTestBase(CommandTestMixin, LogTestMixin, unittest.TestCase):
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


@unittest.skipIf(sys.platform != 'win32', "Windows Service tests need Windows")
class WinServiceTest(WinServiceTestBase):
    def test_start(self):
        self._call("sc", "start", self.SERVICE_NAME)
        self.assertLogContains("win_service", "INFO:wrun:settings \"{'")
        self.assertLogContains("win_service", "INFO:wrun_service:WRUNService.__init__ BEGIN")
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
        result = client(("localhost", self.PORT), json.dumps([EXECUTABLE_NAME, ["P1"], ""]))
        self.assertJsonEqual(result, stdout=os.linesep.join([EXECUTABLE_PATH, "hello P1", ""]), returncode=0)

    def test_client_request_error(self):
        self._call("sc", "start", self.SERVICE_NAME)
        result = client(("localhost", self.PORT), json.dumps([EXECUTABLE_NAME, ["ERROR"], ""]))
        self.assertJsonEqual(result, stdout=os.linesep.join([EXECUTABLE_PATH, ""]), returncode=1)


@unittest.skipIf(sys.platform != 'win32', "Windows Service tests need Windows")
class WinServiceTestWithStderr(WinServiceTestBase):
    def setUp(self):
        log_path = self.initLog("win_service")
        self.settings_file = os.path.join(CWD, "settings_test.py")
        Config.store(
            self.settings_file, LOG_PATH=log_path, COLLECT_STDERR=True,
            EXECUTABLE_PATH=EXECUTABLE_PATH, HOST="localhost", PORT=self.PORT)
        self._call(sys.executable, "wrun_service.py", self.SERVICE_NAME, self.settings_file)

    def test_client_request_error(self):
        self._call("sc", "start", self.SERVICE_NAME)
        result = client(("localhost", self.PORT), json.dumps([EXECUTABLE_NAME, ["ERROR"], ""]))
        self.assertJsonEqual(
            result, stdout=os.linesep.join([EXECUTABLE_PATH, ""]),
            stderr=os.linesep.join(["err_msg ERROR ", ""]), returncode=1)


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
        result_1 = client(("localhost", 3333), json.dumps([EXECUTABLE_NAME, ["P1"], ""]))
        self.assertJsonEqual(result_1, stdout=os.linesep.join([EXECUTABLE_PATH, "hello P1", ""]), returncode=0)
        result_2 = client(("localhost", 3334), json.dumps([EXECUTABLE_NAME, ["P1"], ""]))
        self.assertJsonEqual(result_2, stdout=os.linesep.join([self.EXECUTABLE_PATH_2, "mandi P1", ""]), returncode=0)


if __name__ == '__main__':
    unittest.main()
