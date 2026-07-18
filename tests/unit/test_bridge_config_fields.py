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
                "address": "203.0.113.9",
                "identity": "/id",
            }
        ]
    }
    c = _parse_covert(doc)[0]
    assert c.carrier == "icmp"
    assert c.role == "server"
    assert c.address == "203.0.113.9"
    assert c.identity == "/id"


def test_covert_missing_carrier_aborts():
    with pytest.raises(SystemExit, match="missing carrier"):
        _parse_covert({"covert": [{"role": "client"}]})
