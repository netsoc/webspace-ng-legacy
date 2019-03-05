from functools import wraps
import argparse

from .client import Client

def cmd(f):
    @wraps(f)
    def wrapper(args):
        with Client(args.socket_path) as client:
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

    subparsers = parser.add_subparsers()
    subparsers.required = True
    subparsers.dest = 'command'

    p_test = subparsers.add_parser('test', help='Test command',
                                  formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p_test.set_defaults(func=cmd(test))
