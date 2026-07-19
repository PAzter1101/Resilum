"""Covert discovery: announce this node's endpoint(s) and, on a peer's signed
announce, bring up a client PipeInterface sealed to the peer's identity."""

import argparse
import sys
import threading
import time

import RNS

from rns_tcp_bridge import announce_payload
from rns_tcp_bridge.constants import ANNOUNCE_INTERVAL_SECONDS
from rns_tcp_bridge.identity import load_or_create_identity

from . import nftguard, rendezvous
from .carriers.icmp import DEFAULT_MTU
from .endpoint import pack_endpoint, parse_endpoint
from .icmpid import tunnel_id
from .interfaces import (
    DEFAULT_BITRATE,
    client_interface_config,
    register,
    server_interface_config,
)
from .netdetect import detect_address


def _register_peer(
    carrier: str,
    addr_csv: str,
    announced_identity,
    interface: str = "",
    mtu: int = DEFAULT_MTU,
    bitrate: int = DEFAULT_BITRATE,
) -> None:
    addr = addr_csv.split(",")[0]
    pubhex = announced_identity.get_public_key().hex()
    register(client_interface_config(carrier, addr, pubhex, interface, mtu), bitrate)


class _Handler:
    receive_path_responses = False

    def __init__(
        self,
        carrier: str,
        interface: str = "",
        mtu: int = DEFAULT_MTU,
        bitrate: int = DEFAULT_BITRATE,
    ):
        self.aspect_filter = f"resilum.discovery.covert_{carrier}"
        self._carrier = carrier
        self._interface = interface
        self._mtu = mtu
        self._bitrate = bitrate
        self._handled: set = set()
        self._lock = threading.Lock()

    def received_announce(self, destination_hash, announced_identity, app_data):
        parsed = announce_payload.parse(app_data)
        if parsed is None or parsed.endpoint is None or announced_identity is None:
            return
        ep = parse_endpoint(parsed.endpoint)
        if ep is None or ep[0] != self._carrier:
            return
        with self._lock:
            if announced_identity.hash in self._handled:
                return
        threading.Thread(
            target=self._resolve, args=(announced_identity,), daemon=True
        ).start()

    def _resolve(self, announced_identity):
        addr_csv = rendezvous.request_endpoint(announced_identity, self._carrier)
        if not addr_csv:
            return
        _register_peer(
            self._carrier,
            addr_csv,
            announced_identity,
            self._interface,
            self._mtu,
            self._bitrate,
        )
        with self._lock:
            self._handled.add(announced_identity.hash)


def _announce_addresses(serve: bool, addresses: list, interface: str) -> list:
    if not serve:
        return []
    if addresses:
        return addresses
    auto = detect_address(interface)
    return [auto] if auto else []


def run(
    carrier, role, addresses, interface, mtu, bitrate, identity_path, config
) -> None:
    RNS.Reticulum(config)
    identity = load_or_create_identity(identity_path)
    if role in ("client", "both"):
        RNS.Transport.register_announce_handler(
            _Handler(carrier, interface, mtu, bitrate)
        )
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
    register(server_interface_config(carrier, identity_path, interface, mtu), bitrate)
    dest = RNS.Destination(
        identity,
        RNS.Destination.IN,
        RNS.Destination.SINGLE,
        "resilum",
        "discovery",
        f"covert_{carrier}",
    )
    endpoint = pack_endpoint(carrier, ",".join(addrs))
    dest.register_request_handler(
        rendezvous.ENDPOINT_PATH,
        response_generator=rendezvous.endpoint_responder(endpoint),
        allow=RNS.Destination.ALLOW_ALL,
    )
    capability = announce_payload.pack(pack_endpoint(carrier, ""))
    while True:
        dest.announce(app_data=capability)
        time.sleep(ANNOUNCE_INTERVAL_SECONDS)


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="covert.discovery")
    p.add_argument("carrier")
    p.add_argument("--role", default="both", choices=["server", "client", "both"])
    p.add_argument("--address", action="append", dest="addresses", default=[])
    p.add_argument("--interface", default="")
    p.add_argument("--mtu", type=int, default=DEFAULT_MTU)
    p.add_argument("--bitrate", type=int, default=DEFAULT_BITRATE)
    p.add_argument("--identity", required=True)
    p.add_argument("--config", default="/config/reticulum")
    args = p.parse_args(argv)
    run(
        args.carrier,
        args.role,
        args.addresses,
        args.interface,
        args.mtu,
        args.bitrate,
        args.identity,
        args.config,
    )


if __name__ == "__main__":
    main()
