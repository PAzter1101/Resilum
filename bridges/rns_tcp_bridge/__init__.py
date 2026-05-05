"""TCP-over-RNS-Link bridge.

Two run modes:

* `listen`  — bind to an RNS destination, accept incoming Links, forward
  each Link bidirectionally to a fixed TCP endpoint. Used on anchor
  nodes that already host a service (Yggdrasil, Tor, internal API, ...)
  and want to expose it to the Reticulum mesh.

* `connect` — listen on a local TCP port; for each incoming TCP
  connection open an RNS Link to a known anchor identity and forward
  bytes both ways. Used on clients that need to reach a service that
  lives behind the Reticulum mesh.

Entry point: ``python -m rns_tcp_bridge ...`` — see :mod:`.cli`.
"""
