import multiprocessing
import logging
import os
import signal
import socket
import sys
import time
import unittest

BUFFER_SIZE = 255


log = logging.getLogger(__name__)


class Socket(socket.socket):
    def __init__(self):
        super(Socket, self).__init__(socket.AF_INET, socket.SOCK_STREAM)


def daemon(server_address, execute=lambda request: request, condition=lambda: True):
    ss = Socket()
    ss.bind(server_address)
    ss.listen(1)
    try:
        while condition():
            log.info("SERVER: waiting for a connection...")
            sc, ad = ss.accept()
            log.info("SERVER: connection from %s", ad)
            request = ""
            while True:
                log.info("SERVER: receiving...")
                data = sc.recv(BUFFER_SIZE)
                log.info("SERVER: received '%s'", data)
                if not data:
                    log.info("SERVER: no more data to receive")
                    break
                request += data
            response = execute(request)
            log.info("SERVER: sending '%s' ...", response)
            sc.sendall(response)
            log.info("SERVER: sent")
            log.info("SERVER: closing client socket...")
            sc.close()
            log.info("SERVER: closed client socket")
    finally:
        log.info("SERVER: closing server socket...")
        ss.close()
        log.info("SERVER: closed server socket")


def client(server_address, request):
    ss = Socket()
    log.info("CLIENT: connecting '%s' ...", server_address)
    ss.connect(server_address)
    log.info("CLIENT: connected")
    log.info("CLIENT: sending '%s' ...", request)
    ss.sendall(request)
    ss.shutdown(socket.SHUT_WR)
    log.info("CLIENT: sent")
    response = ""
    while True:
        log.info("CLIENT: receiving...")
        data = ss.recv(BUFFER_SIZE)
        log.info("CLIENT: received '%s'", data)
        if not data:
            log.info("CLIENT: no more data to receive")
            break
        response += data
    log.info("CLIENT: closing...")
    ss.close()
    log.info("CLIENT: closed")
    return response


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
        return func(*args)

    def assertLogContains(self, func, expected):
        self.assertIn(expected, self._get_log(self._log_path(func)))


class TestProcess(multiprocessing.Process):
    def _kill(self):
        if sys.platform == 'win32':
            self.terminate()
        else:
            os.kill(self.pid, signal.SIGINT)

    def __init__(self, func):
        self._queue = multiprocessing.Queue()
        super(TestProcess, self).__init__(target=lambda: self._queue.put(func()))
        self.start()
        time.sleep(0.5)

    def stop(self, ignore_errors=False):
        try:
            self._kill()
        except OSError:
            # process already killed
            if not ignore_errors:
                raise
        self.join()

    @property
    def result(self):
        return self._queue.get()


class TestClientServer(LogTestMixin, unittest.TestCase):
    SERVER_ADDRESS = ('localhost', 3333)

    def start(self, func, *args):
        return TestProcess(lambda: self.logged_func(func, *args))

    def setUp(self):
        self.s = self.start(daemon, self.SERVER_ADDRESS,)

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
        c = self.start(client, self.SERVER_ADDRESS, "prova")
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
    # print(globals()[sys.argv[1]](*sys.argv[2:]))
