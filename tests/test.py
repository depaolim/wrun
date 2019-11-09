import json
import logging
import multiprocessing
import os
import signal
import sys
import time
import unittest
import unittest.mock

from wrun import BaseConfig, Config, Proxy, client, daemon, executor, log_config

from tests.config import *


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
        os_remove(os.path.join(CWD, "test_daemon.log"))
        os_remove(os.path.join(CWD, "test_client.log"))

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
    CERFILE = os.path.join(SSL_PATH, "server.crt")
    KEYFILE = os.path.join(SSL_PATH, "server.key")

    def setUp(self):
        self.s = self._run_process_func(
            daemon, self.SERVER_ADDRESS, TestClientServer_revert, cafile=self.CERFILE, keyfile=self.KEYFILE)

    def tearDown(self):
        self.s.stop(ignore_errors=True)
        os_remove(os.path.join(CWD, "test_daemon.log"))
        os_remove(os.path.join(CWD, "test_client.log"))

    def test(self):
        c = self._run_process_func(client, self.SERVER_ADDRESS, 'ciao', cafile=self.CERFILE)
        c.join()
        self.assertEqual(c.result, 'oaic')
        self.assertLogContains(daemon, "SERVER: securing socket...")
        self.assertLogContains(client, "CLIENT: securing socket...")


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
    def setUp(self):
        def _mock_client(*args, **kwargs):
            self._mock_client_calls.append((args, kwargs))
            return json.dumps(self._mock_client_return_value)

        self._mock_client_calls = []
        self.patch = unittest.mock.patch("wrun.client", _mock_client)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()

    def test_run(self):
        p = Proxy("HOST", "PORT")
        self._mock_client_return_value = {"stdout": "OUTPUT", "returncode": 0}
        result = p.run("SAMPLE_EXE", [])
        self.assertEqual(result, {"stdout": "OUTPUT", "returncode": 0})
        self.assertEqual(self._mock_client_calls, [((('HOST', 'PORT'), '["SAMPLE_EXE", [], ""]'), {})])

    def test_run_with_args(self):
        p = Proxy("HOST", "PORT")
        self._mock_client_return_value = {"stdout": "OUTPUT", "returncode": 0}
        result = p.run("SAMPLE_EXE", ["A1", "A2"])
        self.assertEqual(result, {"stdout": "OUTPUT", "returncode": 0})
        self.assertEqual(self._mock_client_calls, [((('HOST', 'PORT'), '["SAMPLE_EXE", ["A1", "A2"], ""]'), {})])

    def test_run_with_stdin(self):
        p = Proxy("HOST", "PORT")
        self._mock_client_return_value = {"stdout": "OUTPUT", "returncode": 0}
        result = p.run("SAMPLE_EXE", [], input_stdin="INPUT_STDIN")
        self.assertEqual(result, {"stdout": "OUTPUT", "returncode": 0})
        self.assertEqual(self._mock_client_calls, [((('HOST', 'PORT'), '["SAMPLE_EXE", [], "INPUT_STDIN"]'), {})])

    def test_run_secure(self):
        p = Proxy("HOST", "PORT", cafile="mock_cafile")
        self._mock_client_return_value = {"stdout": "OUTPUT", "returncode": 0}
        result = p.run("SAMPLE_EXE", [], input_stdin="INPUT_STDIN")
        self.assertEqual(result, {"stdout": "OUTPUT", "returncode": 0})
        self.assertEqual(self._mock_client_calls, [
            ((('HOST', 'PORT'), '["SAMPLE_EXE", [], "INPUT_STDIN"]'), {"cafile": "mock_cafile"})
        ])


def TestAcceptance_target_executor(command):
    return executor(EXECUTABLE_PATH, command)


def TestAcceptance_run_client(server_address, executable_name, args):
    p = Proxy(*server_address)
    return p.run(executable_name, args)


class TestAcceptance(TestCommunication):
    def setUp(self):
        self.s = self._run_process_func(daemon, self.SERVER_ADDRESS, TestAcceptance_target_executor)

    def tearDown(self):
        self.s.stop(ignore_errors=True)
        os_remove(os.path.join(CWD, "test_daemon.log"))
        os_remove(os.path.join(CWD, "test_TestAcceptance_run_client.log"))

    def test_client_request(self):
        c = self._run_process_func(TestAcceptance_run_client, self.SERVER_ADDRESS, EXECUTABLE_NAME, ["P1"])
        c.join()
        self.assertEqual(
            c.result, {
                "stdout": os.linesep.join([EXECUTABLE_PATH, "hello P1", ""]),
                "returncode": 0})

    def test_client_request_error(self):
        c = self._run_process_func(TestAcceptance_run_client, self.SERVER_ADDRESS, EXECUTABLE_NAME, ["ERROR"])
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
        os_remove(self.config_file)

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
        self.log_file = os.path.join(CWD, "test.log")
        open(self.log_file, "w").close()  # file reset
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
        os_remove(self.log_fileconfig)
        self._remove_handlers(logging.root)
        self._remove_handlers(logging.getLogger("wrun"))
        os_remove(self.config_file)
        os_remove(self.log_file)

    def _remove_handlers(self, logger):
        handlers = list(logger.handlers)
        for h in handlers:
            h.close()
            logger.removeHandler(h)

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


if __name__ == '__main__':
    unittest.main()
