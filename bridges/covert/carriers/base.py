"""Carrier contract. The engine passes opaque `wire` bytes and gets them back;
`reply_to` only addresses the answer — demux is by the datagram's session, so a
carrier stays oblivious to seq/ack/auth."""

from abc import ABC, abstractmethod
from typing import Callable, Literal, Optional, Tuple


class Carrier(ABC):
    name: str
    semantics: Literal["poll", "push"] = "poll"
    tag_len: int = 8

    @property
    @abstractmethod
    def capacity(self) -> int: ...

    def capacity_for(self, dest) -> int:
        """Capacity when addressing ``dest``. Carriers whose payload budget
        varies by destination (e.g. IPv4 vs IPv6 headers) override this; the
        default is destination-independent."""
        return self.capacity

    @abstractmethod
    def build_request(self, reply_to, wire: bytes): ...

    @abstractmethod
    def parse_request(self, raw) -> Optional[Tuple[object, bytes]]: ...

    @abstractmethod
    def build_response(self, reply_to, wire: bytes): ...

    @abstractmethod
    def parse_response(self, raw) -> Optional[bytes]: ...

    @abstractmethod
    def send(self, packet) -> None: ...

    @abstractmethod
    def sniff(self, on_raw: Callable[[object], None], stop) -> None: ...
