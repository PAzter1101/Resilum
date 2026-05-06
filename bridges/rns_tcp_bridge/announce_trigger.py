"""Wake announce-loops up when a new transport interface attaches.

A bare time.sleep makes peers wait up to ANNOUNCE_INTERVAL_SECONDS
before learning we exist when they join the mesh. By polling
RNS.Transport.interfaces in the background and signalling all
registered Events when a new entry appears, we let the loops
re-announce within a few seconds of the path becoming usable.

The first observation never fires — otherwise every fresh
subprocess would emit an extra announce on startup for interfaces
that were already there.
"""

import threading
import time

import RNS

WATCH_INTERVAL_SECONDS = 5

_events: list[threading.Event] = []
_lock = threading.Lock()
_started = False


def register() -> threading.Event:
    event = threading.Event()
    with _lock:
        _events.append(event)
        _ensure_watcher_locked()
    return event


def _ensure_watcher_locked() -> None:
    global _started
    if _started:
        return
    _started = True
    threading.Thread(
        target=_watch,
        name="announce-trigger-watcher",
        daemon=True,
    ).start()


def _interface_names() -> set:
    try:
        return {
            getattr(iface, "name", repr(iface)) for iface in RNS.Transport.interfaces
        }
    except Exception:
        return set()


def _fire_all() -> None:
    with _lock:
        for event in _events:
            event.set()


def _tick(seen: set, first_observation: bool) -> tuple:
    """One iteration of the watcher: returns (new_seen, new_first_flag).
    Side effect: fires registered events when a new interface name
    appears after the first observation."""
    current = _interface_names()
    if not first_observation:
        new = current - seen
        if new:
            RNS.log(
                f"[announce-trigger] new interfaces {new}, kicking announce loops",
                RNS.LOG_VERBOSE,
            )
            _fire_all()
    return current, False


def _watch() -> None:
    seen: set = set()
    first_observation = True
    while True:
        seen, first_observation = _tick(seen, first_observation)
        time.sleep(WATCH_INTERVAL_SECONDS)
