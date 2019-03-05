import logging
import signal
import threading

from unixrpc import ThreadedUnixRPCServer
from . import webspace

is_shutdown = False
def shutdown():
    global is_shutdown
    is_shutdown = True

    logging.info('shutting down...')
    server.shutdown()

def sig_handler(num, frame):
    if not is_shutdown:
        threading.Thread(target=shutdown).start()

def add_args(parser):
    parser.set_defaults(func=run)
    parser.add_argument('-b', '--bind', dest='bind_socket',
                          help='Path to the Unix socket to bind on',
                          default='/var/lib/webspace-ng/unix.socket')
    parser.add_argument('-c', '--lxd-socket', dest='lxd_socket',
                          help='Path to the LXD Unix socket', default='/var/lib/lxd/unix.socket')

def run(args):
    logging.basicConfig(level=logging.DEBUG, format='[{asctime:s}] {levelname:s}: {message:s}', style='{')

    manager = webspace.Manager(args.lxd_socket)

    global server
    server = ThreadedUnixRPCServer(args.bind_socket, allow_none=True)

    # Shutdown handler
    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    server.register_instance(manager)

    # RPC main loop
    server.serve_forever()
    server.server_close()
