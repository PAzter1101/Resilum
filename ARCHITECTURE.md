# Resilum architecture

Data-flow and identity-model details. For installation and usage, see the
[README](README.md).

## Data flow

A SOCKS5 proxy on each host tunnels through Reticulum to a peer with internet
and exits from that peer's public IP. Reticulum picks the best underlay per
destination and falls back on failure:

```text
host app  ──ALL_PROXY=socks5h://127.0.0.1:10808──▶  rns_tcp_bridge (connect)
                                                            │
                                                            ▼
                                                     ┌──────────────┐
                                                     │  Reticulum   │
                                                     │ (rnsd, MTU-  │
                                                     │  agnostic,   │
                                                     │  picks best  │
                                                     │  underlay)   │
                                                     └──────┬───────┘
                            picks dynamically per destination, falls back on failure
                                                            │
              ┌─────────────────┬───────────────┬───────────┴──────┬────────────────┐
              ▼                 ▼               ▼                  ▼                ▼
        clearnet TCP     Yggdrasil 200::/7   Tor onion          I2P b32        LoRa (radio)
        (public hubs    (overlay IPv6,     (via local Tor    (via local i2pd
         from registry,  routes through    SOCKS @9050,      SOCKS @4447,
         + your own      whatever          rdns=true)        rdns=true)
         personal        underlays
         anchors)        still work)
                                                            │
                                                            ▼
                                                rns_tcp_bridge (listen)  on the egress peer
                                                            │
                                                            ▼
                                                  microsocks @127.0.0.1:1080
                                                            │
                                                            ▼
                                                  socket.connect(host:port)
                                                            │
                                                            ▼
                                                     clearnet — egress
                                                     peer's public IP
```

When one underlay goes away (path blocked, peer offline, LoRa link lost),
Reticulum reroutes through the next without dropping the active session.

## Identities and destinations

A node holds **several** Reticulum identities at once, each with a different
role. They live as separate files under `/config/` and survive container
restarts, so the destination hashes peers learned from earlier announces stay
valid:

```text
                          ┌─────── Resilum node ───────┐
                          │                            │
                          ▼                            │
       ┌─────────────────────────────────────┐         │
       │ 1× network identity                 │         │
       │ /config/reticulum/storage/          │         │
       │   identities/resilum                │         │
       │                                     │         │
       │ → signs every announce that rnsd    │         │
       │   emits for its transport           │         │
       │   interfaces (clearnet TCP,         │         │
       │   Yggdrasil, Tor, I2P, LoRa)        │         │
       │ → no aspect of its own; not used    │         │
       │   for application destinations      │         │
       └─────────────────────────────────────┘         │
                                                       │
                          ┌──────── one per service ───┘
                          ▼
       ┌─────────────────────────────────────┐
       │ N× bridge identities                │
       │ /config/bridges/yggdrasil.id        │
       │ /config/bridges/tor.id              │
       │ /config/bridges/i2p.id              │
       │ /config/bridges/socks-egress.id     │
       │   (created only when egress         │
       │    role is opted into)              │
       │ /config/bridges/socks-egress-out.id │
       │   (connect-side, used only to       │
       │    skip our own announces)          │
       │                                     │
       │ → each yields a distinct            │
       │   destination_hash on aspect        │
       │   resilum.bridge.tcp.<service>      │
       │ → each announces independently      │
       │   every ANNOUNCE_INTERVAL_SECONDS,  │
       │   or instantly when a new           │
       │   underlay interface comes up       │
       └─────────────────────────────────────┘

       ┌─────────────────────────────────────┐
       │ 2× VPN identities (when L3 VPN on)  │
       │ /config/vpn/server.id               │
       │ /config/vpn/client.id               │
       │                                     │
       │ → aspect resilum.vpn.gateway        │
       └─────────────────────────────────────┘
```

The split matters because connect-side bridges resolve targets by destination
hash — separate identities give peers a stable per-service hash to dial. If
everything shared one identity, the connect-side fallback chain
(`[socks-egress, tor, …]`) would have to track `identity_hash + aspect` pairs
instead of plain hashes, and skip-self detection during auto-discovery would
get tangled with which aspect the announce came in on.

Transport interfaces themselves (TCPInterface, AutoInterface, LoRaInterface,
our `SocksTCPClientInterface`) do **not** own identities — they piggyback on
the network identity to sign announce traffic at the RNS Transport layer.
