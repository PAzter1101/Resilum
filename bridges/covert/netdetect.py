"""Resolve the address a covert server announces: a chosen interface's IP, or
the default-route egress IP. Only a globally-routable address resolves — a
private/NAT one yields "" so the node stays client-only until an operator sets
`address` explicitly."""

import fcntl
import ipaddress
import socket
import struct

_PROBE = "1.1.1.1"
_SIOCGIFADDR = 0x8915


def _egress_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((_PROBE, 80))
        ip: str = s.getsockname()[0]
        return ip
    except OSError:
        return ""
    finally:
        s.close()


def _interface_ip(interface: str) -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        packed = struct.pack("256s", interface.encode()[:15])
        return socket.inet_ntoa(fcntl.ioctl(s.fileno(), _SIOCGIFADDR, packed)[20:24])
    except OSError:
        return ""
    finally:
        s.close()


def _iface_ip(interface: str) -> str:
    return _interface_ip(interface) if interface else _egress_ip()


def detect_address(interface: str = "") -> str:
    ip = _iface_ip(interface)
    if not ip or ip == "0.0.0.0":
        return ""
    return ip if ipaddress.ip_address(ip).is_global else ""
