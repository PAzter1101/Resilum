"""Resolve the address a covert server announces: a chosen interface's IP, or
the default-route egress IP. Only a globally-routable address resolves — a
private/NAT one yields "" so the node stays client-only until an operator sets
`address` explicitly."""

import ipaddress

from scapy.arch import get_if_addr
from scapy.config import conf

_PROBE = "1.1.1.1"


def _iface_ip(interface: str) -> str:
    if interface:
        return get_if_addr(interface)
    return conf.route.route(_PROBE)[1]


def detect_address(interface: str = "") -> str:
    ip = _iface_ip(interface)
    if not ip or ip == "0.0.0.0":
        return ""
    return ip if ipaddress.ip_address(ip).is_global else ""
