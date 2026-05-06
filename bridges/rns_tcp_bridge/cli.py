"""Argument parsing and dispatch for ``python -m rns_tcp_bridge``."""

import argparse
import sys

import RNS

from . import connect, listen


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="rns_tcp_bridge",
        description="Bridge a TCP stream through a Reticulum RNS Link",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="RNS configuration directory (default: ~/.reticulum)",
    )
    parser.add_argument(
        "--loglevel",
        type=int,
        default=4,
        help="Reticulum log level (0=critical .. 7=extreme; default 4)",
    )
    sub = parser.add_subparsers(dest="mode", required=True)

    p_listen = sub.add_parser(
        "listen",
        help="Accept incoming Links and forward to a local TCP endpoint",
    )
    p_listen.add_argument(
        "--identity", required=True, help="path to bridge's RNS identity file"
    )
    p_listen.add_argument(
        "--service", default="generic", help="service aspect name (e.g. yggdrasil, tor)"
    )
    p_listen.add_argument(
        "--tcp", required=True, help="local TCP endpoint to forward to (host:port)"
    )

    p_connect = sub.add_parser(
        "connect",
        help="Listen on a TCP port and tunnel each connection via an RNS Link",
    )
    p_connect.add_argument(
        "--identity", required=True, help="path to bridge's RNS identity file"
    )
    p_connect.add_argument(
        "--service", default="generic", help="service aspect name (e.g. yggdrasil, tor)"
    )
    p_connect.add_argument(
        "--tcp", required=True, help="local TCP endpoint to bind to (host:port)"
    )
    p_connect.add_argument(
        "--target", default=None, help="hex hash of the listen-side identity to dial"
    )
    return parser


def main():
    args = _build_parser().parse_args()
    RNS.Reticulum(configdir=args.config, loglevel=args.loglevel)
    try:
        if args.mode == "listen":
            listen.run(args)
        elif args.mode == "connect":
            connect.run(args)
    except KeyboardInterrupt:
        sys.exit(0)
