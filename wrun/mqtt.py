import selectors
import socket


class Log:
    @classmethod
    def debug(cls, msg, *args):
        print(msg, *args)


log = Log()


class Host:
    def __init__(self, pool, sock=None):
        self.pool = pool
        self.sock = sock or socket.socket()
        self.sock.setblocking(False)
        log.debug("Host.__init__", self.sock)
        self._dispatch = None

    def set_dispatch(self, _dispatch):
        assert not self._dispatch
        self._dispatch = _dispatch
        self.pool.register(self.sock, selectors.EVENT_READ, self.read)

    def read(self, data):
        assert False, "to be implemented"

    def destroy(self):
        log.debug("Host.Destroy", self.sock)
        self.pool.unregister(self.sock)
        self.sock.close()


class Connection(Host):
    def read(self, sock):
        assert sock == self.sock
        data = self.sock.recv(1024)
        self._dispatch(data)

    def write(self, data):
        self.sock.sendall(data)


class NewConnection(Connection):
    def __init__(self, pool, address):
        super().__init__(pool)
        self.sock.connect_ex(address)


class Listener(Host):
    def __init__(self, pool, address):
        super().__init__(pool)
        self.sock.bind(address)
        self.sock.listen()

    def read(self, sock):
        assert sock == self.sock
        client_socket, client_address = sock.accept()
        log.debug("new Connection", client_socket)
        client = Connection(self.pool, client_socket)
        self._dispatch(client)


class Channel:
    def __init__(self, client, remote):
        self.client = client
        self.remote = remote
        self.client.set_dispatch(self.client_data)
        self.remote.set_dispatch(self.remote_data)

    def client_data(self, data):
        log.debug("read_client", data)
        if data:
            log.debug("remote send...")
            self.remote.write(data)
        # TODO: ... perché è necessario?!?
        if data == b'\xe0\x00':
            log.debug("client disconnect")
            self.client.destroy()

    def remote_data(self, data):
        log.debug("read_remote", data)
        if data:
            log.debug("client send...")
            self.client.write(data)
        else:
            log.debug("remote disconnect")
            self.remote.destroy()


class Broker:
    def __init__(self):
        self.hosts = selectors.DefaultSelector()
        self.doorkeeper = Listener(self.hosts, ("localhost", 1883))
        self.doorkeeper.set_dispatch(self.create)

    def create(self, client):
        remote = NewConnection(self.hosts, ("localhost", 1884))
        Channel(client, remote)

    def process(self):
        selected = self.hosts.select(timeout=1)
        if not selected:
            log.debug("select timeout")
            return
        for key, mask in selected:
            callback = key.data
            callback(key.fileobj)

    def stop(self):
        self.doorkeeper.destroy()
        self.hosts.close()
