"""Persistent peer cache for the discovery loop.

Records are kept in a JSON file under /config/discovered/<service>.json
so the next process can warm-start with whoever was reachable last
time. Each record carries `first_seen` / `last_seen` (UNIX ts) and
the opaque endpoint bytes encoded as a hex string.
"""

import json
import os
import time
from typing import Iterable


def _ensure_dir(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def load(path: str) -> list[dict]:
    if not os.path.isfile(path):
        return []
    try:
        with open(path) as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def save(path: str, records: list[dict]) -> None:
    _ensure_dir(path)
    tmp = f"{path}.tmp"
    with open(tmp, "w") as fh:
        json.dump(records, fh, indent=2)
    os.replace(tmp, path)


def upsert(records: list[dict], endpoint: bytes, *, now: float | None = None) -> None:
    """Insert a fresh record or refresh ``last_seen`` on an existing
    one matching ``endpoint``. Mutates ``records`` in place."""
    ts = now if now is not None else time.time()
    hex_endpoint = endpoint.hex()
    for rec in records:
        if rec.get("endpoint") == hex_endpoint:
            rec["last_seen"] = ts
            return
    records.append(
        {
            "endpoint": hex_endpoint,
            "first_seen": ts,
            "last_seen": ts,
        }
    )


def prune(records: list[dict], ttl_seconds: int, *, now: float | None = None) -> int:
    """Drop records whose ``last_seen`` is older than ``ttl_seconds``.
    Returns the number of records removed."""
    cutoff = (now if now is not None else time.time()) - ttl_seconds
    keep = [r for r in records if r.get("last_seen", 0) >= cutoff]
    removed = len(records) - len(keep)
    if removed:
        records[:] = keep
    return removed


def top_n(records: list[dict], n: int) -> Iterable[bytes]:
    """Return the n most recently seen endpoints (as raw bytes), most
    recent first. Used by the discovery loop to decide which peers
    are currently active."""
    ranked = sorted(records, key=lambda r: r.get("last_seen", 0), reverse=True)
    for rec in ranked[:n]:
        try:
            yield bytes.fromhex(rec["endpoint"])
        except (KeyError, ValueError):
            continue
