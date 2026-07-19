"""Build and parse ICMP/ICMPv6 echo messages carrying the wire datagram in the
echo data field, using only the standard library. Building emits the ICMP
message alone — the kernel adds the IP header on send (and the ICMPv6 checksum).
Parsing takes the L3 IP packet captured via AF_PACKET, tagged with its
ethertype."""

import ipaddress
import socket
import struct

_REQUEST_V4, _REPLY_V4 = 8, 0
_REQUEST_V6, _REPLY_V6 = 128, 129
_PROTO_ICMP, _PROTO_ICMPV6 = 1, 58
ETH_P_IP, ETH_P_IPV6 = 0x0800, 0x86DD
_ECHO = struct.Struct("!BBHHH")  # type, code, checksum, id, seq


def is_v6(addr: str) -> bool:
    return ipaddress.ip_address(addr).version == 6


def _checksum(data: bytes) -> int:
    if len(data) % 2:
        data += b"\x00"
    total: int = sum(struct.unpack("!%dH" % (len(data) // 2), data))
    total = (total >> 16) + (total & 0xFFFF)
    total += total >> 16
    return (~total) & 0xFFFF


def _echo(icmp_type: int, ident: int, payload: bytes, v6: bool) -> bytes:
    body = _ECHO.pack(icmp_type, 0, 0, ident, 0) + payload
    if v6:  # the kernel fills the ICMPv6 checksum on send
        return body
    return body[:2] + struct.pack("!H", _checksum(body)) + body[4:]


def build_request(dst: str, payload: bytes, ident: int):
    v6 = is_v6(dst)
    return (dst, _echo(_REQUEST_V6 if v6 else _REQUEST_V4, ident, payload, v6))


def build_response(dst: str, payload: bytes, ident: int):
    v6 = is_v6(dst)
    return (dst, _echo(_REPLY_V6 if v6 else _REPLY_V4, ident, payload, v6))


def parse_request(raw, ident: int):
    return _extract(raw, _REQUEST_V4, _REQUEST_V6, ident)


def parse_response(raw, ident: int):
    got = _extract(raw, _REPLY_V4, _REPLY_V6, ident)
    return None if got is None else got[1]


def _echo_payload(icmp: bytes, want_type: int, ident: int):
    if len(icmp) < _ECHO.size:
        return None
    itype, _code, _ck, iid, _seq = _ECHO.unpack(icmp[: _ECHO.size])
    if itype != want_type or iid != ident:
        return None
    return icmp[_ECHO.size :]


def _extract(raw, v4_type: int, v6_type: int, ident: int):
    proto, pkt = raw
    if proto == ETH_P_IP:
        if len(pkt) < 20 or pkt[9] != _PROTO_ICMP:
            return None
        ihl = (pkt[0] & 0x0F) * 4
        payload = _echo_payload(pkt[ihl:], v4_type, ident)
        src = socket.inet_ntop(socket.AF_INET, pkt[12:16])
    elif proto == ETH_P_IPV6:
        if len(pkt) < 40 or pkt[6] != _PROTO_ICMPV6:
            return None
        payload = _echo_payload(pkt[40:], v6_type, ident)
        src = socket.inet_ntop(socket.AF_INET6, pkt[8:24])
    else:
        return None
    return None if payload is None else (src, payload)
