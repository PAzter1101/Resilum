"""Verify the connect-bridge fallback chain dispatches services in
priority order and stops on the first service that yields a working
Link. No RNS Reticulum() instance is created — every external call
is patched."""

import threading
from unittest import mock

import pytest

pytest.importorskip("RNS", reason="Reticulum (rns) not installed")

from rns_tcp_bridge import announce_payload
from rns_tcp_bridge.connect import announce as connect_announce
from rns_tcp_bridge.connect import dispatch, link_registry


def _fake_socket():
    s = mock.MagicMock()
    s.close = mock.MagicMock()
    return s


def test_handle_outbound_tries_first_service_and_wires_on_success():
    sock = _fake_socket()
    targets = {"socks-egress": b"\xaa" * 16, "tor": b"\xbb" * 16}
    lock = threading.Lock()
    calls = []

    def fake_try(s, service, target_hash, aspects):
        calls.append((service, target_hash))
        return True

    with mock.patch.object(dispatch, "_try_one_service", fake_try):
        dispatch._handle_outbound(sock, ["socks-egress", "tor"], targets, lock)

    assert calls == [("socks-egress", b"\xaa" * 16)]
    sock.close.assert_not_called()


def test_handle_outbound_falls_through_to_next_service_on_link_failure():
    sock = _fake_socket()
    targets = {"socks-egress": b"\xaa" * 16, "tor": b"\xbb" * 16}
    lock = threading.Lock()
    calls = []

    def fake_try(s, service, target_hash, aspects):
        calls.append(service)
        return service == "tor"

    with mock.patch.object(dispatch, "_try_one_service", fake_try):
        dispatch._handle_outbound(sock, ["socks-egress", "tor"], targets, lock)

    assert calls == ["socks-egress", "tor"]
    sock.close.assert_not_called()


def test_handle_outbound_closes_socket_when_all_services_fail():
    sock = _fake_socket()
    targets = {"socks-egress": b"\xaa" * 16, "tor": b"\xbb" * 16}
    lock = threading.Lock()

    with mock.patch.object(dispatch, "_try_one_service", lambda *a, **k: False):
        dispatch._handle_outbound(sock, ["socks-egress", "tor"], targets, lock)

    sock.close.assert_called_once()


def test_handle_outbound_skips_services_with_no_target_yet():
    sock = _fake_socket()
    targets = {"tor": b"\xbb" * 16}  # socks-egress not yet announced
    lock = threading.Lock()
    calls = []

    def fake_try(s, service, target_hash, aspects):
        calls.append(service)
        return True

    with mock.patch.object(dispatch, "_try_one_service", fake_try):
        dispatch._handle_outbound(sock, ["socks-egress", "tor"], targets, lock)

    assert calls == ["tor"]
    sock.close.assert_not_called()


def test_announce_handler_records_target_in_shared_dict():
    targets = {}
    lock = threading.Lock()
    handler = connect_announce._make_announce_handler(
        service="tor",
        aspects=["resilum", "bridge", "tcp", "tor"],
        skip_hashes=set(),
        targets=targets,
        lock=lock,
    )
    handler.received_announce(
        destination_hash=b"\xcc" * 16,
        announced_identity=None,
        app_data=announce_payload.pack(),
    )
    assert targets == {"tor": b"\xcc" * 16}


def test_announce_handler_ignores_self_hashes():
    self_hash = b"\xdd" * 16
    targets = {}
    lock = threading.Lock()
    handler = connect_announce._make_announce_handler(
        service="tor",
        aspects=["resilum", "bridge", "tcp", "tor"],
        skip_hashes={self_hash},
        targets=targets,
        lock=lock,
    )
    handler.received_announce(
        destination_hash=self_hash,
        announced_identity=None,
        app_data=announce_payload.pack(),
    )
    assert targets == {}


def test_announce_handler_drops_incompatible_peer():
    targets = {}
    lock = threading.Lock()
    handler = connect_announce._make_announce_handler(
        service="tor",
        aspects=["resilum", "bridge", "tcp", "tor"],
        skip_hashes=set(),
        targets=targets,
        lock=lock,
    )
    handler.received_announce(
        destination_hash=b"\xcc" * 16,
        announced_identity=None,
        app_data=b'{"v": "999.0.0"}',
    )
    assert targets == {}


def test_announce_handler_drops_malformed_payload():
    targets = {}
    lock = threading.Lock()
    handler = connect_announce._make_announce_handler(
        service="tor",
        aspects=["resilum", "bridge", "tcp", "tor"],
        skip_hashes=set(),
        targets=targets,
        lock=lock,
    )
    handler.received_announce(
        destination_hash=b"\xcc" * 16,
        announced_identity=None,
        app_data=None,
    )
    assert targets == {}


def test_wait_for_any_target_returns_true_once_any_service_has_a_target():
    targets = {}
    lock = threading.Lock()

    def populate_after_delay():
        import time

        time.sleep(0.05)
        with lock:
            targets["tor"] = b"\xee" * 16

    threading.Thread(target=populate_after_delay, daemon=True).start()
    assert dispatch._wait_for_any_target(targets, lock, ["socks-egress", "tor"], 1.0)


def test_wait_for_any_target_returns_false_on_timeout():
    targets = {}
    lock = threading.Lock()
    assert not dispatch._wait_for_any_target(
        targets, lock, ["socks-egress", "tor"], 0.05
    )


def _fake_link():
    """A Link stand-in that records teardown() and remembers the
    closed-callback the bridge registers on it."""
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
    # Registry is cleared by the closed-callback path; simulate both.
    link_a._closed_cb(link_a)
    link_b._closed_cb(link_b)
    assert dest not in link_registry._active_links


def test_announce_handler_tears_down_active_links_on_incompatible():
    dest = b"\xfc" * 16
    link = _fake_link()
    link_registry._register_link(dest, link)

    targets = {"tor": dest}
    lock = threading.Lock()
    handler = connect_announce._make_announce_handler(
        service="tor",
        aspects=["resilum", "bridge", "tcp", "tor"],
        skip_hashes=set(),
        targets=targets,
        lock=lock,
    )
    handler.received_announce(
        destination_hash=dest,
        announced_identity=None,
        app_data=b'{"v": "999.0.0"}',
    )

    link.teardown.assert_called_once()
    assert "tor" not in targets
    # Cleanup so the registry doesn't leak into other tests.
    link._closed_cb(link)


def test_announce_handler_does_not_teardown_compatible_peer():
    dest = b"\xfd" * 16
    link = _fake_link()
    link_registry._register_link(dest, link)

    targets = {}
    lock = threading.Lock()
    handler = connect_announce._make_announce_handler(
        service="tor",
        aspects=["resilum", "bridge", "tcp", "tor"],
        skip_hashes=set(),
        targets=targets,
        lock=lock,
    )
    handler.received_announce(
        destination_hash=dest,
        announced_identity=None,
        app_data=announce_payload.pack(),
    )

    link.teardown.assert_not_called()
    assert targets == {"tor": dest}
    link._closed_cb(link)
