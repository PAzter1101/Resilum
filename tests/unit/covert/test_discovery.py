import sys
from types import SimpleNamespace

import RNS

from covert import discovery
from covert.discovery import client_interface_config, server_interface_config


def test_client_config_embeds_pubkey_hex():
    cfg = client_interface_config("icmp", "203.0.113.9", "deadbeef")
    assert cfg["name"] == "CovertDiscovered[icmp:203.0.113.9]"
    assert cfg["respawn_delay"] == 5
    assert cfg["command"] == (
        f"{sys.executable} -m covert icmp client "
        "--dst 203.0.113.9 --server-identity deadbeef"
    )


def test_server_config_carries_name_command_respawn():
    cfg = server_interface_config("icmp", "/config/covert/server.id")
    assert cfg["name"] == "CovertServer[icmp]"
    assert cfg["command"] == (
        f"{sys.executable} -m covert icmp server --identity /config/covert/server.id"
    )
    assert cfg["respawn_delay"] == 5


def test_register_peer_registers_client_with_pubkey_hex(monkeypatch):
    captured = []
    monkeypatch.setattr(RNS.Transport, "interfaces", [])
    monkeypatch.setattr(discovery, "PipeInterface", lambda owner, cfg: cfg)
    monkeypatch.setattr(discovery, "register_in_transport", captured.append)
    server = RNS.Identity()
    discovery._register_peer("icmp", "1.2.3.4", server)
    assert len(captured) == 1
    assert server.get_public_key().hex() in captured[0]["command"]


def test_register_peer_dedups_existing_interface(monkeypatch):
    existing = SimpleNamespace(name="CovertDiscovered[icmp:1.2.3.4]")
    captured = []
    monkeypatch.setattr(RNS.Transport, "interfaces", [existing])
    monkeypatch.setattr(discovery, "PipeInterface", lambda owner, cfg: cfg)
    monkeypatch.setattr(discovery, "register_in_transport", captured.append)
    discovery._register_peer("icmp", "1.2.3.4", RNS.Identity())
    assert captured == []
