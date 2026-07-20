"""Covert server engine: unseal keys, demux by session, broadcast downlink."""

from . import keyx
from .datagram import (
    HEADER_LEN,
    Datagram,
    Kind,
    overhead,
    pack,
    peek_header,
    unpack,
)
from .session import SessionTable


class ServerEngine:
    def __init__(self, carrier, own_identity, on_output=None, table=None):
        self._carrier = carrier
        self._identity = own_identity
        self._on_output = on_output or (lambda peer, b: None)
        self._tag = carrier.tag_len
        self.table = table or SessionTable(self._payload_size, window=8)

    def _payload_size(self, reply_to) -> int:
        capacity: int = self._carrier.capacity_for(reply_to)
        return capacity - overhead(self._tag)

    def broadcast(self, data: bytes) -> None:
        for s in self.table.established():
            s.send.write(data)

    def poll(self, now: float) -> None:
        self.table.expire(now)

    def on_received(self, raw, now: float) -> None:
        parsed = self._carrier.parse_request(raw)
        if parsed is None:
            return
        reply_to, wire = parsed
        header = peek_header(wire)
        if header is None:
            return
        session_id, _, _, kind = header
        if kind == Kind.HANDSHAKE:
            self._open(session_id, wire[HEADER_LEN:], reply_to, now)
            return
        s = self.table.get(session_id, now, reply_to)
        if s.key is None:
            return
        dg = unpack(wire, s.key, self._tag)
        if dg is None:
            return
        s.reply_to = reply_to
        s.send.ack(dg.ack, now)
        if dg.kind == Kind.DATA and dg.payload:
            out = s.recv.feed(dg.seq, dg.payload)
            if out:
                self._on_output(session_id, out)
        self._respond(s, session_id, now)

    def _open(self, session_id: int, token: bytes, reply_to, now: float) -> None:
        key = keyx.unseal(self._identity, token)
        if key is None:
            return
        s = self.table.get(session_id, now, reply_to)
        s.key = key
        s.reply_to = reply_to
        self._respond(s, session_id, now)

    def _respond(self, s, session_id: int, now: float) -> None:
        pkts = s.send.ready(now) or [(0, None)]
        for seq, payload in pkts:
            kind = Kind.DATA if payload else Kind.POLL
            dg = Datagram(session_id, seq, s.recv.ack, kind, payload or b"")
            wire = pack(dg, s.key, self._tag)
            self._carrier.send(self._carrier.build_response(s.reply_to, wire))
