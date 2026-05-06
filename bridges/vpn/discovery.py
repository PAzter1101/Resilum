"""VPN-anchor discovery via RNS announces.

Listens on the announce stream for ``resilum.vpn.gateway`` and
collects the destination hashes of nodes that advertise themselves
as VPN servers. Used by the client to skip the explicit
``--target`` argument.

This is deliberately thinner than the generic discovery framework
under ``rns_tcp_bridge/discovery_plugins`` — VPN clients hold a
single Link at a time, so we only need a "give me one anchor"
helper, not a top-N scoreboard.
"""

import time

from .server import VPN_ASPECTS

ASPECT_PATH = ".".join(VPN_ASPECTS)


class GatewayDiscovery:
    """RNS announce handler that buffers gateway destination hashes.

    The handler interface is the duck-typed contract that
    ``RNS.Transport.register_announce_handler`` expects: an
    ``aspect_filter`` attribute and a ``received_announce`` method."""

    aspect_filter = ASPECT_PATH
    receive_path_responses = False

    def __init__(self):
        self._candidates: list[bytes] = []

    def received_announce(self, destination_hash, _identity, _app_data):
        if destination_hash not in self._candidates:
            self._candidates.append(destination_hash)

    def wait_for_one(self, timeout: float) -> bytes | None:
        deadline = time.time() + timeout
        while not self._candidates and time.time() < deadline:
            time.sleep(0.5)
        return self._candidates[0] if self._candidates else None
