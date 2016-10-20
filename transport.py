import multiprocessing
import logging
import os
import signal
import socket
import sys
import time
import unittest

LOG_PATH = "transport.log"
SERVER_ADDRESS = ('localhost', 3333)
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
    def _get_log(self):
        with open(self.LOG_PATH) as f:
            return f.read()

    def setUp(self):
        logging.basicConfig(filename=self.LOG_PATH, level=logging.DEBUG)
        # log cleanup
        logging.FileHandler(self.LOG_PATH, mode='w').close()
        super(LogTestMixin, self).setUp()

    def assertLogContains(self, expected):
        self.assertIn(expected, self._get_log())


class TestProcess(multiprocessing.Process):
    def kill(self):
        os.kill(self.pid, signal.SIGINT)


class TestLog(LogTestMixin, unittest.TestCase):
    LOG_PATH = LOG_PATH

    def test_read_write_ok(self):
        log.info("sample message")
        self.assertLogContains("sample message")

    def test_read_write_mismatch(self):
        log.info("new message")
        self.assertRaisesRegexp(
            AssertionError, r"'sample message' not found in 'INFO:.*:new message",
            self.assertLogContains, "sample message")


class TestServer(LogTestMixin, unittest.TestCase):
    LOG_PATH = LOG_PATH

    def test_start_stop(self):
        self.s = TestProcess(target=daemon, args=(SERVER_ADDRESS,))
        self.s.start()
        time.sleep(1)
        self.s.kill()
        self.s.join()
        self.assertLogContains("waiting for a connection...")
        self.assertLogContains("closing server socket...")
        self.assertLogContains("closed server socket")


class TestClient(LogTestMixin, unittest.TestCase):
    LOG_PATH = LOG_PATH

    def setUp(self):
        super(TestClient, self).setUp()
        self.s = TestProcess(target=daemon, args=(SERVER_ADDRESS,))
        self.s.start()
        time.sleep(1)

    def tearDown(self):
        self.s.kill()
        self.s.join()
        super(TestClient, self).tearDown()

    def test_no_client(self):
        self.assertLogContains("waiting for a connection...")

    def test_client_connect(self):
        self.assertEqual(client(SERVER_ADDRESS, "prova"), "prova")
        time.sleep(1)
        self.assertLogContains("CLIENT: connecting '('localhost', 3333)' ...")
        self.assertLogContains("CLIENT: connected")
        self.assertLogContains("CLIENT: sending 'prova'")
        self.assertLogContains("CLIENT: sent")
        self.assertLogContains("CLIENT: receiving...")
        self.assertLogContains("SERVER: connection from ('127.0.0.1', ")
        self.assertLogContains("SERVER: receiving...")
        self.assertLogContains("SERVER: received 'prova'")
        self.assertLogContains("SERVER: received ''")
        self.assertLogContains("SERVER: no more data to receive")
        self.assertLogContains("SERVER: sending 'prova'")
        self.assertLogContains("SERVER: sent")
        self.assertLogContains("SERVER: closing client socket")
        self.assertLogContains("SERVER: closed client socket")
        self.assertLogContains("CLIENT: received 'prova'")
        self.assertLogContains("CLIENT: received ''")
        self.assertLogContains("CLIENT: no more data to receive")
        self.assertLogContains("CLIENT: closing")
        self.assertLogContains("CLIENT: closed")



if __name__ == '__main__':
    unittest.main()
    # print(globals()[sys.argv[1]](*sys.argv[2:]))
