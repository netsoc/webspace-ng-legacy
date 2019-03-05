from unixrpc import UnixServerProxy

class Client(UnixServerProxy):
    def __init__(self, socket_path):
        UnixServerProxy.__init__(self, socket_path)
