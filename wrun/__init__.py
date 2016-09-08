from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import os.path
import socket
import subprocess
import sys

import Pyro4


class Client:
    def __init__(self, server):
        uri = "PYRO:Executor@{}:3333".format(server)
        self.proxy = Pyro4.Proxy(uri)

    def run(self, exe_name, *args):
        return self.proxy.run(exe_name, *args)


class Executor:
    @Pyro4.expose
    def run(self, exe_name, *args):
        cmd = [os.path.join(self.EXE_PATH, exe_name)]
        cmd.extend(args)
        result = subprocess.check_output(cmd)
        return result


class Server:
    EXECUTOR_CLASS = Executor

    def __init__(self, exe_path, host="", port=3333):
        if not host:
            host = socket.gethostname()
        self.daemon = Pyro4.Daemon(host=host, port=port)
        executor_class = self.EXECUTOR_CLASS
        executor_class.EXE_PATH = exe_path
        self.uri = self.daemon.register(executor_class, executor_class.__name__)

    def start(self):
        self.daemon.requestLoop()

    def stop(self):
        self.daemon.shutdown()


if __name__ == '__main__':
    # just for test purpose
    exe_path = sys.argv[1]
    s = Server(exe_path)
    s.start()
