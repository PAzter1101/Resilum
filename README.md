# Resilum

> Multi-transport mesh node for resilient, censorship-resistant connectivity.

A single Docker container that turns any laptop, SBC or VPS into a node of a
global mesh network running on top of [Reticulum](https://reticulum.network/).
Connectivity gracefully degrades from clearnet TCP/IP through Yggdrasil and
Tor down to email-, ICMP- or DNS-tunnels and finally LoRa radio — whatever
still works in the current environment is used automatically.

The goal is the same as Tor's: anyone with a spare device can join, route
traffic for others, and benefit from the network's collective bandwidth and
fault-tolerance. Unlike Tor, Resilum is not tied to TCP/IP — when the
underlying internet is unavailable, the same node keeps talking to its peers
over LoRa or covert channels, and the encrypted overlay continues to deliver
traffic.

## Status

Multi-arch images (`amd64`, `arm64`) for all four profiles publish
to **GitHub Container Registry** and **Docker Hub** via
`semantic-release`. Bidirectional Tor/I2P discovery, SOCKS5 egress
through the mesh, RNS interface-discovery, auto-selected community
bootstraps — all working end to end. L3-VPN tun-mode (full
default-route redirect) and the Web UI are planned, not built yet.

## Architecture

What actually exists today is a SOCKS5 proxy on every host, tunnelled
through Reticulum to a peer with internet, exiting from that peer's
public IP:

```
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

By default a Resilum node only runs the connect side — its own apps
can use someone else's exit, but the node does not itself relay other
peers' traffic out of its public IP. Becoming an exit is opt-in (set
`ENABLE_SOCKS_EGRESS=1` and uncomment the `listen socks-egress` block
in `bridges.yaml`); operators take it on knowingly because the IP
that downstream traffic appears to come from is theirs, with the same
legal/abuse exposure as a Tor exit or a public VPN. Targets are
discovered automatically through signed RNS announces; no static
peer lists.

When one underlay dies (clearnet blocked, peer offline, LoRa link
lost), Reticulum reroutes through the next without dropping the
active session.

## Identities and destinations

A Resilum node holds **several** Reticulum identities at once, each
with a different role. They live as separate files under `/config/`
and survive container restarts, so the destination hashes other
peers learned from earlier announces stay valid:

```
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

The split matters because connect-side bridges resolve targets by
destination hash — separate identities give peers a stable per-service
hash to dial. If everything shared one identity, the connect-side
fallback chain (`[socks-egress, tor, …]`) would have to track
`identity_hash + aspect` pairs instead of plain hashes, and skip-self
detection during auto-discovery would get tangled with which aspect
the announce came in on.

Transport interfaces themselves (TCPInterface, AutoInterface,
LoRaInterface, our `SocksTCPClientInterface`) do **not** own
identities — they piggyback on the network identity to sign
announce traffic at the RNS Transport layer.

## Bundled transports

| Transport | Source | Status |
|---|---|---|
| TCP / UDP / AutoInterface | Reticulum core | ready |
| LoRa (RNode hardware) | Reticulum core + RTNode firmware | ready |
| Yggdrasil-IPv6 mesh | [yggdrasil-network/yggdrasil-go](https://github.com/yggdrasil-network/yggdrasil-go) | ready |
| Tor onion as RNS-link | local Tor SOCKS + custom `SocksTCPClientInterface` | ready |
| I2P b32 as RNS-link | local i2pd SOCKS + custom `SocksTCPClientInterface` | ready |
| Meshtastic radios | [Nursedude/RNS-Meshtastic-Gateway-Tool](https://github.com/Nursedude/RNS-Meshtastic-Gateway-Tool) | bundled, not yet wired into discovery |
| Email (IMAP/SMTP, fixed-size, locale-camo) | [TechVoid-Co/rns-covert-transport](https://github.com/TechVoid-Co/rns-covert-transport) | bundled in covert profile, integration planned |
| ICMP-tunnel | [matvik22000/rns-over-icmp](https://github.com/matvik22000/rns-over-icmp) | bundled in covert profile, integration planned |
| DNS-tunnel (iodine) | community recipe | binary in covert profile, integration planned |

## Image profiles

The container is built as four feature-supersets so each operator picks
the one that fits their hardware and threat model. Every component in any
profile can still be switched on/off at runtime via the config file or the
web UI — the profile only controls what is *physically in the image*.

| Tag | What it bundles | Typical use |
|---|---|---|
| `resilum:lora` | rnsd + native RNS (TCP/UDP/AutoInterface) + USB stack for LoRa radios + iptables policy router | Minimum LoRa bridge: laptop with a Heltec, Pi Zero without other networks |
| `resilum:mesh` | `lora` + Yggdrasil-go + i2pd | Node in the public mesh overlays; SBC that already has clearnet |
| `resilum:covert` | `mesh` + Tor + obfs4proxy + iodine + rns-over-icmp + rns-covert-transport (email) | Anti-censorship profile |
| `resilum:full` | `covert` + Meshtastic gateway + any experimental transports | All-in-one, nothing missing |

Each profile is a superset of the previous one, so layers cache cleanly and
upgrade paths are linear. Multi-arch builds (`amd64`, `arm64`) via
`docker buildx`, so the same tag pulls the right binary on an Orange Pi,
a Raspberry Pi 4/5, or an x86 laptop.

`debian:trixie-slim` base, multi-stage build, no Rust toolchain, runtime
only in the final layer.

## Where to run it

Resilum is the same image everywhere — pick the profile that matches the
role the device should play in the mesh.

| Device | Role in the mesh | Compose profile | What goes in `config/` |
|---|---|---|---|
| **VPS with public IP** | Anchor / public peer / optional Tor exit / Yggdrasil-NAT to clearnet | `headless` | `TCPServerInterface` listening for incoming RNS peers; optional Tor / Yggdrasil exits |
| **SBC at home** (Pi, Orange Pi, …) with a Heltec / RNode plugged in | Bridge between LoRa airwaves, the home LAN and the rest of the mesh | `lora` | `RNodeInterface` (LoRa) + `AutoInterface` (LAN) + `TCPClientInterface` to one or more anchor VPSes |
| **Laptop / occasional client** | Plain user of the network | `lora` if a radio is plugged in, otherwise `headless` | Minimum: `TCPClientInterface` to an anchor; everything else is optional |

In short: **VPS = anchor, SBC = bridge, laptop = client.** The container
image is identical for all three; the difference is which interfaces are
enabled in the config and whether a radio is attached.

## Quick start

We publish multi-arch images (`amd64`, `arm64`) to **GitHub
Container Registry** and **Docker Hub** in lock-step on every
release:

- `ghcr.io/pazter1101/resilum:<profile>` (and `:<profile>-<version>`)
- `pazter1101/resilum:<profile>` (and `:<profile>-<version>`)

The default `docker-compose.yml` references the GHCR tag; switch
to Docker Hub by editing the `image:` line if GHCR is unreachable.
Docker pulls the right binary for your CPU automatically on
`docker compose up` — there is **no need to know your own
architecture or to build anything locally**. (If you are curious:
`uname -m` returns `x86_64` for AMD/Intel and `aarch64` for 64-bit
ARM, which covers virtually every modern SBC — Raspberry Pi 4/5,
Orange Pi, Rock Pi, etc. 32-bit ARM hosts like the original Pi
Zero W are not published; build locally if you really need that
target.)

The supplied `docker-compose.yml` exposes two run modes via Compose
profiles — pick the one that matches your hardware. The first command
pulls the image; subsequent runs use the cached copy.

### Without LoRa hardware

VPS, SBC, or laptop with no radio plugged in. Reticulum talks to the
rest of the mesh over whatever transports are enabled in the config
(clearnet TCP, Yggdrasil, Tor, I2P, ...).

```bash
docker compose --profile headless up
```

After ≈30 seconds the node has a working SOCKS5 endpoint at
`127.0.0.1:10808`. Point any app there to exit through some peer
that's also running Resilum:

```bash
curl --socks5-hostname 127.0.0.1:10808 https://api.ipify.org
# → public IP of whichever peer the discovery layer picked as your egress
```

Override the local port if 10808 collides with anything else
(Xray's default is also 10808):

```bash
RESILUM_SOCKS_PORT=10807 docker compose --profile headless up
```

### With a LoRa radio (Heltec V4 / RNode)

Plug in the radio first — Docker refuses to start the container if the
USB device is missing.

```bash
docker compose --profile lora up
```

If the radio is **not** on `/dev/ttyACM0` (e.g. CP2102-based RNodes
typically appear as `/dev/ttyUSB0`), point Compose at the right path:

```bash
LORA_DEVICE=/dev/ttyUSB0 docker compose --profile lora up
```

### Why the `--profile` flag at all

A Compose profile is the standard way to make a service start
conditionally without juggling override files. Both run modes share the
same container image and config — only the device-passthrough list
differs.

### Networking

`network_mode: host` so the SOCKS5 endpoint binds on the host's
loopback (`127.0.0.1:10808`) where local apps can reach it without
extra port-mapping. No iptables, no WireGuard, no kernel modules
required for the current SOCKS-mode runtime. Future L3-VPN mode
will additionally need `/dev/net/tun` and `cap_add: NET_ADMIN`,
both already wired in the supplied compose file.

## Building from source

For development or when iterating on the Dockerfile / a transport.
Compose will use the local image instead of pulling from the registry.

```bash
docker compose build
docker compose --profile headless up
```

To build a different profile, override the build-arg:

```bash
docker compose build --build-arg PROFILE=lora
```

## Roadmap

Done:

- All four profiles publish multi-arch (`amd64`, `arm64`) to GHCR
  and Docker Hub on every `dev → main` merge via `semantic-release`.
- Bidirectional Tor onion + I2P b32 as RNS underlays
  (`SocksTCPClientInterface`).
- SOCKS5 egress through the mesh; consume by default, opt in to
  also act as an exit for other peers.
- Auto-discovered targets via signed RNS announces; no static peer
  lists.
- Auto-selected community RNS bootstraps from
  [directory.rns.recipes](https://directory.rns.recipes), with
  Yggdrasil-IPv6 anchors as the no-clearnet fallback.

Next:

- L3-VPN tun mode for protocols that don't do SOCKS (UDP/QUIC,
  ICMP, full default-route redirect).
- Web UI (`127.0.0.1:8080`) for editing interfaces / peers / exit
  policy and viewing per-transport throughput.
- Wire the bundled covert transports (email / ICMP / DNS-tunnel)
  into discovery so they're not just binaries-in-image.
- Adaptive payload compression for the L3 VPN tunnel (issues
  #1–#4).

## Related projects

- [Reticulum Network Stack](https://reticulum.network/) — the routing
  fabric this project sits on top of.
- [RTNode-HeltecV4](https://github.com/jrl290/RTNode-HeltecV4) — the LoRa
  transport-node firmware, naturally pairs with Resilum on the host side.
- [Sideband](https://github.com/markqvist/sideband) — mobile messenger that
  speaks Reticulum out of the box; works through any Resilum node.
