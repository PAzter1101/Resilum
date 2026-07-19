import socket
import struct

from covert.carriers import load
from covert.carriers._icmp_wire import ETH_P_IP, ETH_P_IPV6, _checksum
from covert.carriers.icmp import IcmpCarrier

_ID = 0x1234


def _v4(src, dst, icmp):
    header = struct.pack(
        "!BBHHHBBH4s4s",
        0x45,
        0,
        20 + len(icmp),
        0,
        0,
        64,
        1,
        0,
        socket.inet_aton(src),
        socket.inet_aton(dst),
    )
    return (ETH_P_IP, header + icmp)


def _v6(src, dst, icmp):
    header = struct.pack(
        "!IHBB16s16s",
        0x60000000,
        len(icmp),
        58,
        64,
        socket.inet_pton(socket.AF_INET6, src),
        socket.inet_pton(socket.AF_INET6, dst),
    )
    return (ETH_P_IPV6, header + icmp)


def test_loader_returns_icmp():
    assert isinstance(load("icmp"), IcmpCarrier)


def test_request_round_trip_v4():
    c = IcmpCarrier(dst="203.0.113.9", ident=_ID)
    dst, icmp = c.build_request(None, b"payload-bytes")
    assert dst == "203.0.113.9"
    reply_to, wire = c.parse_request(_v4("198.51.100.7", "203.0.113.9", icmp))
    assert reply_to == "198.51.100.7"
    assert wire == b"payload-bytes"


def test_response_round_trip_v4():
    c = IcmpCarrier(dst="203.0.113.9", ident=_ID)
    _dst, icmp = c.build_response("198.51.100.7", b"down")
    assert c.parse_response(_v4("203.0.113.9", "198.51.100.7", icmp)) == b"down"


def test_request_round_trip_v6():
    c = IcmpCarrier(dst="2001:db8::7", ident=_ID)
    dst, icmp = c.build_request(None, b"v6-payload")
    assert dst == "2001:db8::7"
    reply_to, wire = c.parse_request(_v6("2001:db8::9", "2001:db8::7", icmp))
    assert reply_to == "2001:db8::9"
    assert wire == b"v6-payload"


def test_response_round_trip_v6():
    c = IcmpCarrier(dst="2001:db8::9", ident=_ID)
    _dst, icmp = c.build_response("2001:db8::7", b"v6-down")
    assert c.parse_response(_v6("2001:db8::7", "2001:db8::9", icmp)) == b"v6-down"


def test_v4_checksum_is_valid():
    # The ones-complement checksum over a message that carries its own correct
    # checksum is zero.
    _dst, icmp = IcmpCarrier(dst="203.0.113.9", ident=_ID).build_request(None, b"abc")
    assert _checksum(icmp) == 0


def test_parse_rejects_non_icmp():
    c = IcmpCarrier(dst="203.0.113.9", ident=_ID)
    pkt = _v4("1.2.3.4", "203.0.113.9", b"\x08" + b"\x00" * 7)
    pkt = (ETH_P_IP, pkt[1][:9] + b"\x06" + pkt[1][10:])  # protocol 6 (TCP)
    assert c.parse_request(pkt) is None


def test_parse_rejects_non_echo():
    c = IcmpCarrier(dst="203.0.113.9", ident=_ID)
    icmp = struct.pack("!BBHHH", 3, 0, 0, _ID, 0)  # type 3, dest unreachable
    assert c.parse_request(_v4("1.2.3.4", "203.0.113.9", icmp)) is None


def test_parse_rejects_foreign_echo_id():
    _dst, icmp = IcmpCarrier(dst="203.0.113.9", ident=_ID ^ 1).build_request(None, b"x")
    c = IcmpCarrier(dst="203.0.113.9", ident=_ID)
    assert c.parse_request(_v4("1.2.3.4", "203.0.113.9", icmp)) is None


def test_capacity_positive():
    assert IcmpCarrier(dst="203.0.113.9").capacity > 1000


def test_capacity_per_family():
    c = IcmpCarrier(mtu=1400)
    assert c.capacity_for("203.0.113.9") == 1400 - (20 + 8)
    assert c.capacity_for("2001:db8::9") == 1400 - (40 + 8)


def test_client_capacity_follows_dst_family():
    assert IcmpCarrier(dst="203.0.113.9").capacity == 1400 - (20 + 8)
    assert IcmpCarrier(dst="2001:db8::9").capacity == 1400 - (40 + 8)


def test_unknown_dst_is_conservative():
    assert IcmpCarrier(dst="").capacity == 1400 - (40 + 8)


def test_mtu_override():
    assert IcmpCarrier(dst="203.0.113.9", mtu=576).capacity == 576 - (20 + 8)
