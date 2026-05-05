"""ABC for transport-specific discovery plugins."""

from abc import ABC, abstractmethod


class DiscoveryPlugin(ABC):
    """A discovery plugin knows how to announce one transport endpoint
    and how to act on someone else's announcement of the same
    transport. Both halves are mandatory: announce-only or
    consume-only deployments are configured by simply not enabling the
    relevant `mode: listen` bridge — see project memory
    `feedback_resilum_p2p_symmetry`.
    """

    @abstractmethod
    def produce_endpoint(self) -> bytes:
        """Return the bytes describing where this node accepts peers
        over the plugin's transport. Format is opaque to the discovery
        framework — only the matching `consume_endpoint` needs to
        parse it.

        Raise an exception if the local transport is not yet ready;
        the discovery loop will retry."""

    @abstractmethod
    def consume_endpoint(self, payload: bytes) -> None:
        """Act on a peer's announcement. Typically registers a new
        Reticulum interface (TCPClient, etc) so the active RNS stack
        starts using the freshly discovered peer."""
