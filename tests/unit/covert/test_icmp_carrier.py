from scapy.layers.inet import ICMP, IP
from scapy.layers.inet6 import IPv6

from covert.carriers import load
from covert.carriers.icmp import IcmpCarrier

_ID = 0x1234


def test_loader_returns_icmp():
    assert isinstance(load("icmp"), IcmpCarrier)


def test_request_round_trip_v4():
    c = IcmpCarrier(dst="203.0.113.9", ident=_ID)
    pkt = c.build_request(None, b"payload-bytes")
    incoming = IP(src="198.51.100.7", dst="203.0.113.9") / pkt[ICMP]
    reply_to, wire = c.parse_request(bytes(incoming))
    assert reply_to == "198.51.100.7"
    assert wire == b"payload-bytes"


def test_response_round_trip_v4():
    c = IcmpCarrier(dst="203.0.113.9", ident=_ID)
    pkt = c.build_response("198.51.100.7", b"down")
    incoming = IP(src="203.0.113.9", dst="198.51.100.7") / pkt[ICMP]
    assert c.parse_response(bytes(incoming)) == b"down"


def test_request_round_trip_v6():
    c = IcmpCarrier(dst="2001:db8::7", ident=_ID)
    pkt = c.build_request(None, b"v6-payload")
    incoming = IPv6(src="2001:db8::9", dst="2001:db8::7") / pkt[IPv6].payload
    reply_to, wire = c.parse_request(bytes(incoming))
    assert reply_to == "2001:db8::9"
    assert wire == b"v6-payload"


def test_response_round_trip_v6():
    c = IcmpCarrier(dst="2001:db8::9", ident=_ID)
    pkt = c.build_response("2001:db8::7", b"v6-down")
    assert c.parse_response(bytes(pkt)) == b"v6-down"


def test_parse_rejects_non_echo():
    c = IcmpCarrier(dst="203.0.113.9", ident=_ID)
    junk = IP(src="1.2.3.4", dst="203.0.113.9") / ICMP(type=3)
    assert c.parse_request(bytes(junk)) is None


def test_parse_rejects_foreign_echo_id():
    c = IcmpCarrier(dst="203.0.113.9", ident=_ID)
    ping = IP(src="1.2.3.4", dst="203.0.113.9") / ICMP(type=8, id=_ID ^ 1)
    assert c.parse_request(bytes(ping)) is None


def test_capacity_positive():
    assert IcmpCarrier(dst="203.0.113.9").capacity > 1000


def test_capacity_is_larger_for_v4_than_v6():
    c = IcmpCarrier(mtu=1400)
    assert c.capacity_for("203.0.113.9") == 1400 - (20 + 8)
    assert c.capacity_for("2001:db8::9") == 1400 - (40 + 8)


def test_client_capacity_follows_dst_family():
    assert IcmpCarrier(dst="203.0.113.9").capacity == 1400 - (20 + 8)
    assert IcmpCarrier(dst="2001:db8::9").capacity == 1400 - (40 + 8)


def test_unknown_dst_is_conservative():
    assert IcmpCarrier(dst="").capacity == 1400 - (40 + 8)


def test_mtu_override_changes_capacity():
    assert IcmpCarrier(dst="203.0.113.9", mtu=576).capacity == 576 - (20 + 8)
