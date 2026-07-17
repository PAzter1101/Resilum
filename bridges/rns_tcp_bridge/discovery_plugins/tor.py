"""Tor onion-service discovery plugin.

Endpoint format: ``b"<hash>.onion:<port>"``. The local Tor daemon is
configured (see /opt/resilum/defaults/torrc) to expose the local
Reticulum TCP listener as a hidden service; the resulting .onion
hostname is read from the hidden-service directory at announce time.

When a peer's announcement arrives, a TCPClientInterface is added to
the running RNS stack, dialing the announced .onion through the local
Tor SOCKS5 proxy (127.0.0.1:9050).
"""

import re

import RNS

from socks_tcp_interface import SocksTCPClientInterface

from ._transport import register_in_transport
from .base import DiscoveryPlugin

HOSTNAME_PATH = "/config/tor/hidden_service/hostname"
SOCKS_HOST = "127.0.0.1"
SOCKS_PORT = 9050
RNS_PORT = 4242
ENDPOINT_RE = re.compile(rb"^([a-z2-7]{16,56}\.onion):(\d+)$")


class _Tor(DiscoveryPlugin):
    def produce_endpoint(self) -> bytes:
        with open(HOSTNAME_PATH) as fh:
            onion = fh.read().strip()
        return f"{onion}:{RNS_PORT}".encode()

    def consume_endpoint(self, payload: bytes) -> None:
        match = ENDPOINT_RE.match(payload.strip())
        if not match:
            RNS.log(f"[discovery:tor] malformed payload {payload!r}", RNS.LOG_DEBUG)
            return
        host = match.group(1).decode()
        port = int(match.group(2))
        name = f"TorDiscovered[{host}]:{port}"
        if any(
            getattr(iface, "name", "") == name for iface in RNS.Transport.interfaces
        ):
            return
        iface = SocksTCPClientInterface(
            owner=RNS.Transport,
            configuration={
                "name": name,
                "target_host": host,
                "target_port": port,
                "socks_proxy_host": SOCKS_HOST,
                "socks_proxy_port": SOCKS_PORT,
            },
        )
        register_in_transport(iface)
        RNS.log(f"[discovery:tor] added interface {name} via Tor SOCKS", RNS.LOG_INFO)


def plugin() -> DiscoveryPlugin:
    return _Tor()
