import os
import pwd
import grp
import argparse

from .. import ADMIN_GROUP
from .commands import *

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

    p_images = subparsers.add_parser('images', help='List available images')
    p_images.set_defaults(func=images)

    p_init = subparsers.add_parser('init', help='Create your container',
                                   formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p_init.add_argument('image',
                        help='Image alias / fingerprint to create your container from')
    p_init.set_defaults(func=init)

    p_status = subparsers.add_parser('status', help='Show the status of your container')
    p_status.set_defaults(func=status)

    args = parser.parse_args()
    args.func(args)
