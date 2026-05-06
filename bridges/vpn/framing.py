"""Length-prefixed IP-packet framing on a byte-stream.

The RNS Link delivers an unstructured byte stream; IP packets are
discrete units, so we wrap each one as ``<len:2 BE><payload>`` and
stitch them back on the receiving side.

A 16-bit length supports IP packets up to 65535 bytes, which already
exceeds the Linux IP MTU and is well above any TUN MTU we'll
realistically pick.
"""

import struct

LENGTH_BYTES = 2
HEADER       = struct.Struct(">H")
MAX_PACKET   = (1 << 16) - 1


class FramingError(Exception):
    """Raised when the peer sends an oversize or malformed packet."""


def encode(packet: bytes) -> bytes:
    if len(packet) > MAX_PACKET:
        raise FramingError(f"IP packet too large to frame: {len(packet)} bytes")
    return HEADER.pack(len(packet)) + packet


class StreamDecoder:
    """Pull complete IP packets out of arbitrarily-chunked input."""

    def __init__(self):
        self._buf = bytearray()

    def feed(self, chunk: bytes) -> list[bytes]:
        """Append ``chunk`` to the internal buffer and return any
        complete packets produced as a result. Partial frames remain
        buffered for the next call."""
        self._buf.extend(chunk)
        out: list[bytes] = []
        while True:
            if len(self._buf) < LENGTH_BYTES:
                break
            (length,) = HEADER.unpack(self._buf[:LENGTH_BYTES])
            if length > MAX_PACKET:
                raise FramingError(f"frame length out of range: {length}")
            total = LENGTH_BYTES + length
            if len(self._buf) < total:
                break
            out.append(bytes(self._buf[LENGTH_BYTES:total]))
            del self._buf[:total]
        return out
