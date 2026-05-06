"""Verify the announce-trigger watcher fires registered events when
RNS.Transport.interfaces gains a new entry, and stays silent on the
first observation."""

import threading
from types import SimpleNamespace

import pytest

pytest.importorskip("RNS", reason="Reticulum (rns) not installed")

from rns_tcp_bridge import announce_trigger as module


def test_interface_names_extracts_names_from_transport():
    import RNS

    fake = [SimpleNamespace(name="Yggdrasil"), SimpleNamespace(name="Tor")]
    saved = getattr(RNS.Transport, "interfaces", None)
    RNS.Transport.interfaces = fake
    try:
        assert module._interface_names() == {"Yggdrasil", "Tor"}
    finally:
        if saved is None:
            try:
                del RNS.Transport.interfaces
            except AttributeError:
                pass
        else:
            RNS.Transport.interfaces = saved


def test_fire_all_sets_every_registered_event():
    e1, e2 = threading.Event(), threading.Event()
    saved = list(module._events)
    module._events.clear()
    module._events.extend([e1, e2])
    try:
        module._fire_all()
        assert e1.is_set()
        assert e2.is_set()
    finally:
        module._events.clear()
        module._events.extend(saved)


def test_first_tick_does_not_fire(monkeypatch):
    fired = threading.Event()
    monkeypatch.setattr(module, "_fire_all", fired.set)
    monkeypatch.setattr(module, "_interface_names", lambda: {"A", "B"})

    new_seen, new_first = module._tick(set(), True)
    assert new_seen == {"A", "B"}
    assert new_first is False
    assert not fired.is_set()


def test_tick_with_no_new_entries_does_not_fire(monkeypatch):
    fired = threading.Event()
    monkeypatch.setattr(module, "_fire_all", fired.set)
    monkeypatch.setattr(module, "_interface_names", lambda: {"A", "B"})

    new_seen, _ = module._tick({"A", "B"}, False)
    assert new_seen == {"A", "B"}
    assert not fired.is_set()


def test_tick_with_new_entry_fires(monkeypatch):
    fired = threading.Event()
    monkeypatch.setattr(module, "_fire_all", fired.set)
    monkeypatch.setattr(module, "_interface_names", lambda: {"A", "B"})

    new_seen, _ = module._tick({"A"}, False)
    assert new_seen == {"A", "B"}
    assert fired.is_set()


def test_register_returns_event_added_to_registry():
    saved = list(module._events)
    module._events.clear()
    try:
        e = module.register()
        assert e in module._events
        assert isinstance(e, threading.Event)
    finally:
        module._events.clear()
        module._events.extend(saved)
