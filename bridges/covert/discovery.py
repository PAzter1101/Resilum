"""Covert discovery: announce this node's endpoint and, on a peer's signed
announce, bring up a client PipeInterface sealed to the peer's identity."""

import argparse
import sys
import threading
import time

import RNS
from RNS.Interfaces.PipeInterface import PipeInterface

from rns_tcp_bridge import announce_payload
from rns_tcp_bridge.constants import ANNOUNCE_INTERVAL_SECONDS
from rns_tcp_bridge.discovery_plugins._transport import register_in_transport
from rns_tcp_bridge.identity import load_or_create_identity

from .endpoint import pack_endpoint, parse_endpoint


def _interface_name(carrier: str, addr: str) -> str:
    return f"CovertDiscovered[{carrier}:{addr}]"


def client_interface_config(carrier: str, addr: str, pubhex: str) -> dict:
    return {
        "name": _interface_name(carrier, addr),
        "command": (
            f"{sys.executable} -m covert {carrier} client "
            f"--dst {addr} --server-identity {pubhex}"
        ),
        "respawn_delay": 5,
    }


def server_interface_config(carrier: str, identity_path: str) -> dict:
    return {
        "name": f"CovertServer[{carrier}]",
        "command": (
            f"{sys.executable} -m covert {carrier} server --identity {identity_path}"
        ),
        "respawn_delay": 5,
    }


def _register(config: dict) -> None:
    if any(getattr(i, "name", "") == config["name"] for i in RNS.Transport.interfaces):
        return
    register_in_transport(PipeInterface(RNS.Transport, config))


def _register_peer(carrier: str, addr: str, announced_identity) -> None:
    pubhex = announced_identity.get_public_key().hex()
    _register(client_interface_config(carrier, addr, pubhex))


class _Handler:
    receive_path_responses = False

    def __init__(self, carrier: str):
        self.aspect_filter = f"resilum.discovery.covert_{carrier}"
        self._carrier = carrier

    def received_announce(self, destination_hash, announced_identity, app_data):
        parsed = announce_payload.parse(app_data)
        if parsed is None or parsed.endpoint is None or announced_identity is None:
            return
        ep = parse_endpoint(parsed.endpoint)
        if ep is None or ep[0] != self._carrier:
            return
        _register_peer(ep[0], ep[1], announced_identity)


def run(carrier: str, address: str, identity_path: str, config: str) -> None:
    RNS.Reticulum(config)
    identity = load_or_create_identity(identity_path)
    RNS.Transport.register_announce_handler(_Handler(carrier))
    if not address:
        threading.Event().wait()
        return
    _register(server_interface_config(carrier, identity_path))
    dest = RNS.Destination(
        identity,
        RNS.Destination.IN,
        RNS.Destination.SINGLE,
        "resilum",
        "discovery",
        f"covert_{carrier}",
    )
    endpoint = pack_endpoint(carrier, address)
    while True:
        dest.announce(app_data=announce_payload.pack(endpoint))
        time.sleep(ANNOUNCE_INTERVAL_SECONDS)


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="covert.discovery")
    p.add_argument("carrier")
    p.add_argument("--address", dest="address", default="")
    p.add_argument("--identity", required=True)
    p.add_argument("--config", default="/config/reticulum")
    args = p.parse_args(argv)
    run(args.carrier, args.address, args.identity, args.config)


if __name__ == "__main__":
    main()
