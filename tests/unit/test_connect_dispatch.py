"""Tests for the connect-bridge dispatch helpers and link registry.
No RNS Reticulum() instance is created — external calls are patched."""

from unittest import mock

import pytest

pytest.importorskip("RNS", reason="Reticulum (rns) not installed")

from rns_tcp_bridge.connect import dispatch, link_registry
from rns_tcp_bridge.connect.candidates import Candidate
from rns_tcp_bridge.constants import DEFAULT_ASPECTS


def _fake_socket():
    s = mock.MagicMock()
    s.close = mock.MagicMock()
    return s


def _fake_link():
    link = mock.MagicMock()
    link.teardown = mock.MagicMock()
    link._closed_cb = None

    def remember_cb(cb):
        link._closed_cb = cb

    link.set_link_closed_callback = mock.MagicMock(side_effect=remember_cb)
    return link


def test_register_link_drops_entry_when_closed_callback_fires():
    dest = b"\xfa" * 16
    link = _fake_link()
    link_registry._register_link(dest, link)
    assert dest in link_registry._active_links
    link._closed_cb(link)
    assert dest not in link_registry._active_links


def test_teardown_links_for_calls_teardown_and_clears_registry():
    dest = b"\xfb" * 16
    link_a, link_b = _fake_link(), _fake_link()
    link_registry._register_link(dest, link_a)
    link_registry._register_link(dest, link_b)

    link_registry._teardown_links_for(dest, reason="test")

    link_a.teardown.assert_called_once()
    link_b.teardown.assert_called_once()
    link_a._closed_cb(link_a)
    link_b._closed_cb(link_b)
    assert dest not in link_registry._active_links


def test_dispatch_to_calls_try_one_service_with_correct_args():
    sock = _fake_socket()
    cand = Candidate(dest_hash=b"\xaa" * 16, service="tor")
    calls = []

    def fake_try(s, service, target_hash, aspects):
        calls.append((service, target_hash, aspects))
        return True

    with mock.patch.object(dispatch, "_try_one_service", fake_try):
        result = dispatch.dispatch_to(sock, cand)

    assert result is True
    assert calls == [("tor", b"\xaa" * 16, DEFAULT_ASPECTS + ["tor"])]


def test_dispatch_to_returns_false_when_link_fails():
    sock = _fake_socket()
    cand = Candidate(dest_hash=b"\xbb" * 16, service="socks-egress")

    with mock.patch.object(dispatch, "_try_one_service", lambda *a: False):
        result = dispatch.dispatch_to(sock, cand)

    assert result is False
