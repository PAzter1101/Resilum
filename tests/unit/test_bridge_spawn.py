"""Supervisor process-spawn argv (no processes actually started)."""

import bridge_spawn
from bridge_config import _Covert


def _argv(monkeypatch, spec) -> list:
    captured = {}
    monkeypatch.setattr(
        bridge_spawn.subprocess, "Popen", lambda cmd: captured.setdefault("cmd", cmd)
    )
    bridge_spawn._spawn_covert(spec)
    return captured["cmd"]


def test_spawn_covert_forwards_role_addresses_interface(monkeypatch):
    cmd = _argv(
        monkeypatch,
        _Covert(
            "icmp",
            role="server",
            addresses=["1.2.3.4", "2001:db8::9"],
            interface="eth0",
            identity="/id",
        ),
    )
    assert "covert.discovery" in cmd
    assert cmd[cmd.index("--role") + 1] == "server"
    assert cmd.count("--address") == 2
    assert "1.2.3.4" in cmd and "2001:db8::9" in cmd
    assert cmd[cmd.index("--interface") + 1] == "eth0"


def test_spawn_covert_omits_unset_address_interface(monkeypatch):
    cmd = _argv(monkeypatch, _Covert("icmp", role="client", identity="/id"))
    assert "--role" in cmd
    assert "--address" not in cmd
    assert "--interface" not in cmd
    assert "--mtu" not in cmd  # default MTU is not forwarded


def test_spawn_covert_forwards_non_default_mtu(monkeypatch):
    cmd = _argv(monkeypatch, _Covert("icmp", mtu=1280, identity="/id"))
    assert cmd[cmd.index("--mtu") + 1] == "1280"
