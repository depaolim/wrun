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
    SERVER_LOG_PATH = "transport_daemon.log"
    CLIENT_LOG_PATH = "transport_client.log"

    @staticmethod
    def _get_log(path):
        with open(path) as f:
            return f.read()

    @staticmethod
    def init_log_file(path):
        print("init_log_file START", os.getpid(), path)
        logging.basicConfig(filename=path, level=logging.DEBUG, filemode='a')
        logging.FileHandler(path, mode='w').close()  # log cleanup
        print("init_log_file END", logging.Logger.manager.loggerDict.keys())

    @classmethod
    def logged_func(cls, func, queue, *args):
        cls.init_log_file("transport_" + func.func_name + ".log")
        print("RUN START", func.func_name)
        result = func(*args)
        print("RUN END", func.func_name, result)
        queue.put(result)

    def assertServerLogContains(self, expected):
        slog = self._get_log(self.SERVER_LOG_PATH)
        clog = self._get_log(self.CLIENT_LOG_PATH)
        print("SERVER", expected, expected in slog, slog)
        self.assertIn(expected, slog)

    def assertClientLogContains(self, expected):
        slog = self._get_log(self.SERVER_LOG_PATH)
        clog = self._get_log(self.CLIENT_LOG_PATH)
        print("CLIENT", expected, expected in clog, clog)
        self.assertIn(expected, clog)


class TestLogClient(LogTestMixin, unittest.TestCase):
    def test_read_write_ok(self):
        log.info("sample message")
        self.assertClientLogContains("sample message")

    def test_read_write_mismatch(self):
        log.info("new message")
        self.assertRaisesRegexp(
            AssertionError, r"'sample message' not found in 'INFO:.*:new message",
            self.assertClientLogContains, "sample message")


class TestProcess(multiprocessing.Process):
    def kill(self):
        if sys.platform == 'win32':
            self.terminate()
        else:
            os.kill(self.pid, signal.SIGINT)


class TestClientServer(LogTestMixin, unittest.TestCase):
    SERVER_ADDRESS = ('localhost', 3333)

    def setUp(self):
        q = multiprocessing.Queue()
        self.s = TestProcess(target=lambda ad: self.logged_func(daemon, q, ad), args=(self.SERVER_ADDRESS,))
        self.s.start()
        time.sleep(1)
        #super(TestClientServer, self).setUp()

    def tearDown(self):
        #super(TestClientServer, self).tearDown()
        try:
            self.s.kill()
        except OSError:
            # process already killed
            pass
        self.s.join()

    def test_server_is_listening(self):
        self.assertServerLogContains("waiting for a connection...")

    @unittest.skipIf(sys.platform == 'win32', "no clean shutdown on Windows")
    def test_server_shutdown(self):
        self.s.kill()
        self.s.join()
        self.assertServerLogContains("closing server socket...")
        self.assertServerLogContains("closed server socket")

    def test_client_connect(self):
        #self.assertEqual(client(self.SERVER_ADDRESS, "prova"), "prova")
        q = multiprocessing.Queue()
        c = TestProcess(target=lambda ad, msg: self.logged_func(client, q, ad, msg), args=(self.SERVER_ADDRESS, "prova"))
        c.start()
        time.sleep(1)
        c.kill()
        c.join()
        self.assertEqual(q.get(), "prova")
        self.assertClientLogContains("CLIENT: connecting '('localhost', 3333)' ...")
        self.assertClientLogContains("CLIENT: connected")
        self.assertClientLogContains("CLIENT: sending 'prova'")
        self.assertClientLogContains("CLIENT: sent")
        self.assertClientLogContains("CLIENT: receiving...")
        self.assertServerLogContains("SERVER: connection from ('127.0.0.1', ")
        self.assertServerLogContains("SERVER: receiving...")
        self.assertServerLogContains("SERVER: received 'prova'")
        self.assertServerLogContains("SERVER: received ''")
        self.assertServerLogContains("SERVER: no more data to receive")
        self.assertServerLogContains("SERVER: sending 'prova'")
        self.assertServerLogContains("SERVER: sent")
        self.assertServerLogContains("SERVER: closing client socket")
        self.assertServerLogContains("SERVER: closed client socket")
        self.assertClientLogContains("CLIENT: received 'prova'")
        self.assertClientLogContains("CLIENT: received ''")
        self.assertClientLogContains("CLIENT: no more data to receive")
        self.assertClientLogContains("CLIENT: closing")
        self.assertClientLogContains("CLIENT: closed")



if __name__ == '__main__':
    unittest.main()
    # print(globals()[sys.argv[1]](*sys.argv[2:]))
