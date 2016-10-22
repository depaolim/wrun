from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import argparse
import logging
import os
import signal
import socket
import subprocess
import sys

import Pyro4

SERVER = None


CommunicationError = Pyro4.errors.CommunicationError
log = logging.getLogger(__name__)


class Executor:
    @Pyro4.expose
    def run(self, exe_name, *args):
        log.debug("Executor.run %s %s", exe_name, " ".join(args))
        cmd = [os.path.join(self.EXE_PATH, exe_name)]
        cmd.extend(args)
        result = subprocess.check_output(cmd, cwd=self.EXE_PATH)
        return result


class Server:
    EXECUTOR_CLASS = Executor

    def __init__(self, exe_path, port, hmackey="", host=""):
        log.debug("Server setup...")
        if not host:
            host = socket.gethostname()
        log.debug("setting host: %s, port: %s", host, port)
        self.daemon = Pyro4.Daemon(host=host, port=int(port))
        if hmackey:
            log.debug("setting Hmac Key")
            self.daemon._pyroHmacKey = bytes(hmackey)
        executor_class = self.EXECUTOR_CLASS
        executor_class.EXE_PATH = exe_path
        log.debug("registering executor")
        self.uri = self.daemon.register(executor_class, executor_class.__name__)

    def start(self):
        log.debug("Server starting...")
        self.daemon.requestLoop()

    def stop(self):
        log.debug("Server stopping...")

        # !!! TODO !!!
        if sys.platform == 'win32':
            self.daemon.shutdown()
        else:
            self.daemon.close()

        log.debug("Server stopped")


class Client:
    EXECUTOR_CLASS_NAME = Executor.__name__

    def __init__(self, server, port, hmackey=""):
        executor_class_name = self.EXECUTOR_CLASS_NAME
        uri = "PYRO:{}@{}:{}".format(executor_class_name, server, port)
        self.proxy = Pyro4.Proxy(uri)
        if hmackey:
            self.proxy._pyroHmacKey = bytes(hmackey)

    def run(self, exe_name, *args):
        return self.proxy.run(exe_name, *args)


def main(argv):
    global SERVER
    parser = argparse.ArgumentParser()
    parser.add_argument('exe_path')
    parser.add_argument('port')
    parser.add_argument('--hmackey')
    args = parser.parse_args(argv)
    SERVER = Server(args.exe_path, args.port, args.hmackey)
    SERVER.start()


def sig_term_handler(sig, frame):
    global SERVER
    SERVER.stop()


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, sig_term_handler)
    main(sys.argv[1:])
