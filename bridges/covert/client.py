"""Covert client engine: handshake a per-link key, then pump ARQ over the carrier."""

from . import keyx
from .datagram import Datagram, Kind, overhead, pack, unpack
from .framing import RecvBuffer, SendBuffer
from .poll import AdaptivePoll

HANDSHAKE_INTERVAL = 5.0


class ClientEngine:
    def __init__(
        self,
        carrier,
        server_identity,
        session_id,
        on_output=None,
        min_poll=0.2,
        max_poll=4.0,
    ):
        self._carrier = carrier
        self._server = server_identity
        self._sid = session_id
        self._on_output = on_output or (lambda b: None)
        self._tag = carrier.tag_len
        self._key = keyx.new_session_key()
        self._send = SendBuffer(carrier.capacity - overhead(self._tag), window=8)
        self._recv = RecvBuffer()
        self._poll = AdaptivePoll(min_poll, max_poll)
        self._last_poll = -1e9
        self._last_hs = -1e9
        self._established = False
        self._had_traffic = False

    def write(self, data: bytes) -> None:
        self._send.write(data)

    def on_received(self, raw, now: float) -> None:
        wire = self._carrier.parse_response(raw)
        dg = unpack(wire, self._key, self._tag) if wire is not None else None
        if dg is None:
            return
        self._established = True
        self._send.ack(dg.ack, now)
        if dg.kind == Kind.DATA and dg.payload:
            out = self._recv.feed(dg.seq, dg.payload)
            if out:
                self._had_traffic = True
                self._on_output(out)

    def poll(self, now: float) -> None:
        if not self._established and now - self._last_hs >= HANDSHAKE_INTERVAL:
            token = keyx.seal(self._server, self._key)
            hs = Datagram(self._sid, 0, 0, Kind.HANDSHAKE, token)
            self._carrier.send(self._carrier.build_request(None, pack(hs, b"", 0)))
            self._last_hs = now
        due = now - self._last_poll >= self._poll.interval()
        pkts = self._send.ready(now)
        if pkts:
            for seq, payload in pkts:
                self._emit(Datagram(self._sid, seq, self._recv.ack, Kind.DATA, payload))
            self._last_poll = now
        elif due:
            self._emit(Datagram(self._sid, 0, self._recv.ack, Kind.POLL, b""))
            self._last_poll = now
        self._poll.observe(self._had_traffic)
        self._had_traffic = False

    def _emit(self, dg: "Datagram") -> None:
        wire = pack(dg, self._key, self._tag)
        self._carrier.send(self._carrier.build_request(None, wire))
