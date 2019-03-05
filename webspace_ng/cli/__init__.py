from functools import wraps
import os
import pwd
import grp
import argparse

from .. import ADMIN_GROUP
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

def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-c', '--socket', dest='socket_path',
                        help="Path to the daemon's Unix socket",
                        default='/var/lib/webspace-ng/unix.socket')
    current_user = pwd.getpwuid(os.geteuid()).pw_name
    if current_user in grp.getgrnam(ADMIN_GROUP).gr_mem:
        parser.add_argument('-u', '--user', help='User to perform operations as',
                            default=current_user)

    subparsers = parser.add_subparsers()
    subparsers.required = True
    subparsers.dest = 'command'

    p_test = subparsers.add_parser('test', help='Test command',
                                  formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p_test.set_defaults(func=cmd(test))

    args = parser.parse_args()
    args.func(args)
