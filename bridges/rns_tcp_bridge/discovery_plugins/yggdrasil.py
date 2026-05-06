"""Yggdrasil discovery plugin.

Endpoint format is the bytes ``"[<ipv6>]:<port>\\n"`` — an IPv6
address suitable for `RNS.TCPClientInterface` plus the RNS-listener
port. The RNS server-side already listens on `[::]:4242` (default
config), so peers reach us through Yggdrasil simply by dialing the
ygg-IPv6 of the local node.
"""

import re
import subprocess

import RNS
from RNS.Interfaces.TCPInterface import TCPClientInterface

from .base import DiscoveryPlugin

DEFAULT_RNS_PORT = 4242
ENDPOINT_RE = re.compile(rb"^\[([0-9a-fA-F:]+)\]:(\d+)$")
IPV6_LINE_RE = re.compile(r"IPv6 address:\s*([0-9a-fA-F:]+)")


class _Yggdrasil(DiscoveryPlugin):
    def produce_endpoint(self) -> bytes:
        out = subprocess.check_output(["yggdrasilctl", "getSelf"], text=True)
        match = IPV6_LINE_RE.search(out)
        if not match:
            raise RuntimeError("yggdrasilctl getSelf produced no IPv6 line")
        ipv6 = match.group(1).strip()
        return f"[{ipv6}]:{DEFAULT_RNS_PORT}".encode()

    def consume_endpoint(self, payload: bytes) -> None:
        match = ENDPOINT_RE.match(payload.strip())
        if not match:
            RNS.log(
                f"[discovery:yggdrasil] malformed payload {payload!r}", RNS.LOG_DEBUG
            )
            return
        host = match.group(1).decode()
        port = int(match.group(2))
        name = f"YggdrasilDiscovered[{host}]:{port}"
        if any(
            getattr(iface, "name", "") == name for iface in RNS.Transport.interfaces
        ):
            return  # already added
        iface = TCPClientInterface(
            owner=RNS.Transport,
            configuration={"name": name, "target_host": host, "target_port": port},
        )
        RNS.Transport.interfaces.append(iface)
        RNS.log(f"[discovery:yggdrasil] added interface {name}", RNS.LOG_INFO)


def plugin() -> DiscoveryPlugin:
    return _Yggdrasil()
