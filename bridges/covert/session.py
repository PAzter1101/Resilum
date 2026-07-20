"""Server-side per-client state, keyed by the datagram's session id."""

from dataclasses import dataclass

from .framing import RecvBuffer, SendBuffer


@dataclass
class Session:
    send: SendBuffer
    recv: RecvBuffer
    reply_to: object = None
    last_seen: float = 0.0
    key: "bytes | None" = None


class SessionTable:
    def __init__(self, size_for, window: int, ttl: float = 300.0):
        self._size_for = size_for
        self._window = window
        self._ttl = ttl
        self._sessions: dict[int, Session] = {}

    def get(self, session_id: int, now: float, reply_to=None) -> Session:
        s = self._sessions.get(session_id)
        if s is None:
            s = Session(
                SendBuffer(self._size_for(reply_to), self._window), RecvBuffer()
            )
            self._sessions[session_id] = s
        s.last_seen = now
        return s

    def expire(self, now: float) -> None:
        stale = [
            sid for sid, v in self._sessions.items() if now - v.last_seen > self._ttl
        ]
        for sid in stale:
            del self._sessions[sid]

    def established(self) -> list:
        return [s for s in self._sessions.values() if s.key is not None]

    def count(self) -> int:
        return len(self._sessions)
