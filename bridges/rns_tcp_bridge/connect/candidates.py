"""Discovered egress candidates and the registry that holds them."""

import threading
from dataclasses import dataclass


@dataclass(eq=False)
class Candidate:
    dest_hash: bytes
    service: str
    exit_country: str = "*"
    capabilities: tuple = ()
    link_rtt: float | None = None  # seconds, mesh leg (consumer -> provider)
    egress_side: float | None = None  # seconds, egress leg (provider -> internet)
    healthy: bool = True
    last_probe: float | None = None  # monotonic timestamp of last e2e probe

    @property
    def effective_latency(self) -> float | None:
        if self.link_rtt is None or self.egress_side is None:
            return None
        return self.link_rtt + self.egress_side


class CandidateRegistry:
    def __init__(self):
        self._by_service: dict[str, dict[bytes, Candidate]] = {}
        self._lock = threading.Lock()

    def upsert(self, service, dest_hash, exit_country="*", capabilities=()):
        with self._lock:
            svc = self._by_service.setdefault(service, {})
            cand = svc.get(dest_hash)
            if cand is None:
                cand = Candidate(dest_hash=dest_hash, service=service)
                svc[dest_hash] = cand
            cand.exit_country = exit_country
            cand.capabilities = tuple(capabilities)
            return cand

    def remove(self, service, dest_hash):
        with self._lock:
            self._by_service.get(service, {}).pop(dest_hash, None)

    def for_service(self, service):
        with self._lock:
            return list(self._by_service.get(service, {}).values())

    def all(self):
        with self._lock:
            return [c for svc in self._by_service.values() for c in svc.values()]
