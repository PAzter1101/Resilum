"""HMAC-authenticated wire datagram: HEADER + payload + truncated HMAC tag."""

import hashlib
import hmac
import struct
from dataclasses import dataclass
from enum import IntEnum

_HEADER = struct.Struct(">IIIB")
HEADER_LEN = _HEADER.size
DEFAULT_TAG_LEN = 8


class Kind(IntEnum):
    DATA = 1
    POLL = 2
    HANDSHAKE = 3


def overhead(tag_len: int) -> int:
    return HEADER_LEN + tag_len


def peek_header(raw: bytes) -> "tuple[int, int, int, int] | None":
    if len(raw) < HEADER_LEN:
        return None
    return _HEADER.unpack(raw[:HEADER_LEN])


@dataclass(frozen=True)
class Datagram:
    session: int
    seq: int
    ack: int
    kind: int
    payload: bytes


def pack(dg: "Datagram", key: bytes, tag_len: int = DEFAULT_TAG_LEN) -> bytes:
    body = _HEADER.pack(dg.session, dg.seq, dg.ack, dg.kind) + dg.payload
    tag = hmac.new(key, body, hashlib.sha256).digest()[:tag_len]
    return body + tag


def unpack(raw: bytes, key: bytes, tag_len: int = DEFAULT_TAG_LEN) -> "Datagram | None":
    if len(raw) < HEADER_LEN + tag_len:
        return None
    if tag_len:
        body, tag = raw[:-tag_len], raw[-tag_len:]
        expect = hmac.new(key, body, hashlib.sha256).digest()[:tag_len]
        if not hmac.compare_digest(tag, expect):
            return None
    else:
        body = raw
    session, seq, ack, kind = _HEADER.unpack(body[:HEADER_LEN])
    return Datagram(session, seq, ack, kind, body[HEADER_LEN:])
