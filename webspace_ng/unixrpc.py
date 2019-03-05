import struct
import stat
import os
import pwd
import grp
import threading
import socket
import socketserver
from http.server import BaseHTTPRequestHandler
from socketserver import StreamRequestHandler, UnixStreamServer
from xmlrpc.server import SimpleXMLRPCDispatcher, SimpleXMLRPCRequestHandler
import http.client
import xmlrpc.client

SO_PEERCRED = 17

class UnixStreamRequestHandler(StreamRequestHandler):
    def setup(self):
        super(UnixStreamRequestHandler, self).setup()
        
        # Obtain client pid, uid and gid
        # Python does not expose a high-level interface for this
        creds = self.connection.getsockopt(socket.SOL_SOCKET, SO_PEERCRED, struct.calcsize('3i'))
        creds = struct.unpack('3i', creds)

        self.client_address = creds
        self.client_pid = creds[0]
        self.client_uid = creds[1]
        self.client_gid = creds[2]

        self.client_user = pwd.getpwuid(self.client_uid).pw_name
        self.client_group = grp.getgrgid(self.client_gid).gr_name

class UnixHTTPRequestHandler(UnixStreamRequestHandler, BaseHTTPRequestHandler):
    # We're using Unix sockets so this is irrelevant
    disable_nagle_algorithm = False

    def address_string(self):
        return 'unix+pid://{}?user={}&group={}'.format(
            self.client_pid, self.client_user, self.client_group)


_hacky_local = threading.local()
class UnixRPCRequestHandler(UnixHTTPRequestHandler, SimpleXMLRPCRequestHandler):
    # RPC2 only
    rpc_paths = ('/RPC2',)

    # Hacky way of passing the request through to the RPC functions
    # Shove the request into thread-local storage (yuck...)
    def setup(self):
        super(UnixRPCRequestHandler, self).setup()
        _hacky_local.current_req = self

class UnixRPCServer(UnixStreamServer, SimpleXMLRPCDispatcher):
    def __init__(self, addr, requestHandler=UnixRPCRequestHandler,
                 logRequests=True, allow_none=True, encoding=None,
                 bind_and_activate=True, use_builtin_types=False,
                 socket_mode=stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO):
        self.logRequests = logRequests

        try:
            os.unlink(addr)
        except OSError:
            if os.path.exists(addr):
                raise

        SimpleXMLRPCDispatcher.__init__(self, allow_none, encoding, use_builtin_types)
        UnixStreamServer.__init__(self, addr, requestHandler, bind_and_activate)

        os.chmod(addr, socket_mode)

    @property
    def current_request(self):
        return _hacky_local.current_req

class ThreadedUnixRPCServer(socketserver.ThreadingMixIn, UnixRPCServer):
    pass



class UnixStreamHTTPConnection(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self.host)

class UnixStreamTransport(xmlrpc.client.Transport, object):
    def __init__(self, socket_path):
        self.socket_path = socket_path
        super(UnixStreamTransport, self).__init__()

    def make_connection(self, host):
        return UnixStreamHTTPConnection(self.socket_path)

class UnixServerProxy(xmlrpc.client.ServerProxy):
    def __init__(self, socket_path, **kwargs):
        xmlrpc.client.ServerProxy.__init__(self, 'http://its-a-unix.socket',
                                           transport=UnixStreamTransport(socket_path), **kwargs)
