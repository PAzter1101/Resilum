"""Config validation: malformed entries abort with a clear message."""

import pytest

from bridge_config import _parse_bridges, _parse_covert, _parse_vpn

_BRIDGE = {
    "mode": "connect",
    "service": "tor",
    "identity": "/id",
    "tcp": "127.0.0.1:9050",
}


def test_bridge_requires_host_port():
    doc = {"bridges": [{**_BRIDGE, "tcp": "127.0.0.1"}]}
    with pytest.raises(SystemExit, match="host:port"):
        _parse_bridges(doc)


def test_bridge_rejects_unknown_use_own():
    doc = {"bridges": [{**_BRIDGE, "use_own": "maybe"}]}
    with pytest.raises(SystemExit, match="use_own"):
        _parse_bridges(doc)


def test_bridge_requires_identity():
    doc = {"bridges": [{"mode": "connect", "service": "tor", "tcp": "127.0.0.1:9050"}]}
    with pytest.raises(SystemExit, match="identity"):
        _parse_bridges(doc)


def test_covert_rejects_unknown_role():
    doc = {"covert": [{"carrier": "icmp", "role": "gateway"}]}
    with pytest.raises(SystemExit, match="role"):
        _parse_covert(doc)


def test_covert_rejects_bad_address():
    doc = {"covert": [{"carrier": "icmp", "addresses": ["not-an-ip"]}]}
    with pytest.raises(SystemExit, match="valid IP"):
        _parse_covert(doc)


def test_covert_accepts_v4_and_v6_addresses():
    doc = {"covert": [{"carrier": "icmp", "addresses": ["1.2.3.4", "2001:db8::9"]}]}
    assert _parse_covert(doc)[0].addresses == ["1.2.3.4", "2001:db8::9"]


def test_covert_rejects_out_of_range_mtu():
    doc = {"covert": [{"carrier": "icmp", "mtu": 10}]}
    with pytest.raises(SystemExit, match="greater than"):
        _parse_covert(doc)


def test_covert_rejects_non_integer_mtu():
    doc = {"covert": [{"carrier": "icmp", "mtu": "wide"}]}
    with pytest.raises(SystemExit, match="valid integer"):
        _parse_covert(doc)


def test_vpn_rejects_bad_subnet():
    doc = {"vpn": [{"mode": "server", "identity": "/id", "subnet": "10.0.0.0/99"}]}
    with pytest.raises(SystemExit, match="CIDR"):
        _parse_vpn(doc)
