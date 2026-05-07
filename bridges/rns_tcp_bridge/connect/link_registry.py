"""Live RNS-Link registry, keyed by destination hash.

Populated by the dispatcher every time a Link to a peer becomes
active and a TCP socket is wired through it; emptied either by the
per-Link closed-callback (peer or local pump tore the Link down for
normal reasons) or explicitly by :func:`_teardown_links_for` when an
inbound announce reveals the peer is no longer compatible."""

import threading

import RNS

_active_links_lock = threading.Lock()
_active_links: dict[bytes, list] = {}


def _register_link(dest_hash: bytes, link) -> None:
    with _active_links_lock:
        _active_links.setdefault(dest_hash, []).append(link)

    def on_closed(_link):
        with _active_links_lock:
            bucket = _active_links.get(dest_hash)
            if bucket is None:
                return
            try:
                bucket.remove(link)
            except ValueError:
                return
            if not bucket:
                _active_links.pop(dest_hash, None)

    link.set_link_closed_callback(on_closed)


def _teardown_links_for(dest_hash: bytes, reason: str) -> None:
    """Tear down every active Link to ``dest_hash``. Pump threads on
    those Links will see the close and shut their TCP halves."""
    with _active_links_lock:
        snapshot = list(_active_links.get(dest_hash, []))
    if not snapshot:
        return
    RNS.log(
        f"[bridge:connect] tearing down {len(snapshot)} active Link(s) "
        f"to {RNS.prettyhexrep(dest_hash)}: {reason}",
        RNS.LOG_WARNING,
    )
    for link in snapshot:
        try:
            link.teardown()
        except Exception as exc:
            RNS.log(f"[bridge:connect] teardown failed: {exc}", RNS.LOG_DEBUG)
