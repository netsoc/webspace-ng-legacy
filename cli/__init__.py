from functools import wraps
import os
import argparse

from .client import Client

def cmd(f):
    @wraps(f)
    def wrapper(args):
        user = args.user if 'user' in args else None
        with Client(args.socket_path, user=user) as client:
            return f(client, args)
    return wrapper

def test(client, args):
    print('Running containers:')
    for c in client.test():
        print(' - {}'.format(c))

def add_args(parser):
    parser.add_argument('-c', '--socket', dest='socket_path',
                        help="Path to the daemon's Unix socket",
                        default='/var/lib/webspace-ng/unix.socket')
    if os.geteuid() == 0:
        parser.add_argument('-u', '--user', help='User to perform operations as',
                            default='root')

    subparsers = parser.add_subparsers()
    subparsers.required = True
    subparsers.dest = 'command'

    p_test = subparsers.add_parser('test', help='Test command',
                                  formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p_test.set_defaults(func=cmd(test))
