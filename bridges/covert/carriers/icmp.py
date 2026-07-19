"""ICMP-echo carrier: the wire datagram rides in the echo data field, over
IPv4 or IPv6 by destination family. Sniffing takes only inbound traffic, so a
node never re-ingests its own outbound (or a sibling role's) echoes. The echo
id marking our packets is the link's, derived from the server identity."""

import ipaddress

from scapy.sendrecv import send, sniff

from . import _icmp_wire as wire
from .base import Carrier

DEFAULT_MTU = 1400
_IPV4_OVERHEAD = 20 + 8  # IP + ICMP echo headers
_IPV6_OVERHEAD = 40 + 8  # IPv6 + ICMPv6 echo headers


class IcmpCarrier(Carrier):
    name = "icmp"
    semantics = "poll"

    def __init__(
        self, dst: str = "", iface: str = "", ident: int = 0, mtu: int = DEFAULT_MTU
    ):
        self._dst = dst
        self._iface = iface
        self._id = ident
        self._mtu = mtu

    def _capacity_for(self, dest) -> int:
        v6 = not dest or ipaddress.ip_address(dest).version == 6
        return self._mtu - (_IPV6_OVERHEAD if v6 else _IPV4_OVERHEAD)

    @property
    def capacity(self) -> int:
        return self._capacity_for(self._dst)

    def capacity_for(self, dest) -> int:
        return self._capacity_for(dest)

    def build_request(self, reply_to, data: bytes):
        return wire.build_request(self._dst, data, self._id)

    def parse_request(self, raw):
        return wire.parse_request(raw, self._id)

    def build_response(self, reply_to, data: bytes):
        return wire.build_response(reply_to, data, self._id)

    def parse_response(self, raw):
        return wire.parse_response(raw, self._id)

    def send(self, packet) -> None:
        send(packet, iface=self._iface or None, verbose=False)

    def sniff(self, on_raw, stop) -> None:
        sniff(
            iface=self._iface or None,
            filter="inbound and (icmp or icmp6)",
            prn=lambda p: on_raw(p),
            store=False,
            stop_filter=lambda _p: stop is not None and stop.is_set(),
            timeout=1,
        )


def carrier(
    dst: str = "", iface: str = "", ident: int = 0, mtu: int = DEFAULT_MTU
) -> IcmpCarrier:
    return IcmpCarrier(dst=dst, iface=iface, ident=ident, mtu=mtu)
