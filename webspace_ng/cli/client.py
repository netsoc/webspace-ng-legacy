from ..unixrpc import UnixServerProxy

# Copied from xmlrpc.client._Method
class _UserMethod:
    def __init__(self, send, name, user):
        self.__send = send
        self.__name = name
        self.__user = user
    def __getattr__(self, name):
        return _UserMethod(self.__send, "%s.%s" % (self.__name, name), self.__user)
    def __call__(self, *args):
        if self.__user is not None:
            # The server expects us to pass the desired user as an argument
            # if a member of the `webspace-admin` group
            args = (self.__user,) + args
            return self.__send(self.__name, args)

        return self.__send(self.__name, args)

class Client(UnixServerProxy):
    def __init__(self, socket_path, user=None):
        UnixServerProxy.__init__(self, socket_path)
        self.user = user

    def __getattr__(self, name):
        return _UserMethod(self._ServerProxy__request, name, self.user)
