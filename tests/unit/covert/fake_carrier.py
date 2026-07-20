"""In-memory carrier for engine tests. Moves wire bytes between a client
and a server engine via two lists, with optional loss/reorder/dup. Packets
are (reply_to, wire) tuples; reply_to is a fake peer id."""

from covert.carriers.base import Carrier


class _Link:
    def __init__(self):
        self.to_server = []
        self.to_client = []


class FakeClientCarrier(Carrier):
    name = "fake"

    def __init__(self, link, peer="client-A", drop=(), capacity=64):
        self._link, self._peer, self._drop, self._cap = link, peer, set(drop), capacity
        self._n = 0

    @property
    def capacity(self):
        return self._cap

    def build_request(self, reply_to, wire):
        return wire

    def parse_response(self, raw):
        return raw

    def build_response(self, reply_to, wire):
        return wire

    def parse_request(self, raw):
        return None

    def send(self, packet):
        self._n += 1
        if self._n not in self._drop:
            self._link.to_server.append((self._peer, packet))

    def sniff(self, on_raw, stop):
        while self._link.to_client:
            on_raw(self._link.to_client.pop(0))


class FakeServerCarrier(Carrier):
    name = "fake"

    def __init__(self, link, capacity=64):
        self._link, self._cap = link, capacity

    @property
    def capacity(self):
        return self._cap

    def build_response(self, reply_to, wire):
        return wire

    def parse_request(self, raw):
        reply_to, wire = raw
        return (reply_to, wire)

    def build_request(self, reply_to, wire):
        return wire

    def parse_response(self, raw):
        return raw

    def send(self, packet):
        self._link.to_client.append(packet)

    def sniff(self, on_raw, stop):
        while self._link.to_server:
            on_raw(self._link.to_server.pop(0))
