"""Verify the announce envelope encoder/decoder: round-trip preserves
endpoint bytes, malformed inputs return None, and the version field
is checked against the local node's compatibility window."""

import pytest

pytest.importorskip("RNS", reason="Reticulum (rns) not installed")

from rns_tcp_bridge import announce_payload as module


def test_pack_then_parse_round_trip_with_endpoint():
    packed = module.pack(b"abc.onion:4242")
    parsed = module.parse(packed)
    assert parsed is not None
    assert parsed.version == module.VERSION
    assert parsed.endpoint == b"abc.onion:4242"


def test_pack_then_parse_round_trip_without_endpoint():
    packed = module.pack()
    parsed = module.parse(packed)
    assert parsed is not None
    assert parsed.version == module.VERSION
    assert parsed.endpoint is None


def test_parse_empty_bytes_returns_none():
    assert module.parse(b"") is None


def test_parse_none_returns_none():
    assert module.parse(None) is None


def test_parse_malformed_json_returns_none():
    assert module.parse(b"not json at all") is None


def test_parse_non_object_json_returns_none():
    assert module.parse(b"[1, 2, 3]") is None


def test_parse_missing_version_returns_none():
    assert module.parse(b'{"ep": "abc.onion:4242"}') is None


def test_parse_non_string_version_returns_none():
    assert module.parse(b'{"v": 1}') is None


def test_parse_incompatible_version_returns_none(monkeypatch):
    monkeypatch.setattr(module, "VERSION", "1.0.0")
    monkeypatch.setattr(
        module, "is_compatible", lambda other, ours=module.VERSION: False
    )
    assert module.parse(b'{"v": "2.0.0"}') is None


def test_parse_compatible_different_minor_accepted(monkeypatch):
    # Local 0.5.2 hears a peer on 0.6.0 — same major (0), so accept.
    monkeypatch.setattr(module, "VERSION", "0.5.2")
    monkeypatch.setattr(module, "is_compatible", lambda other, ours="0.5.2": True)
    parsed = module.parse(b'{"v": "0.6.0", "ep": "abc.onion:4242"}')
    assert parsed is not None
    assert parsed.version == "0.6.0"
    assert parsed.endpoint == b"abc.onion:4242"
