from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import argparse
import os.path
import socket
import subprocess

import Pyro4


CommunicationError = Pyro4.errors.CommunicationError


class Executor:
    @Pyro4.expose
    def run(self, exe_name, *args):
        cmd = [os.path.join(self.EXE_PATH, exe_name)]
        cmd.extend(args)
        result = subprocess.check_output(cmd, cwd=self.EXE_PATH)
        return result


class Server:
    EXECUTOR_CLASS = Executor

    def __init__(self, exe_path, port, hmackey="", host=""):
        if not host:
            host = socket.gethostname()
        self.daemon = Pyro4.Daemon(host=host, port=int(port))
        if hmackey:
            self.daemon._pyroHmacKey = bytes(hmackey)
        executor_class = self.EXECUTOR_CLASS
        executor_class.EXE_PATH = exe_path
        self.uri = self.daemon.register(executor_class, executor_class.__name__)

    def start(self):
        self.daemon.requestLoop()

    def stop(self):
        self.daemon.shutdown()


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


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('exe_path')
    parser.add_argument('port')
    parser.add_argument('--hmackey')
    args = parser.parse_args()
    s = Server(args.exe_path, args.port, args.hmackey)
    s.start()
