"""Latency monitor: link_rtt (passive warm Link) + egress_side (e2e
probe) → effective_latency, refreshed for the top-k eligible candidates."""

import threading
import time

import RNS

from ..constants import DEFAULT_ASPECTS, LINK_ESTABLISH_TIMEOUT
from .candidates import Candidate
from .dispatch import _resolve_target
from .probe import e2e_probe

PROBE_INTERVAL = 60.0  # seconds between e2e probes per candidate
TOP_K = 3  # warm Links maintained

_warm_links: dict[bytes, "RNS.Link"] = {}
_warm_lock = threading.Lock()


def egress_side_from_probe(e2e: float, link_rtt: float) -> float:
    """egress latency = e2e − link_rtt, floored at zero (noise guard)."""
    return max(0.0, e2e - link_rtt)


def _rank_key(c: Candidate):
    eff = c.effective_latency
    # measured before unmeasured; within measured, sort ascending
    return (0, eff) if eff is not None else (1, 0.0)


def top_k(candidates: list, k: int = TOP_K) -> list:
    """Up to k candidates: measured-first by effective_latency, then unmeasured."""
    return sorted(candidates, key=_rank_key)[:k]


def due_for_probe(c: Candidate, now: float, interval: float = PROBE_INTERVAL) -> bool:
    """True when never probed or last probe is stale."""
    return c.last_probe is None or (now - c.last_probe) >= interval


def _get_or_open_link(candidate: Candidate) -> "RNS.Link | None":
    """Reuse cached ACTIVE Link or open a new one; None on failure."""
    h = candidate.dest_hash
    with _warm_lock:
        link = _warm_links.get(h)

    if link is not None and link.status == RNS.Link.ACTIVE:
        return link

    dest = _resolve_target(h, DEFAULT_ASPECTS + [candidate.service])
    if dest is None:
        return None

    link = RNS.Link(dest)
    deadline = time.time() + LINK_ESTABLISH_TIMEOUT
    while time.time() < deadline and link.status != RNS.Link.ACTIVE:
        time.sleep(0.1)

    if link.status != RNS.Link.ACTIVE:
        link.teardown()
        return None

    def _on_closed(_lnk):
        with _warm_lock:
            if _warm_links.get(h) is _lnk:
                _warm_links.pop(h, None)

    link.set_link_closed_callback(_on_closed)
    with _warm_lock:
        _warm_links[h] = link
    return link


def _refresh_link_rtt(candidate: Candidate) -> None:
    """Open/reuse warm Link; copy RTT to candidate. healthy=False if Link fails."""
    link = _get_or_open_link(candidate)
    if link is None:
        candidate.healthy = False
        return
    rtt = link.rtt
    if rtt is not None and rtt > 0:
        candidate.link_rtt = rtt


def run(registry, eligible_fn, probe_targets, probe_fn=None, stop=None):
    """Warm Links to top-k eligible candidates; probe those due against
    ``probe_targets``. probe_fn injectable for tests."""
    probe_fn = probe_fn or e2e_probe
    stop = stop or threading.Event()
    while not stop.wait(1.0):
        cands = top_k(eligible_fn(registry.all()))
        now = time.monotonic()
        for c in cands:
            _refresh_link_rtt(c)
            if due_for_probe(c, now):
                e2e = probe_fn(c, probe_targets)
                c.last_probe = time.monotonic()
                if e2e is None:
                    c.healthy = False
                else:
                    c.healthy = True
                    c.egress_side = egress_side_from_probe(e2e, c.link_rtt or 0.0)
