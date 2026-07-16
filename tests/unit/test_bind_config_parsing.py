"""Tests for listen-value parsing and validation."""

import pytest

import bind_config as rbc


def test_split_host_port_handles_ipv6_brackets():
    assert rbc.split_host_port("[2001:db8::1]:4242") == ("2001:db8::1", "4242")
    assert rbc.split_host_port("203.0.113.10:65533") == ("203.0.113.10", "65533")


def test_split_host_port_rejects_missing_port():
    with pytest.raises(ValueError):
        rbc.split_host_port("203.0.113.10")


def test_parse_ygg_requires_scheme():
    with pytest.raises(ValueError):
        rbc.parse_ygg_listen("203.0.113.10:65533")


def test_parse_ygg_rejects_bad_port():
    with pytest.raises(ValueError):
        rbc.parse_ygg_listen("tcp://203.0.113.10:99999")


def test_parse_rns_rejects_bad_entry():
    with pytest.raises(ValueError):
        rbc.parse_rns_listen("203.0.113.10")
