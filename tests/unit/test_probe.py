"""Tests for probe-target parsing. No RNS Reticulum() instance is created."""

import pytest

pytest.importorskip("RNS", reason="Reticulum (rns) not installed")

from rns_tcp_bridge.connect.probe import (
    DEFAULT_PROBE_TARGETS,
    PROBE_TARGETS_ENV,
    parse_targets,
    resolve_targets,
)


def test_unset_falls_back_to_defaults():
    assert parse_targets(None) == DEFAULT_PROBE_TARGETS
    assert parse_targets("   ") == DEFAULT_PROBE_TARGETS


def test_parses_valid_list():
    assert parse_targets("1.1.1.1:443, 9.9.9.9:53") == [
        ("1.1.1.1", 443),
        ("9.9.9.9", 53),
    ]


def test_skips_malformed_but_keeps_valid():
    # nonsense-host, out-of-range port, and missing port are dropped
    assert parse_targets("not-an-ip:443,8.8.8.8:70000,1.1.1.1,9.9.9.9:80") == [
        ("9.9.9.9", 80)
    ]


def test_all_invalid_falls_back_to_defaults():
    assert parse_targets("bad,also:bad,:443") == DEFAULT_PROBE_TARGETS


def test_resolve_prefers_cli_over_env(monkeypatch):
    monkeypatch.setenv(PROBE_TARGETS_ENV, "8.8.8.8:443")
    assert resolve_targets(["1.1.1.1:443"]) == [("1.1.1.1", 443)]


def test_resolve_falls_back_to_env_when_no_cli(monkeypatch):
    monkeypatch.setenv(PROBE_TARGETS_ENV, "8.8.8.8:53")
    assert resolve_targets(None) == [("8.8.8.8", 53)]
    assert resolve_targets([]) == [("8.8.8.8", 53)]


def test_resolve_falls_back_to_defaults_when_neither(monkeypatch):
    monkeypatch.delenv(PROBE_TARGETS_ENV, raising=False)
    assert resolve_targets(None) == DEFAULT_PROBE_TARGETS


def test_resolve_ignores_all_invalid_cli_then_uses_env(monkeypatch):
    monkeypatch.setenv(PROBE_TARGETS_ENV, "9.9.9.9:443")
    assert resolve_targets(["garbage", "also:bad"]) == [("9.9.9.9", 443)]
