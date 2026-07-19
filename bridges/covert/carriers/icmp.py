"""ICMP-echo carrier over standard-library sockets. Sending uses a raw socket
and the kernel adds the IP header. Receiving uses AF_PACKET with a kernel cBPF
filter (ICMP only), which taps below netfilter — so the covert server still sees
a request even though nftguard drops the kernel's duplicate echo-reply for it.
Locally-originated frames are skipped by packet type, so a node never re-ingests
its own echoes."""

import ctypes
import ipaddress
import select
import socket
import struct

from . import _icmp_wire as wire
from .base import Carrier

DEFAULT_MTU = 1400
_IPV4_OVERHEAD = 20 + 8  # IP + ICMP echo headers
_IPV6_OVERHEAD = 40 + 8  # IPv6 + ICMPv6 echo headers
_PACKET_OUTGOING = 4
_SO_ATTACH_FILTER = 26
# cBPF matching only ICMP/ICMPv6, so the kernel wakes us only for those instead
# of every IP packet. On an AF_PACKET SOCK_DGRAM socket the filter sees the L3
# packet: the IPv4 protocol is at byte 9, the IPv6 next-header at byte 6.
_ICMP_AT = {wire.ETH_P_IP: (9, 1), wire.ETH_P_IPV6: (6, 58)}


def _icmp_bpf(offset: int, value: int) -> tuple[bytes, int]:
    prog = [
        (0x30, 0, 0, offset),  # ldb [offset]
        (0x15, 0, 1, value),  # jeq value ? accept : reject
        (0x06, 0, 0, 0x0000FFFF),  # ret 0xffff (accept)
        (0x06, 0, 0, 0x00000000),  # ret 0 (reject)
    ]
    return b"".join(struct.pack("HBBI", *ins) for ins in prog), len(prog)


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
        self._send4: socket.socket | None = None
        self._send6: socket.socket | None = None

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

    def _raw_send(self, family: int, proto: int) -> socket.socket:
        s = socket.socket(family, socket.SOCK_RAW, proto)
        if self._iface:
            s.setsockopt(
                socket.SOL_SOCKET, socket.SO_BINDTODEVICE, self._iface.encode()
            )
        return s

    def send(self, packet) -> None:
        dest, msg = packet
        if wire.is_v6(dest):
            if self._send6 is None:
                self._send6 = self._raw_send(socket.AF_INET6, socket.IPPROTO_ICMPV6)
            self._send6.sendto(msg, (dest, 0))
        else:
            if self._send4 is None:
                self._send4 = self._raw_send(socket.AF_INET, socket.IPPROTO_ICMP)
            self._send4.sendto(msg, (dest, 0))

    def _capture(self, ethertype: int) -> socket.socket:
        s = socket.socket(socket.AF_PACKET, socket.SOCK_DGRAM, socket.htons(ethertype))
        bpf, count = _icmp_bpf(*_ICMP_AT[ethertype])
        buf = ctypes.create_string_buffer(bpf)
        s.setsockopt(
            socket.SOL_SOCKET,
            _SO_ATTACH_FILTER,
            struct.pack("@HP", count, ctypes.addressof(buf)),
        )
        if self._iface:
            s.bind((self._iface, ethertype))
        return s

    def sniff(self, on_raw, stop) -> None:
        v4 = self._capture(wire.ETH_P_IP)
        socks = [v4]
        try:
            socks.append(self._capture(wire.ETH_P_IPV6))
        except OSError:
            pass  # host without IPv6 — v4 only
        try:
            while stop is None or not stop.is_set():
                ready, _, _ = select.select(socks, [], [], 1.0)
                for s in ready:
                    data, addr = s.recvfrom(65535)
                    if addr[2] == _PACKET_OUTGOING:
                        continue
                    proto = wire.ETH_P_IP if s is v4 else wire.ETH_P_IPV6
                    on_raw((proto, data))
        finally:
            for s in socks:
                s.close()


def carrier(
    dst: str = "", iface: str = "", ident: int = 0, mtu: int = DEFAULT_MTU
) -> IcmpCarrier:
    return IcmpCarrier(dst=dst, iface=iface, ident=ident, mtu=mtu)
