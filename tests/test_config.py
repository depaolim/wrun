import logging
import os
import subprocess
import sys
import time


if sys.platform == 'win32':
    EXECUTABLE_NAME = "sample.bat"
else:
    EXECUTABLE_NAME = "sample.sh"

CWD = os.path.dirname(os.path.realpath(__file__))
EXECUTABLE_PATH = os.path.join(CWD, "test_executables")
SSL_PATH = os.path.join(CWD, "demo_ssl")


def subprocess_check_call(args, ignore_errors=False):
    try:
        subprocess.check_call(args)
        time.sleep(0.5)
    except subprocess.CalledProcessError:
        if not ignore_errors:
            raise


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
