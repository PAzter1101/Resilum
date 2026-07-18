from covert.datagram import Datagram, Kind, overhead, pack, peek_header, unpack

KEY = b"k" * 32


def test_round_trip():
    dg = Datagram(session=7, seq=3, ack=2, kind=Kind.DATA, payload=b"hello")
    assert unpack(pack(dg, KEY), KEY) == dg


def test_overhead_scales_with_tag_len():
    assert overhead(8) == 21
    assert overhead(4) == 17
    assert len(pack(Datagram(1, 1, 0, Kind.DATA, b""), KEY)) == overhead(8)


def test_custom_tag_len_round_trip():
    dg = Datagram(1, 1, 0, Kind.DATA, b"abc")
    wire = pack(dg, KEY, tag_len=4)
    assert len(wire) == overhead(4) + 3
    assert unpack(wire, KEY, tag_len=4) == dg


def test_wrong_tag_len_rejected():
    wire = pack(Datagram(1, 1, 0, Kind.DATA, b"abc"), KEY, tag_len=8)
    assert unpack(wire, KEY, tag_len=4) is None


def test_tampered_payload_rejected():
    wire = bytearray(pack(Datagram(1, 1, 0, Kind.DATA, b"abc"), KEY))
    wire[-9] ^= 0xFF
    assert unpack(bytes(wire), KEY) is None


def test_wrong_key_rejected():
    wire = pack(Datagram(1, 1, 0, Kind.DATA, b"abc"), KEY)
    assert unpack(wire, b"x" * 32) is None


def test_truncated_rejected():
    assert unpack(b"short", KEY) is None


def test_handshake_unauthenticated_round_trip():
    dg = Datagram(42, 0, 0, Kind.HANDSHAKE, b"sealed-token")
    wire = pack(dg, b"", tag_len=0)
    assert len(wire) == overhead(0) + len(b"sealed-token")
    assert unpack(wire, b"", tag_len=0) == dg


def test_peek_header_reads_kind_without_key():
    dg = Datagram(session=42, seq=0, ack=0, kind=Kind.HANDSHAKE, payload=b"tok")
    session, seq, ack, kind = peek_header(pack(dg, b"", tag_len=0))
    assert session == 42 and kind == Kind.HANDSHAKE


def test_peek_header_short_returns_none():
    assert peek_header(b"tiny") is None
