import logging
import signal
import threading
import argparse
import ipaddress
import os
from os import path

from munch import Munch
from ruamel.yaml import YAML

from ..unixrpc import ThreadedUnixRPCServer
from . import webspace

is_shutdown = False
def shutdown():
    global is_shutdown
    is_shutdown = True

    logging.info('shutting down...')
    server.shutdown()

def sig_handler(_num, _frame):
    if not is_shutdown:
        threading.Thread(target=shutdown).start()

def merge(source, destination):
    """
    run me with nosetests --with-doctest file.py

    >>> a = { 'first' : { 'all_rows' : { 'pass' : 'dog', 'number' : '1' } } }
    >>> b = { 'first' : { 'all_rows' : { 'fail' : 'cat', 'number' : '5' } } }
    >>> merge(b, a) == { 'first' : { 'all_rows' : { 'pass' : 'dog', 'fail' : 'cat', 'number' : '5' } } }
    True
    """
    for key, value in source.items():
        if isinstance(value, dict):
            # get node or create one
            node = destination.setdefault(key, {})
            merge(value, node)
        else:
            destination[key] = value

    return destination
def load_config():
    config = {
        'bind_socket': '/var/lib/webspace-ng/unix.socket',
        'lxd': {
            'socket': '/var/lib/lxd/unix.socket',
            'profile': 'webspace',
            'suffix': '-ws',
            'net': {
                'cidr': '10.233.0.0/24',
                'container_iface': 'eth0'
            }
        },
        'defaults': {
            'terminate_ssl': 'true',
            'startup_delay': '3'
        },
        'domain_suffix': '.ng.localhost',
        'max_startup_delay': 60,
        'run_limit': 20,
        'ports': {
            'proxy_bin': '/usr/local/bin/webspace-tcp-proxy',
            'start': 49152,
            'end': 65535,
            'max': 64
        }
    }

    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-c', '--config', help='Path to config file', default='/etc/webspaced.yaml')
    parser.add_argument('-v', '--verbose', action='count', help='Print more detailed log messages')
    parser.add_argument('-b', '--bind', dest='bind_socket',
                          help='Path to the Unix socket to bind on (default {})'.format(config['bind_socket']))
    parser.add_argument('-s', '--lxd-socket', dest='lxd_socket',
                          help='Path to the LXD Unix socket (default {})'.format(config['lxd']['socket']))
    parser.add_argument('--tcp-proxy-bin', dest='tcp_proxy_bin',
                          help='Path to the TCP proxy binary (default {})'.format(config['ports']['proxy_bin']))
    args = parser.parse_args()

    yaml = YAML()
    if not path.isfile(args.config):
        with open(args.config, 'w') as conf:
            yaml.dump(config, conf)

    with open(args.config) as conf:
        yaml_dict = yaml.load(conf)
        merge(yaml_dict, config)

    config = Munch.fromDict(config)
    config.lxd.net.cidr = ipaddress.IPv4Network(config.lxd.net.cidr)
    if args.bind_socket is not None:
        config.bind_socket = args.bind_socket
    if args.lxd_socket is not None:
        config.lxd.socket = args.lxd_socket
    if args.tcp_proxy_bin is not None:
        config.ports.proxy_bin = args.tcp_proxy_bin

    sock_dir = path.normpath(path.join(config.bind_socket, '..'))
    os.makedirs(sock_dir, exist_ok=True)

    level = logging.INFO
    if args.verbose and args.verbose >= 1:
        level = logging.DEBUG
    logging.basicConfig(level=level, format='[{asctime:s}] {levelname:s}: {message:s}', style='{')

    if config.run_limit <= 0:
        raise WebspaceError('Configuration must allow at least one container to run')

    return config

def main():
    config = load_config()

    global server
    server = ThreadedUnixRPCServer(config.bind_socket, allow_none=True)
    manager = webspace.Manager(config, server)

    # Shutdown handler
    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    server.register_instance(manager)

    # RPC main loop
    server.serve_forever()
    server.server_close()

    manager._stop()
