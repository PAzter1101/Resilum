"""Unit tests for the discovery peer-cache helper."""

import os

from rns_tcp_bridge import cache


def test_upsert_inserts_new_endpoint(tmp_path):
    records = []
    cache.upsert(records, b"endpoint-A", now=100.0)
    assert len(records) == 1
    assert records[0]["first_seen"] == 100.0
    assert records[0]["last_seen"] == 100.0


def test_upsert_refreshes_existing_endpoint():
    records = []
    cache.upsert(records, b"endpoint-A", now=100.0)
    cache.upsert(records, b"endpoint-A", now=200.0)
    assert len(records) == 1
    assert records[0]["first_seen"] == 100.0
    assert records[0]["last_seen"] == 200.0


def test_prune_drops_records_older_than_ttl():
    records = []
    cache.upsert(records, b"old", now=0.0)
    cache.upsert(records, b"fresh", now=1000.0)
    removed = cache.prune(records, ttl_seconds=500, now=1000.0)
    assert removed == 1
    assert [bytes.fromhex(r["endpoint"]) for r in records] == [b"fresh"]


def test_top_n_returns_most_recently_seen():
    records = []
    cache.upsert(records, b"one", now=1.0)
    cache.upsert(records, b"two", now=2.0)
    cache.upsert(records, b"three", now=3.0)
    assert list(cache.top_n(records, 2)) == [b"three", b"two"]


def test_save_and_load_roundtrip(tmp_path):
    path = str(tmp_path / "peers.json")
    records = [{"endpoint": b"x".hex(), "first_seen": 1.0, "last_seen": 2.0}]
    cache.save(path, records)
    assert os.path.isfile(path)
    assert cache.load(path) == records


def test_load_returns_empty_for_missing_file(tmp_path):
    assert cache.load(str(tmp_path / "missing.json")) == []
