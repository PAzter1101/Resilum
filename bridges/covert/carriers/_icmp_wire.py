"""Build and parse ICMP/ICMPv6 echo packets carrying a wire datagram in the
echo data field. Each packet is tagged with the link's echo id (derived from
the server identity, see covert.icmpid) so the kernel's own echo-reply can be
dropped for ours alone (see covert.nftguard) while ordinary pings keep
working."""

import ipaddress

from scapy.layers.inet import ICMP, IP
from scapy.layers.inet6 import ICMPv6EchoReply, ICMPv6EchoRequest, IPv6
from scapy.packet import Packet, Raw

_ECHO_REQUEST = 8
_ECHO_REPLY = 0


def _is_v6(addr: str) -> bool:
    return ipaddress.ip_address(addr).version == 6


def build_request(dst: str, wire: bytes, ident: int):
    if _is_v6(dst):
        return IPv6(dst=dst) / ICMPv6EchoRequest(id=ident, data=wire)
    return IP(dst=dst) / ICMP(type=_ECHO_REQUEST, id=ident) / Raw(wire)


def build_response(dst: str, wire: bytes, ident: int):
    if _is_v6(dst):
        return IPv6(dst=dst) / ICMPv6EchoReply(id=ident, data=wire)
    return IP(dst=dst) / ICMP(type=_ECHO_REPLY, id=ident) / Raw(wire)


def parse_request(raw, ident: int):
    return _extract(raw, _ECHO_REQUEST, ICMPv6EchoRequest, ident)


def parse_response(raw, ident: int):
    got = _extract(raw, _ECHO_REPLY, ICMPv6EchoReply, ident)
    return None if got is None else got[1]


def _reparse(raw) -> Packet:
    if isinstance(raw, Packet):
        return raw
    data = bytes(raw)
    return IPv6(data) if data and (data[0] >> 4) == 6 else IP(data)


def _extract(raw, v4_type: int, v6_cls, ident: int):
    pkt = _reparse(raw)
    if IP in pkt and ICMP in pkt and Raw in pkt:
        icmp = pkt[ICMP]
        if icmp.type == v4_type and icmp.id == ident:
            return (pkt[IP].src, bytes(pkt[Raw].load))
    if IPv6 in pkt and v6_cls in pkt:
        echo = pkt[v6_cls]
        if echo.id == ident:
            return (pkt[IPv6].src, bytes(echo.data))
    return None
