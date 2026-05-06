"""Shared constants for the bridge."""

import os

# Aspect path under which bridge destinations are announced. The final
# element (``--service``) lets us run several independent bridges from
# the same identity (one for Yggdrasil, one for Tor, ...) without
# collisions.
DEFAULT_ASPECTS = ["resilum", "bridge", "tcp"]

# Periodic announce cadence. Default 10 minutes is a clearnet/Yggdrasil-
# friendly compromise — frequent enough that a peer joining the mesh
# discovers existing bridges within minutes, light enough to not flood
# the network. LoRa-only operators should bump this back up via the env
# var (e.g. RESILUM_BRIDGE_ANNOUNCE_INTERVAL=21600 for the upstream
# Reticulum default of 6h).
ANNOUNCE_INTERVAL_SECONDS = int(os.environ.get("RESILUM_BRIDGE_ANNOUNCE_INTERVAL", 600))
LINK_ESTABLISH_TIMEOUT = 30
PATH_REQUEST_TIMEOUT = 30

# Buffer chunk used by the byte pump in both directions.
SOCKET_CHUNK = 4096
