"""Covert discovery: announce this node's endpoint(s) and, on a peer's signed
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

from . import nftguard
from .carriers.icmp import DEFAULT_MTU
from .endpoint import pack_endpoint, parse_endpoint
from .icmpid import tunnel_id
from .netdetect import detect_address


def _interface_name(carrier: str, addr: str) -> str:
    return f"CovertDiscovered[{carrier}:{addr}]"


def _options(interface: str, mtu: int) -> str:
    opts = f" --interface {interface}" if interface else ""
    return opts + (f" --mtu {mtu}" if mtu != DEFAULT_MTU else "")


def client_interface_config(
    carrier: str, addr: str, pubhex: str, interface: str = "", mtu: int = DEFAULT_MTU
) -> dict:
    command = (
        f"{sys.executable} -m covert {carrier} client "
        f"--dst {addr} --server-identity {pubhex}"
    )
    return {
        "name": _interface_name(carrier, addr),
        "command": command + _options(interface, mtu),
        "respawn_delay": 5,
    }


def server_interface_config(
    carrier: str, identity_path: str, interface: str = "", mtu: int = DEFAULT_MTU
) -> dict:
    command = f"{sys.executable} -m covert {carrier} server --identity {identity_path}"
    return {
        "name": f"CovertServer[{carrier}]",
        "command": command + _options(interface, mtu),
        "respawn_delay": 5,
    }


def _register(config: dict) -> None:
    if any(getattr(i, "name", "") == config["name"] for i in RNS.Transport.interfaces):
        return
    register_in_transport(PipeInterface(RNS.Transport, config))


def _register_peer(
    carrier: str,
    addr_csv: str,
    announced_identity,
    interface: str = "",
    mtu: int = DEFAULT_MTU,
) -> None:
    addr = addr_csv.split(",")[0]
    pubhex = announced_identity.get_public_key().hex()
    _register(client_interface_config(carrier, addr, pubhex, interface, mtu))


class _Handler:
    receive_path_responses = False

    def __init__(self, carrier: str, interface: str = "", mtu: int = DEFAULT_MTU):
        self.aspect_filter = f"resilum.discovery.covert_{carrier}"
        self._carrier = carrier
        self._interface = interface
        self._mtu = mtu

    def received_announce(self, destination_hash, announced_identity, app_data):
        parsed = announce_payload.parse(app_data)
        if parsed is None or parsed.endpoint is None or announced_identity is None:
            return
        ep = parse_endpoint(parsed.endpoint)
        if ep is None or ep[0] != self._carrier:
            return
        _register_peer(ep[0], ep[1], announced_identity, self._interface, self._mtu)


def _announce_addresses(serve: bool, addresses: list, interface: str) -> list:
    if not serve:
        return []
    if addresses:
        return addresses
    auto = detect_address(interface)
    return [auto] if auto else []


def run(carrier, role, addresses, interface, mtu, identity_path, config) -> None:
    RNS.Reticulum(config)
    identity = load_or_create_identity(identity_path)
    if role in ("client", "both"):
        RNS.Transport.register_announce_handler(_Handler(carrier, interface, mtu))
    addrs = _announce_addresses(role in ("server", "both"), addresses, interface)
    if addrs and not nftguard.install(tunnel_id(identity.get_public_key())):
        print(
            "covert: could not install echo-suppression rule; serving disabled",
            file=sys.stderr,
        )
        addrs = []
    if not addrs:
        threading.Event().wait()
        return
    _register(server_interface_config(carrier, identity_path, interface, mtu))
    dest = RNS.Destination(
        identity,
        RNS.Destination.IN,
        RNS.Destination.SINGLE,
        "resilum",
        "discovery",
        f"covert_{carrier}",
    )
    endpoint = pack_endpoint(carrier, ",".join(addrs))
    while True:
        dest.announce(app_data=announce_payload.pack(endpoint))
        time.sleep(ANNOUNCE_INTERVAL_SECONDS)


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="covert.discovery")
    p.add_argument("carrier")
    p.add_argument("--role", default="both", choices=["server", "client", "both"])
    p.add_argument("--address", action="append", dest="addresses", default=[])
    p.add_argument("--interface", default="")
    p.add_argument("--mtu", type=int, default=DEFAULT_MTU)
    p.add_argument("--identity", required=True)
    p.add_argument("--config", default="/config/reticulum")
    args = p.parse_args(argv)
    run(
        args.carrier,
        args.role,
        args.addresses,
        args.interface,
        args.mtu,
        args.identity,
        args.config,
    )


if __name__ == "__main__":
    main()
