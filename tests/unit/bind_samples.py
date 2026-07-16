"""Shared config samples for the bind_config unit tests."""

import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULTS = os.path.join(ROOT, "config", "defaults")

YGG_SAMPLE = """\
{
  Listen: [
    "tcp://127.0.0.1:9000"
    # >>> resilum:managed ygg-public-listen — rendered from RESILUM_YGG_PUBLIC_LISTEN
    "tcp://[::]:65533"
    # <<< resilum:managed
  ]
}
"""

RNS_SAMPLE = """\
[interfaces]
  [[LAN AutoDiscovery]]
    type = AutoInterface
    enabled = yes

  # >>> resilum:managed rns-public-listen — rendered from RESILUM_RNS_LISTEN
  [[Public TCP listener]]
    type = TCPServerInterface
    enabled = yes
    listen_ip = ::
    listen_port = 4242
    discoverable = yes
    discovery_name = resilum
    mode = gateway
  # <<< resilum:managed

  [[Bootstrap — Reserve.Network DE]]
    type = TCPClientInterface
    enabled = yes
"""
