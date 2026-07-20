from covert.framing import RTO_INITIAL, RTO_MIN, SendBuffer


def test_chunks_respect_payload_size():
    sb = SendBuffer(payload_size=4, window=10)
    sb.write(b"abcdefg")
    out = sb.ready(now=0.0)
    assert [(seq, p) for seq, p in out] == [(1, b"abcd"), (2, b"efg")]


def test_window_limits_in_flight():
    sb = SendBuffer(payload_size=1, window=2)
    sb.write(b"abcd")
    first = sb.ready(now=0.0)
    assert [p for _, p in first] == [b"a", b"b"]
    assert sb.ready(now=0.0) == []


def test_ack_frees_window_and_drops_unacked():
    sb = SendBuffer(payload_size=1, window=2)
    sb.write(b"abcd")
    sb.ready(now=0.0)
    sb.ack(1, now=0.1)
    nxt = sb.ready(now=0.1)
    assert [(seq, p) for seq, p in nxt] == [(3, b"c")]


def test_retransmit_after_rto():
    sb = SendBuffer(payload_size=1, window=4)
    sb.write(b"a")
    sb.ready(now=0.0)
    assert sb.ready(now=1.0) == []
    assert sb.ready(now=RTO_INITIAL + 0.1) == [(1, b"a")]


def test_has_pending():
    sb = SendBuffer(payload_size=4, window=10)
    assert not sb.has_unsent()
    sb.write(b"x")
    assert sb.has_unsent()


def test_rto_adapts_down_from_fast_acks():
    sb = SendBuffer(payload_size=1, window=8)
    sb.write(b"ab")
    sb.ready(now=0.0)
    sb.ack(2, now=0.1)
    assert sb.rto < RTO_INITIAL
    assert sb.rto >= RTO_MIN


def test_rto_backs_off_on_retransmit():
    sb = SendBuffer(payload_size=1, window=4)
    sb.write(b"a")
    sb.ready(now=0.0)
    before = sb.rto
    sb.ready(now=RTO_INITIAL + 0.1)
    assert sb.rto > before


def test_karn_ignores_retransmitted_sample():
    sb = SendBuffer(payload_size=1, window=4)
    sb.write(b"a")
    sb.ready(now=0.0)
    sb.ready(now=RTO_INITIAL + 0.1)
    backed_off = sb.rto
    sb.ack(1, now=RTO_INITIAL + 0.2)
    assert sb.rto == backed_off
