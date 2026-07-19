import sys
from types import SimpleNamespace

import RNS

from covert import discovery
from covert.discovery import (
    _announce_addresses,
    client_interface_config,
    server_interface_config,
)


def test_client_config_embeds_pubkey_hex():
    cfg = client_interface_config("icmp", "203.0.113.9", "deadbeef")
    assert cfg["name"] == "CovertDiscovered[icmp:203.0.113.9]"
    assert cfg["respawn_delay"] == 5
    assert cfg["command"] == (
        f"{sys.executable} -m covert icmp client "
        "--dst 203.0.113.9 --server-identity deadbeef"
    )


def test_client_config_appends_interface():
    cfg = client_interface_config("icmp", "203.0.113.9", "deadbeef", "eth1")
    assert cfg["command"].endswith("--interface eth1")


def test_client_config_appends_non_default_mtu():
    cfg = client_interface_config("icmp", "203.0.113.9", "deadbeef", "eth1", 1280)
    assert cfg["command"].endswith("--interface eth1 --mtu 1280")


def test_config_omits_default_mtu():
    cfg = client_interface_config("icmp", "203.0.113.9", "deadbeef")
    assert "--mtu" not in cfg["command"]


def test_server_config_appends_interface():
    cfg = server_interface_config("icmp", "/config/covert/server.id", "eth0")
    assert cfg["command"] == (
        f"{sys.executable} -m covert icmp server "
        "--identity /config/covert/server.id --interface eth0"
    )
    assert cfg["name"] == "CovertServer[icmp]"


def test_register_peer_uses_first_announced_address(monkeypatch):
    captured = []
    monkeypatch.setattr(RNS.Transport, "interfaces", [])
    monkeypatch.setattr(discovery, "PipeInterface", lambda owner, cfg: cfg)
    monkeypatch.setattr(discovery, "register_in_transport", captured.append)
    discovery._register_peer("icmp", "1.2.3.4,2001:db8::9", RNS.Identity())
    assert captured[0]["name"] == "CovertDiscovered[icmp:1.2.3.4]"


def test_register_peer_dedups_existing_interface(monkeypatch):
    existing = SimpleNamespace(name="CovertDiscovered[icmp:1.2.3.4]")
    captured = []
    monkeypatch.setattr(RNS.Transport, "interfaces", [existing])
    monkeypatch.setattr(discovery, "PipeInterface", lambda owner, cfg: cfg)
    monkeypatch.setattr(discovery, "register_in_transport", captured.append)
    discovery._register_peer("icmp", "1.2.3.4", RNS.Identity())
    assert captured == []


def test_announce_addresses_prefers_explicit():
    assert _announce_addresses(True, ["203.0.113.9"], "") == ["203.0.113.9"]


def test_announce_addresses_empty_for_client_role():
    assert _announce_addresses(False, ["203.0.113.9"], "") == []


def test_announce_addresses_autodetects_public(monkeypatch):
    monkeypatch.setattr(discovery, "detect_address", lambda iface: "198.51.100.7")
    assert _announce_addresses(True, [], "") == ["198.51.100.7"]


def test_announce_addresses_empty_when_autodetect_private(monkeypatch):
    monkeypatch.setattr(discovery, "detect_address", lambda iface: "")
    assert _announce_addresses(True, [], "") == []
