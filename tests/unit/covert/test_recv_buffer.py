from covert.framing import RecvBuffer


def test_in_order_delivers_immediately():
    rb = RecvBuffer()
    assert rb.feed(1, b"a") == b"a"
    assert rb.feed(2, b"b") == b"b"
    assert rb.ack == 2


def test_out_of_order_buffers_then_flushes():
    rb = RecvBuffer()
    assert rb.feed(2, b"b") == b""
    assert rb.ack == 0
    assert rb.feed(1, b"a") == b"ab"
    assert rb.ack == 2


def test_duplicate_and_old_dropped():
    rb = RecvBuffer()
    rb.feed(1, b"a")
    assert rb.feed(1, b"a") == b""
    assert rb.ack == 1
