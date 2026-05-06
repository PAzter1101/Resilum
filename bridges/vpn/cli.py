"""CLI for the VPN module — `python -m bridges.vpn server|client ...`."""

import argparse
import sys

import RNS

from . import client, server


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bridges.vpn",
        description="Layer-3 VPN tunnel over a Reticulum Link.",
    )
    parser.add_argument("--config", default=None,
                        help="RNS configuration directory")
    parser.add_argument("--loglevel", type=int, default=4,
                        help="Reticulum log level (0..7)")
    sub = parser.add_subparsers(dest="role", required=True)

    p_server = sub.add_parser("server", help="anchor side (NATs to clearnet)")
    p_server.add_argument("--identity", required=True)
    p_server.add_argument("--tun",      default="resilum0")
    p_server.add_argument("--subnet",   default="10.20.0.0/24")
    p_server.add_argument("--uplink",   required=True,
                          help="host interface for MASQUERADE (e.g. eth0)")
    p_server.add_argument("--mtu", type=int, default=1280)

    p_client = sub.add_parser("client", help="leaf side (default route → tunnel)")
    p_client.add_argument("--identity", required=True)
    p_client.add_argument("--target",   default=None,
                          help="hex hash of a specific server's VPN destination "
                               "(optional; defaults to auto-discovery via RNS announces)")
    p_client.add_argument("--tun",      default="resilum0")
    p_client.add_argument("--mtu", type=int, default=1280)
    p_client.add_argument("--no-default-route", action="store_true",
                          help="skip rewriting the default route (advanced)")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    RNS.Reticulum(configdir=args.config, loglevel=args.loglevel)
    try:
        if args.role == "server":
            server.run(args)
        elif args.role == "client":
            client.run(args)
    except KeyboardInterrupt:
        sys.exit(0)
