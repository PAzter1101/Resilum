from scapy.layers.inet import ICMP, IP

from covert.carriers import load
from covert.carriers.icmp import IcmpCarrier


def test_loader_returns_icmp():
    assert isinstance(load("icmp"), IcmpCarrier)


def test_request_round_trip():
    c = IcmpCarrier(dst="203.0.113.9")
    pkt = c.build_request(None, b"payload-bytes")
    incoming = IP(src="198.51.100.7", dst="203.0.113.9") / pkt[ICMP]
    reply_to, wire = c.parse_request(bytes(incoming))
    assert reply_to == "198.51.100.7"
    assert wire == b"payload-bytes"


def test_response_round_trip():
    c = IcmpCarrier(dst="203.0.113.9")
    pkt = c.build_response("198.51.100.7", b"down")
    incoming = IP(src="203.0.113.9", dst="198.51.100.7") / pkt[ICMP]
    assert c.parse_response(bytes(incoming)) == b"down"


def test_parse_rejects_non_echo():
    c = IcmpCarrier(dst="203.0.113.9")
    junk = IP(src="1.2.3.4", dst="203.0.113.9") / ICMP(type=3)
    assert c.parse_request(bytes(junk)) is None


def test_capacity_positive():
    assert IcmpCarrier(dst="203.0.113.9").capacity > 1000
