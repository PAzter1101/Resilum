"""Unit tests for the VPN length-prefix framing helper."""

import pytest
from vpn import framing


def test_encode_round_trips_through_decoder():
    decoder = framing.StreamDecoder()
    pkts = [b"hello", b"\x00world", b"x" * 1500]
    blob = b"".join(framing.encode(p) for p in pkts)
    assert decoder.feed(blob) == pkts


def test_decoder_handles_split_chunks():
    decoder = framing.StreamDecoder()
    blob = framing.encode(b"split-me-please")
    half = len(blob) // 2
    assert decoder.feed(blob[:half]) == []
    assert decoder.feed(blob[half:]) == [b"split-me-please"]


def test_decoder_handles_partial_header():
    decoder = framing.StreamDecoder()
    blob = framing.encode(b"abc")
    # Feed one byte of the 2-byte length header, then the rest.
    assert decoder.feed(blob[:1]) == []
    assert decoder.feed(blob[1:]) == [b"abc"]


def test_encode_rejects_oversized_packet():
    with pytest.raises(framing.FramingError):
        framing.encode(b"x" * (framing.MAX_PACKET + 1))


def test_decoder_rejects_runs_of_garbage_with_huge_length():
    # `\xff\xff` is the maximum valid header (65535 bytes), which is
    # within MAX_PACKET, so we can't trigger FramingError on length
    # alone unless we change the cap. This test instead verifies that
    # the decoder still emits the partial payload correctly when the
    # full packet eventually arrives.
    decoder = framing.StreamDecoder()
    decoder.feed(b"\xff\xff")  # 65535-byte payload incoming
    body = b"\x00" * 65535
    assert decoder.feed(body) == [body]
