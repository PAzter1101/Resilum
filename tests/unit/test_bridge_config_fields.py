"""Field extraction from bridge and covert config entries."""

import pytest

from bridge_config import _parse_bridges, _parse_covert


def test_connect_entry_carries_policy_fields():
    doc = {
        "bridges": [
            {
                "mode": "connect",
                "services": ["socks-egress", "tor"],
                "identity": "/id",
                "tcp": "127.0.0.1:10808",
                "use_own": "false",
                "allow_countries": ["NL"],
                "deny_countries": ["CN"],
                "probe_targets": ["1.1.1.1:443", "9.9.9.9:443"],
            }
        ]
    }
    b = _parse_bridges(doc)[0]
    assert b.use_own == "false"
    assert b.allow_countries == ["NL"]
    assert b.deny_countries == ["CN"]
    assert b.probe_targets == ["1.1.1.1:443", "9.9.9.9:443"]


def test_listen_entry_carries_exit_country():
    doc = {
        "bridges": [
            {
                "mode": "listen",
                "service": "socks-egress",
                "identity": "/id",
                "tcp": "127.0.0.1:1080",
                "exit_country": "DE",
            }
        ]
    }
    b = _parse_bridges(doc)[0]
    assert b.exit_country == "DE"


def test_covert_entry_carries_fields():
    doc = {
        "covert": [
            {
                "carrier": "icmp",
                "role": "server",
                "interface": "eth0",
                "addresses": ["203.0.113.9", "2001:db8::9"],
                "mtu": 1280,
                "bitrate": 9600,
                "identity": "/id",
            }
        ]
    }
    c = _parse_covert(doc)[0]
    assert c.carrier == "icmp"
    assert c.role == "server"
    assert c.interface == "eth0"
    assert c.addresses == ["203.0.113.9", "2001:db8::9"]
    assert c.mtu == 1280
    assert c.bitrate == 9600
    assert c.identity == "/id"


def test_covert_addresses_from_comma_string():
    doc = {"covert": [{"carrier": "icmp", "addresses": "192.0.2.4, 198.51.100.8"}]}
    assert _parse_covert(doc)[0].addresses == ["192.0.2.4", "198.51.100.8"]


def test_covert_null_fields_become_empty():
    doc = {
        "covert": [{"carrier": "icmp", "role": None, "addresses": None, "mtu": None}]
    }
    c = _parse_covert(doc)[0]
    assert c.role == "both"
    assert c.addresses == []
    assert c.interface == ""
    assert c.mtu == 1400
    assert c.bitrate == 32000


def test_covert_missing_carrier_aborts():
    with pytest.raises(SystemExit, match="missing carrier"):
        _parse_covert({"covert": [{"role": "client"}]})
