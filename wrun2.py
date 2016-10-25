from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import json
import logging
import os
import socket
import subprocess

BUFFER_SIZE = 255

log = logging.getLogger(__name__)


class Socket(socket.socket):
    def __init__(self):
        super(Socket, self).__init__(socket.AF_INET, socket.SOCK_STREAM)


def daemon(server_address, execute, condition=lambda: True):
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


def executor(exe_path, command):
    exe_name, args = json.loads(command)
    log.debug("executor %s %s", exe_name, " ".join(args))
    cmd = [os.path.join(exe_path, exe_name)]
    cmd.extend(args)
    result = subprocess.check_output(cmd, cwd=exe_path)
    return result
