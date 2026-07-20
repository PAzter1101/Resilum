"""Describe covert PipeInterfaces (the respawn command the supervisor runs) and
register them in the RNS Transport."""

import sys

import RNS
from RNS.Interfaces.PipeInterface import PipeInterface

from rns_tcp_bridge.discovery_plugins._transport import register_in_transport

from .carriers.icmp import DEFAULT_MTU

# Low bitrate makes RNS patient with the slow, lossy covert link (generous
# timeouts) and deprioritises it against faster interfaces; it is NOT a data
# throughput cap — RNS windows data by RTT, not by this value.
DEFAULT_BITRATE = 32_000


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


def register(config: dict, bitrate: int = DEFAULT_BITRATE) -> None:
    if any(getattr(i, "name", "") == config["name"] for i in RNS.Transport.interfaces):
        return
    iface = PipeInterface(RNS.Transport, config)
    iface.bitrate = (
        bitrate  # the PipeInterface otherwise guesses an unrealistic 1 Mbit/s
    )
    register_in_transport(iface)
