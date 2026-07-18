"""ICMP-echo carrier: the wire datagram rides in the echo data field."""

import os

from scapy.layers.inet import ICMP, IP
from scapy.packet import Raw
from scapy.sendrecv import send, sniff

from .base import Carrier

_ECHO_REQUEST = 8
_ECHO_REPLY = 0
_PATH_MTU = 1400
_IP_ICMP_HEADERS = 28
_CAPACITY = _PATH_MTU - _IP_ICMP_HEADERS


class IcmpCarrier(Carrier):
    name = "icmp"
    semantics = "poll"

    def __init__(self, dst: str = "", ident: int | None = None):
        self._dst = dst
        self._id = ident if ident is not None else (os.getpid() & 0xFFFF)

    @property
    def capacity(self) -> int:
        return _CAPACITY

    def build_request(self, reply_to, wire: bytes):
        return IP(dst=self._dst) / ICMP(type=_ECHO_REQUEST, id=self._id) / Raw(wire)

    def parse_request(self, raw):
        return self._extract(raw, _ECHO_REQUEST)

    def build_response(self, reply_to, wire: bytes):
        return IP(dst=reply_to) / ICMP(type=_ECHO_REPLY, id=self._id) / Raw(wire)

    def parse_response(self, raw):
        got = self._extract(raw, _ECHO_REPLY)
        return None if got is None else got[1]

    def _extract(self, raw, icmp_type):
        pkt = raw if isinstance(raw, IP) else IP(bytes(raw))
        if ICMP not in pkt or pkt[ICMP].type != icmp_type or Raw not in pkt:
            return None
        return (pkt[IP].src, bytes(pkt[Raw].load))

    def send(self, packet) -> None:
        send(packet, verbose=False)

    def sniff(self, on_raw, stop) -> None:
        sniff(
            filter="icmp",
            prn=lambda p: on_raw(p),
            store=False,
            stop_filter=lambda _p: stop is not None and stop.is_set(),
            timeout=1,
        )


def carrier(dst: str = "") -> IcmpCarrier:
    return IcmpCarrier(dst=dst)
