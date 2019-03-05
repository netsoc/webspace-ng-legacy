#!/usr/bin/env python3
import argparse

import daemon, cli

def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    subparsers.required = True
    subparsers.dest = 'command'

    # Daemon subcommand
    p_daemon = subparsers.add_parser('daemon', help='Run management daemon',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    daemon.add_args(p_daemon)

    # Client subcommand
    p_cli = subparsers.add_parser('cli', help='Run management CLI',
                                  formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    cli.add_args(p_cli)

    # Pass the arguments to either the daemon / cli
    args = parser.parse_args()
    args.func(args)

if __name__ == '__main__':
    main()
