from covert.session import SessionTable


def _table(**kw):
    return SessionTable(lambda _reply_to: 8, window=4, **kw)


def test_get_or_create_is_stable():
    t = _table()
    s1 = t.get(session_id=42, now=0.0)
    s2 = t.get(session_id=42, now=1.0)
    assert s1 is s2
    assert s1.send is not None and s1.recv is not None


def test_session_key_starts_unset_and_is_settable():
    s = _table().get(1, now=0.0)
    assert s.key is None
    s.key = b"k" * 32
    assert s.key == b"k" * 32


def test_distinct_sessions_isolated():
    t = _table()
    assert t.get(1, now=0.0) is not t.get(2, now=0.0)


def test_send_buffer_sized_by_reply_to():
    t = SessionTable(lambda reply_to: 40 if reply_to == "v6" else 60, window=4)
    assert t.get(1, now=0.0, reply_to="v6").send.payload_size == 40
    assert t.get(2, now=0.0, reply_to="v4").send.payload_size == 60


def test_expire_removes_stale():
    t = _table(ttl=10.0)
    t.get(1, now=0.0)
    t.get(2, now=9.0)
    t.expire(now=11.0)
    assert t.count() == 1
