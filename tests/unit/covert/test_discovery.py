from types import SimpleNamespace

import RNS

from covert import discovery, interfaces
from covert.discovery import _announce_addresses


def test_register_peer_uses_first_announced_address(monkeypatch):
    captured = []
    monkeypatch.setattr(RNS.Transport, "interfaces", [])
    monkeypatch.setattr(
        interfaces, "PipeInterface", lambda owner, cfg: SimpleNamespace(**cfg)
    )
    monkeypatch.setattr(interfaces, "register_in_transport", captured.append)
    discovery._register_peer("icmp", "192.0.2.4,2001:db8::9", RNS.Identity())
    assert captured[0].name == "CovertDiscovered[icmp:192.0.2.4]"


def test_register_peer_dedups_existing_interface(monkeypatch):
    existing = SimpleNamespace(name="CovertDiscovered[icmp:192.0.2.4]")
    captured = []
    monkeypatch.setattr(RNS.Transport, "interfaces", [existing])
    monkeypatch.setattr(interfaces, "PipeInterface", lambda owner, cfg: cfg)
    monkeypatch.setattr(interfaces, "register_in_transport", captured.append)
    discovery._register_peer("icmp", "192.0.2.4", RNS.Identity())
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
