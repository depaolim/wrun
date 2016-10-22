import StringIO
import multiprocessing
import logging
import os
import signal
import sys
import time
import unittest

from transport import client, daemon


class LogTestMixin(object):
    @staticmethod
    def _get_log(path):
        with open(path) as f:
            return f.read()

    @staticmethod
    def _log_path(func):
        return "transport_" + func.func_name + ".log"

    @staticmethod
    def init_log_file(path):
        logging.basicConfig(filename=path, level=logging.DEBUG, filemode='a')
        logging.FileHandler(path, mode='w').close()  # log cleanup

    @classmethod
    def logged_func(cls, func, *args):
        cls.init_log_file(cls._log_path(func))
        sys.stderr = StringIO.StringIO()  # ignore stderr
        return func(*args)

    def assertLogContains(self, func, expected):
        self.assertIn(expected, self._get_log(self._log_path(func)))


class ProcessFunc(object):
    def _kill(self):
        if sys.platform == 'win32':
            self._process.terminate()
        else:
            os.kill(self._process.pid, signal.SIGINT)

    def __init__(self, func):
        self._queue = multiprocessing.Queue()
        self._process = multiprocessing.Process(target=lambda: self._queue.put(func()))
        self._process.start()
        time.sleep(0.5)

    def stop(self, ignore_errors=False):
        if not ignore_errors or self._process.is_alive():
            self._kill()
        self._process.join()

    @property
    def result(self):
        return self._queue.get()


class TestClientServer(LogTestMixin, unittest.TestCase):
    SERVER_ADDRESS = ('localhost', 3333)

    def _run_process_func(self, func, *args):
        return ProcessFunc(lambda: self.logged_func(func, *args))

    def setUp(self):
        self.s = self._run_process_func(daemon, self.SERVER_ADDRESS,)

    def tearDown(self):
        self.s.stop(ignore_errors=True)

    def test_server_is_listening(self):
        self.assertLogContains(daemon, "waiting for a connection...")

    @unittest.skipIf(sys.platform == 'win32', "no clean shutdown on Windows")
    def test_server_shutdown(self):
        self.s.stop()
        self.assertLogContains(daemon, "closing server socket...")
        self.assertLogContains(daemon, "closed server socket")

    def test_client_connect(self):
        c = self._run_process_func(client, self.SERVER_ADDRESS, "prova")
        c.stop()
        self.assertEqual(c.result, "prova")
        self.assertLogContains(client, "CLIENT: connecting '('localhost', 3333)' ...")
        self.assertLogContains(client, "CLIENT: connected")
        self.assertLogContains(client, "CLIENT: sending 'prova'")
        self.assertLogContains(client, "CLIENT: sent")
        self.assertLogContains(client, "CLIENT: receiving...")
        self.assertLogContains(daemon, "SERVER: connection from ('127.0.0.1', ")
        self.assertLogContains(daemon, "SERVER: receiving...")
        self.assertLogContains(daemon, "SERVER: received 'prova'")
        self.assertLogContains(daemon, "SERVER: received ''")
        self.assertLogContains(daemon, "SERVER: no more data to receive")
        self.assertLogContains(daemon, "SERVER: sending 'prova'")
        self.assertLogContains(daemon, "SERVER: sent")
        self.assertLogContains(daemon, "SERVER: closing client socket")
        self.assertLogContains(daemon, "SERVER: closed client socket")
        self.assertLogContains(client, "CLIENT: received 'prova'")
        self.assertLogContains(client, "CLIENT: received ''")
        self.assertLogContains(client, "CLIENT: no more data to receive")
        self.assertLogContains(client, "CLIENT: closing")
        self.assertLogContains(client, "CLIENT: closed")


if __name__ == '__main__':
    unittest.main()
