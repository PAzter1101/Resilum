"""Shared constants for the bridge."""

# Aspect path under which bridge destinations are announced. The final
# element (``--service``) lets us run several independent bridges from
# the same identity (one for Yggdrasil, one for Tor, ...) without
# collisions.
DEFAULT_ASPECTS = ["resilum", "bridge", "tcp"]

# Tunables. The announce interval matches the RNS default so the bridge
# does not pollute the mesh with extra announces. The two timeouts apply
# to both directions of the path-request / link-establish handshake.
ANNOUNCE_INTERVAL_SECONDS = 6 * 60 * 60
LINK_ESTABLISH_TIMEOUT    = 30
PATH_REQUEST_TIMEOUT      = 30

# Buffer chunk used by the byte pump in both directions.
SOCKET_CHUNK = 4096
