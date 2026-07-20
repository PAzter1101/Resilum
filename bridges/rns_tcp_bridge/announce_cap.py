"""Adapt each Resilum-managed interface's announce budget to channel activity.
RNS reads announce_cap live on every announce, so a discovered link lets
announces use the whole channel while idle (topology converges fast) and drops
them to ~1% once real traffic flows, yielding the (often narrow) channel to
data. Applies to every interface registered via register_in_transport — covert,
tor, i2p — but not the base interfaces owned by the stock rnsd process."""

import threading
import time

CAP_IDLE = 1.0
CAP_BUSY = 0.01
_THRESHOLD_BPS = 512  # "busy": above a node's own sparse announces, below real data
_WINDOW = 2.0  # throughput averaging window
_COOLDOWN = 5.0  # hold "busy" across short data gaps so the cap doesn't flap


def _iface_bytes(iface) -> int:
    rxb, txb = getattr(iface, "rxb", 0), getattr(iface, "txb", 0)
    # tolerate interfaces without numeric counters (e.g. test doubles)
    return (rxb if isinstance(rxb, int) else 0) + (txb if isinstance(txb, int) else 0)


class CapController:
    def __init__(self):
        self._entries: list = []  # [iface, last_bytes, busy_until]
        self._lock = threading.Lock()

    def attach(self, iface) -> None:
        iface.announce_cap = CAP_IDLE
        with self._lock:
            self._entries.append([iface, _iface_bytes(iface), 0.0])

    def tick(self, now: float) -> None:
        with self._lock:
            entries = list(self._entries)
        for entry in entries:
            iface, last, busy_until = entry
            total = _iface_bytes(iface)
            entry[1] = total
            if (total - last) / _WINDOW > _THRESHOLD_BPS:
                entry[2] = now + _COOLDOWN
                iface.announce_cap = CAP_BUSY
            elif now >= busy_until:
                iface.announce_cap = CAP_IDLE

    def start(self) -> None:
        def _loop():
            while True:
                time.sleep(_WINDOW)
                self.tick(time.monotonic())

        threading.Thread(target=_loop, daemon=True).start()


_controller: "CapController | None" = None
_lock = threading.Lock()


def adaptive_cap(iface) -> None:
    """Place iface under process-wide adaptive announce-cap control."""
    global _controller
    with _lock:
        if _controller is None:
            _controller = CapController()
            _controller.start()
    _controller.attach(iface)
