"""Tests for rendering the Yggdrasil and Reticulum regions."""

from pathlib import Path

from bind_samples import DEFAULTS, RNS_SAMPLE, YGG_SAMPLE

import bind_config as rbc


def test_render_ygg_single_uri():
    out = rbc.render_ygg(YGG_SAMPLE, "tcp://203.0.113.10:65533")
    assert '"tcp://203.0.113.10:65533"' in out
    assert '"tcp://[::]:65533"' not in out
    assert '"tcp://127.0.0.1:9000"' in out


def test_render_ygg_multiple_uris():
    out = rbc.render_ygg(
        YGG_SAMPLE, "tcp://203.0.113.10:65533, tcp://[2001:db8::1]:65534"
    )
    assert '"tcp://203.0.113.10:65533"' in out
    assert '"tcp://[2001:db8::1]:65534"' in out


def test_render_ygg_default_is_idempotent():
    assert rbc.render_ygg(YGG_SAMPLE, "tcp://[::]:65533") == YGG_SAMPLE


def test_render_rns_single_bind():
    out = rbc.render_rns(RNS_SAMPLE, "203.0.113.10:4242")
    assert "listen_ip = 203.0.113.10" in out
    assert "listen_ip = ::" not in out
    assert "[[LAN AutoDiscovery]]" in out
    assert "[[Bootstrap — Reserve.Network DE]]" in out


def test_render_rns_multiple_binds_makes_n_blocks():
    out = rbc.render_rns(RNS_SAMPLE, "203.0.113.10:4242, [2001:db8::1]:4343")
    assert out.count("type = TCPServerInterface") == 2
    assert "[[Public TCP listener 1]]" in out
    assert "[[Public TCP listener 2]]" in out
    assert "listen_ip = 203.0.113.10" in out
    assert "listen_ip = 2001:db8::1" in out
    assert "listen_port = 4343" in out
    assert out.count("discoverable = yes") == 1
    assert out.count("discoverable = no") == 1


def test_render_rns_default_is_idempotent():
    assert rbc.render_rns(RNS_SAMPLE, "[::]:4242") == RNS_SAMPLE


def test_seed_ygg_default_roundtrips():
    text = Path(DEFAULTS, "yggdrasil.conf").read_text()
    assert (
        rbc.replace_region(text, "ygg-public-listen", ['    "tcp://[::]:65533"'])
        is not None
    )
    assert rbc.render_ygg(text, "tcp://[::]:65533") == text


def test_seed_rns_default_roundtrips():
    text = Path(DEFAULTS, "reticulum.config").read_text()
    assert rbc.replace_region(text, "rns-public-listen", ["  x"]) is not None
    assert rbc.render_rns(text, "[::]:4242") == text
