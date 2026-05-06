"""Layer-3 VPN over Reticulum.

Two roles:

* `server` — anchor with clearnet uplink. Creates a TUN interface on
  the host, NATs traffic out via iptables MASQUERADE, accepts RNS
  Links from clients and pumps IP packets between the Link and the
  TUN device.

* `client` — host without direct internet (e.g. only LoRa). Opens an
  RNS Link to a known anchor, receives an IP allocation, brings up a
  local TUN with that IP, and points the host's default route at it
  so all userland traffic transits the mesh.

Designed to run alongside `rns_tcp_bridge` and the discovery
framework — the VPN is just another transport-of-last-resort, not a
replacement for service-specific bridges.

Entry point: ``python -m bridges.vpn server|client ...`` (see
:mod:`.cli`).
"""
