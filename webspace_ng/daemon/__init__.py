import logging
import signal
import threading
import argparse

from ..unixrpc import ThreadedUnixRPCServer
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

def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-b', '--bind', dest='bind_socket',
                          help='Path to the Unix socket to bind on',
                          default='/var/lib/webspace-ng/unix.socket')
    parser.add_argument('-c', '--lxd-socket', dest='lxd_socket',
                          help='Path to the LXD Unix socket', default='/var/lib/lxd/unix.socket')
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG, format='[{asctime:s}] {levelname:s}: {message:s}', style='{')

    global server
    server = ThreadedUnixRPCServer(args.bind_socket, allow_none=True)
    manager = webspace.Manager(args.lxd_socket, server)

    # Shutdown handler
    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    server.register_instance(manager)

    # RPC main loop
    server.serve_forever()
    server.server_close()

    manager.stop()
