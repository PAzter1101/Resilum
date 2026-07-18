"""Supervisor process-spawn argv (no processes actually started)."""

import bridge_spawn
from bridge_config import _Covert


def test_spawn_covert_server_includes_address(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        bridge_spawn.subprocess, "Popen", lambda cmd: captured.setdefault("cmd", cmd)
    )
    bridge_spawn._spawn_covert(
        _Covert("icmp", role="both", address="1.2.3.4", identity="/id")
    )
    assert "covert.discovery" in captured["cmd"]
    assert "--address" in captured["cmd"] and "1.2.3.4" in captured["cmd"]


def test_spawn_covert_client_omits_address(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        bridge_spawn.subprocess, "Popen", lambda cmd: captured.setdefault("cmd", cmd)
    )
    bridge_spawn._spawn_covert(
        _Covert("icmp", role="client", address="1.2.3.4", identity="/id")
    )
    assert "--address" not in captured["cmd"]
