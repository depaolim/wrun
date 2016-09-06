from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import subprocess

import Pyro4


class Client:
    def __init__(self, server):
        uri = "PYRO:Executor@localhost:3333"
        self.proxy = Pyro4.Proxy(uri)
        
    def run(self, exe_name, *args):
        return self.proxy.run(exe_name, *args)


class Executor:
    @Pyro4.expose
    def run(self, exe_name, *args):
        result = subprocess.check_output([exe_name] + list(args))
        return result
        
        
class Server:
    def __init__(self):
        self.daemon = Pyro4.Daemon(host="localhost", port=3333)
        self.uri = self.daemon.register(Executor, "Executor")
        
    def start(self):
        self.daemon.requestLoop()

    def stop(self):
        self.daemon.shutdown()
        
        
if __name__ == '__main__':
    s = Server()
    s.start()