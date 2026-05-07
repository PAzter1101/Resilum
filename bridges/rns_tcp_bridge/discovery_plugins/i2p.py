"""I2P b32-destination discovery plugin.

Endpoint format: ``b"<hash>.b32.i2p:<port>"``. The local i2pd daemon
is expected to expose the local Reticulum TCP listener as a server
tunnel; the resulting .b32.i2p address is read from the hidden-service
hostname file at announce time.

Outbound (consume_endpoint) works any time i2pd's SOCKS5 proxy is
running on 127.0.0.1:4447 (default), even without a configured
inbound tunnel — peers announced via b32.i2p are dialed through the
SOCKS5 proxy with rdns=True.
"""

import re

import RNS
from socks_tcp_interface import SocksTCPClientInterface

from ._transport import register_in_transport
from .base import DiscoveryPlugin

HOSTNAME_PATH = "/config/i2p/hidden_service/hostname"
SOCKS_HOST = "127.0.0.1"
SOCKS_PORT = 4447
RNS_PORT = 4242
ENDPOINT_RE = re.compile(rb"^([a-z2-7]+\.b32\.i2p):(\d+)$")


class _I2P(DiscoveryPlugin):
    def produce_endpoint(self) -> bytes:
        with open(HOSTNAME_PATH) as fh:
            b32 = fh.read().strip()
        return f"{b32}:{RNS_PORT}".encode()

    def consume_endpoint(self, payload: bytes) -> None:
        match = ENDPOINT_RE.match(payload.strip())
        if not match:
            RNS.log(f"[discovery:i2p] malformed payload {payload!r}", RNS.LOG_DEBUG)
            return
        host = match.group(1).decode()
        port = int(match.group(2))
        name = f"I2PDiscovered[{host}]:{port}"
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
        RNS.log(
            f"[discovery:i2p] added interface {name} via i2pd SOCKS",
            RNS.LOG_INFO,
        )


def plugin() -> DiscoveryPlugin:
    return _I2P()
