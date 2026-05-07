"""Verify the connect-bridge fallback chain dispatches services in
priority order and stops on the first service that yields a working
Link. No RNS Reticulum() instance is created — every external call
is patched."""

import threading
from unittest import mock

import pytest

pytest.importorskip("RNS", reason="Reticulum (rns) not installed")

from rns_tcp_bridge import connect as module


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

    with mock.patch.object(module, "_try_one_service", fake_try):
        module._handle_outbound(sock, ["socks-egress", "tor"], targets, lock)

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

    with mock.patch.object(module, "_try_one_service", fake_try):
        module._handle_outbound(sock, ["socks-egress", "tor"], targets, lock)

    assert calls == ["socks-egress", "tor"]
    sock.close.assert_not_called()


def test_handle_outbound_closes_socket_when_all_services_fail():
    sock = _fake_socket()
    targets = {"socks-egress": b"\xaa" * 16, "tor": b"\xbb" * 16}
    lock = threading.Lock()

    with mock.patch.object(module, "_try_one_service", lambda *a, **k: False):
        module._handle_outbound(sock, ["socks-egress", "tor"], targets, lock)

    sock.close.assert_called_once()


def test_handle_outbound_skips_services_with_no_target_yet():
    sock = _fake_socket()
    targets = {"tor": b"\xbb" * 16}  # socks-egress not yet announced
    lock = threading.Lock()
    calls = []

    def fake_try(s, service, target_hash, aspects):
        calls.append(service)
        return True

    with mock.patch.object(module, "_try_one_service", fake_try):
        module._handle_outbound(sock, ["socks-egress", "tor"], targets, lock)

    assert calls == ["tor"]
    sock.close.assert_not_called()


def test_announce_handler_records_target_in_shared_dict():
    targets = {}
    lock = threading.Lock()
    handler = module._make_announce_handler(
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
    assert targets == {"tor": b"\xcc" * 16}


def test_announce_handler_ignores_self_hashes():
    self_hash = b"\xdd" * 16
    targets = {}
    lock = threading.Lock()
    handler = module._make_announce_handler(
        service="tor",
        aspects=["resilum", "bridge", "tcp", "tor"],
        skip_hashes={self_hash},
        targets=targets,
        lock=lock,
    )
    handler.received_announce(
        destination_hash=self_hash,
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
    assert module._wait_for_any_target(targets, lock, ["socks-egress", "tor"], 1.0)


def test_wait_for_any_target_returns_false_on_timeout():
    targets = {}
    lock = threading.Lock()
    assert not module._wait_for_any_target(targets, lock, ["socks-egress", "tor"], 0.05)
