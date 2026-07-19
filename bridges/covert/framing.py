"""Sliding-window ARQ over a lossy datagram carrier."""

from typing import NamedTuple

RTO_INITIAL = 2.0
RTO_MIN = 0.5
RTO_MAX = 30.0
_ALPHA = 0.125
_BETA = 0.25
_K = 4


def _clamp_rto(rto: float) -> float:
    return max(RTO_MIN, min(RTO_MAX, rto))


class _Unacked(NamedTuple):
    payload: bytes
    sent_at: float
    retransmitted: bool


class SendBuffer:
    def __init__(self, payload_size: int, window: int):
        self._size = payload_size
        self._window = window
        self._pending = bytearray()
        self._next_seq = 1
        self._acked = 0
        self._unacked: dict[int, _Unacked] = {}
        self._srtt: float | None = None
        self._rttvar = 0.0
        self._rto = RTO_INITIAL

    @property
    def payload_size(self) -> int:
        return self._size

    @property
    def rto(self) -> float:
        return self._rto

    def write(self, data: bytes) -> None:
        self._pending.extend(data)

    def has_unsent(self) -> bool:
        return bool(self._pending)

    def ack(self, ack_seq: int, now: float) -> None:
        if ack_seq <= self._acked:
            return
        sample = None
        for seq in range(self._acked + 1, ack_seq + 1):
            chunk = self._unacked.get(seq)
            if chunk is not None and not chunk.retransmitted:
                sample = now - chunk.sent_at
        self._acked = ack_seq
        for seq in [s for s in self._unacked if s <= ack_seq]:
            del self._unacked[seq]
        if sample is not None:
            self._observe_rtt(sample)

    def _observe_rtt(self, r: float) -> None:
        if self._srtt is None:
            self._srtt, self._rttvar = r, r / 2
        else:
            self._rttvar = (1 - _BETA) * self._rttvar + _BETA * abs(self._srtt - r)
            self._srtt = (1 - _ALPHA) * self._srtt + _ALPHA * r
        self._rto = _clamp_rto(self._srtt + _K * self._rttvar)

    def ready(self, now: float) -> list[tuple[int, bytes]]:
        out: list[tuple[int, bytes]] = []
        resent = False
        for seq in sorted(self._unacked):
            chunk = self._unacked[seq]
            if now - chunk.sent_at >= self._rto:
                self._unacked[seq] = _Unacked(chunk.payload, now, True)
                out.append((seq, chunk.payload))
                resent = True
        if resent:
            self._rto = _clamp_rto(self._rto * 2)
        while self._pending and (self._next_seq - self._acked - 1) < self._window:
            payload = bytes(self._pending[: self._size])
            del self._pending[: self._size]
            self._unacked[self._next_seq] = _Unacked(payload, now, False)
            out.append((self._next_seq, payload))
            self._next_seq += 1
        return out


class RecvBuffer:
    def __init__(self) -> None:
        self._expected = 1
        self._buf: dict[int, bytes] = {}

    def feed(self, seq: int, payload: bytes) -> bytes:
        if seq < self._expected:
            return b""
        self._buf[seq] = payload
        out = bytearray()
        while self._expected in self._buf:
            out += self._buf.pop(self._expected)
            self._expected += 1
        return bytes(out)

    @property
    def ack(self) -> int:
        return self._expected - 1
