from covert.session import SessionTable


def test_get_or_create_is_stable():
    t = SessionTable(payload_size=8, window=4)
    s1 = t.get(session_id=42, now=0.0)
    s2 = t.get(session_id=42, now=1.0)
    assert s1 is s2
    assert s1.send is not None and s1.recv is not None


def test_session_key_starts_unset_and_is_settable():
    s = SessionTable(payload_size=8, window=4).get(1, now=0.0)
    assert s.key is None
    s.key = b"k" * 32
    assert s.key == b"k" * 32


def test_distinct_sessions_isolated():
    t = SessionTable(payload_size=8, window=4)
    assert t.get(1, now=0.0) is not t.get(2, now=0.0)


def test_expire_removes_stale():
    t = SessionTable(payload_size=8, window=4, ttl=10.0)
    t.get(1, now=0.0)
    t.get(2, now=9.0)
    t.expire(now=11.0)
    assert t.count() == 1
