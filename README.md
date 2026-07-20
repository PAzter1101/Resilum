# Resilum

> Multi-transport mesh node for resilient, decentralized connectivity.

A single Docker container that turns any laptop, SBC or VPS into a node of a
mesh network built on [Reticulum](https://reticulum.network/). Connectivity
adapts across whatever transports are reachable — clearnet TCP/IP, Yggdrasil,
Tor, I2P, DNS/ICMP tunnels, and LoRa radio — and reroutes automatically when
one of them goes away.

Anyone with a spare device can join, route traffic for peers, and share in the
network's aggregate bandwidth and fault-tolerance. Because it is not tied to
TCP/IP, a node keeps talking to its peers over LoRa or other underlays when the
internet path is unavailable, and the encrypted overlay keeps delivering
traffic.

**Just want to run it?** Jump to [Quick start](#quick-start). The sections in
between explain how it works.

## Status

Multi-arch images (`amd64`, `arm64`) for all four profiles publish to **GitHub
Container Registry** and **Docker Hub** via `semantic-release`. Working end to
end: bidirectional Tor/I2P discovery, SOCKS5 egress through the mesh, RNS
interface-discovery, auto-selected community bootstraps, and the ICMP transport.
L3-VPN tun-mode (full default-route redirect) and the Web UI are planned.

## How it works

Each host runs a SOCKS5 proxy that tunnels through Reticulum to a peer with
internet and exits from that peer's public IP. Reticulum picks the best
underlay per destination (clearnet TCP, Yggdrasil, Tor, I2P, ICMP, LoRa) and
reroutes through another when one goes away, without dropping the session.

By default a node only runs the connect side: its own apps use another peer's
exit, but it does not relay other peers' traffic out of its own public IP.
Acting as an exit is opt-in (`ENABLE_SOCKS_EGRESS=1` plus the `listen
socks-egress` block in `bridges.yaml`); downstream traffic then appears to
originate from the operator's IP — the same legal/abuse exposure as running a
Tor exit or a public VPN. Targets are discovered through signed RNS announces;
no static peer lists.

See **[ARCHITECTURE.md](ARCHITECTURE.md)** for the data-flow and identity-model
diagrams.

## Transports

Ready today, plus the ones on the roadmap (issue links). Reticulum treats
each as one more interface to route over.

| Transport | Source | Status |
| --- | --- | --- |
| TCP / UDP / AutoInterface | Reticulum core | ready |
| LoRa (RNode hardware) | Reticulum core + RTNode firmware | ready |
| Yggdrasil-IPv6 mesh | [yggdrasil-network/yggdrasil-go](https://github.com/yggdrasil-network/yggdrasil-go) | ready |
| Tor onion as RNS-link | local Tor SOCKS + custom `SocksTCPClientInterface` | ready |
| I2P b32 as RNS-link | local i2pd SOCKS + custom `SocksTCPClientInterface` | ready |
| ICMP | Resilum (clean-room) | ready (covert profile) |
| Meshtastic radios | [Nursedude/RNS-Meshtastic-Gateway-Tool](https://github.com/Nursedude/RNS-Meshtastic-Gateway-Tool) | bundled, discovery integration planned ([#50](https://github.com/PAzter1101/Resilum/issues/50)) |
| DNS (iodine) | community recipe | binary bundled, integration planned ([#56](https://github.com/PAzter1101/Resilum/issues/56)) |
| Email (IMAP/SMTP) | [TechVoid-Co/rns-covert-transport](https://github.com/TechVoid-Co/rns-covert-transport) | bundled, integration planned |
| iroh QUIC (dial by key, NAT hole-punching) | [n0-computer/iroh](https://github.com/n0-computer/iroh) | planned ([#48](https://github.com/PAzter1101/Resilum/issues/48)) |
| BitTorrent Mainline DHT (low-rate data + rendezvous/holepunch) | BEP-44/50/55 | planned ([#57](https://github.com/PAzter1101/Resilum/issues/57)) |
| Sphinx mixnet (Katzenpost / Nym) | Katzenpost | planned ([#47](https://github.com/PAzter1101/Resilum/issues/47)) |
| Wi-Fi HaLow (802.11ah) underlay | recipe | planned ([#52](https://github.com/PAzter1101/Resilum/issues/52)) |
| Local Wi-Fi mesh (batman-adv) | recipe | planned ([#53](https://github.com/PAzter1101/Resilum/issues/53)) |
| Bluetooth last hop (RFCOMM) | recipe | planned ([#54](https://github.com/PAzter1101/Resilum/issues/54)) |
| LXMF delay-tolerant / sneakernet | Reticulum LXMF | planned ([#51](https://github.com/PAzter1101/Resilum/issues/51)) |
| libp2p / IPFS | — | under assessment ([#58](https://github.com/PAzter1101/Resilum/issues/58)) |

## Image profiles

The container is built as four feature-supersets so each operator picks the one
that fits their hardware and role. Every component in any profile can still be
toggled at runtime via the config file; the profile only controls what is
*physically in the image*.

| Tag | What it bundles | Typical use |
| --- | --- | --- |
| `resilum:lora` | rnsd + native RNS (TCP/UDP/AutoInterface) + USB stack for LoRa radios + iptables policy router | Minimum LoRa bridge: laptop with a Heltec, Pi Zero without other networks |
| `resilum:mesh` | `lora` + Yggdrasil-go + i2pd | Node in the public mesh overlays; SBC that already has clearnet |
| `resilum:covert` | `mesh` + Tor + obfs4proxy + iodine (DNS) + ICMP transport + email transport | Extra low-bandwidth transports for networks where direct clearnet is limited |
| `resilum:full` | `covert` + Meshtastic gateway + any experimental transports | All-in-one, nothing missing |

Each profile is a superset of the previous one, so layers cache cleanly and
upgrade paths are linear. Multi-arch builds (`amd64`, `arm64`) via `docker
buildx`, so the same tag pulls the right binary on an Orange Pi, a Raspberry Pi
4/5, or an x86 laptop.

`debian:trixie-slim` base, multi-stage build, apt pinned to a
`snapshot.debian.org` date for reproducible images, runtime only in the final
layer.

## Where to run it

The image is the same everywhere — pick the profile that matches the role the
device should play in the mesh.

| Device | Role in the mesh | Compose profile | What goes in `config/` |
| --- | --- | --- | --- |
| **VPS with public IP** | Anchor / public peer / optional Tor exit / Yggdrasil-NAT to clearnet | `headless` | `TCPServerInterface` listening for incoming RNS peers; optional Tor / Yggdrasil exits |
| **SBC at home** (Pi, Orange Pi, …) with a Heltec / RNode plugged in | Bridge between LoRa airwaves, the home LAN and the rest of the mesh | `lora` | `RNodeInterface` (LoRa) + `AutoInterface` (LAN) + `TCPClientInterface` to one or more anchor VPSes |
| **Laptop / occasional client** | Plain user of the network | `lora` if a radio is plugged in, otherwise `headless` | Minimum: `TCPClientInterface` to an anchor; everything else is optional |

In short: **VPS = anchor, SBC = bridge, laptop = client.** The image is
identical for all three; the difference is which interfaces are enabled in the
config and whether a radio is attached.

## Quick start

Multi-arch images (`amd64`, `arm64`) publish to **GitHub Container Registry**
and **Docker Hub** in lock-step on every release:

- `ghcr.io/pazter1101/resilum:<profile>` (and `:<profile>-<version>`)
- `pazter1101/resilum:<profile>` (and `:<profile>-<version>`)

The default `docker-compose.yml` references the GHCR tag; switch to Docker Hub
by editing the `image:` line if GHCR is unreachable. Docker pulls the right
binary for your CPU automatically — no need to build anything locally.

### Without LoRa hardware

VPS, SBC, or laptop with no radio. Reticulum talks to the rest of the mesh over
whatever transports are enabled in the config.

```bash
docker compose --profile headless up
```

After ≈30 seconds the node has a working SOCKS5 endpoint at `127.0.0.1:10808`.
Point any app there to exit through a peer that's also running Resilum:

```bash
curl --socks5-hostname 127.0.0.1:10808 https://api.ipify.org
# → public IP of whichever peer the discovery layer picked as your egress
```

Override the local port if 10808 collides with anything else (Xray's default is
also 10808):

```bash
RESILUM_SOCKS_PORT=10807 docker compose --profile headless up
```

### With a LoRa radio (Heltec V4 / RNode)

Plug in the radio first — Docker refuses to start the container if the USB
device is missing.

```bash
docker compose --profile lora up
```

If the radio is **not** on `/dev/ttyACM0` (CP2102-based RNodes typically appear
as `/dev/ttyUSB0`), point Compose at the right path:

```bash
LORA_DEVICE=/dev/ttyUSB0 docker compose --profile lora up
```

### Networking

`network_mode: host` so the SOCKS5 endpoint binds on the host's loopback
(`127.0.0.1:10808`) where local apps reach it without extra port-mapping. No
iptables, WireGuard or kernel modules required for the SOCKS-mode runtime. The
planned L3-VPN mode will additionally need `/dev/net/tun` and `cap_add:
NET_ADMIN`, both already wired in the supplied compose file.

### Public bind address

Two listeners accept traffic from outside the host: the Yggdrasil peer port
(`65533`) and the Reticulum TCP listener (`4242`). Both default to a dual-stack
wildcard (`[::]` / `::`) — accepting IPv4 and IPv6, the right default for a node
behind NAT or with one public IP.

To bind explicit addresses (a multi-IP VPS, or to keep a listener off a
management interface), set:

- `RESILUM_YGG_PUBLIC_LISTEN` — comma-separated `tcp://`/`tls://` URIs, IPv6 in
  brackets, e.g. `tcp://203.0.113.10:65533,tcp://[2001:db8::1]:65533`
- `RESILUM_RNS_LISTEN` — comma-separated `host:port`, IPv6 in brackets, e.g.
  `203.0.113.10:4242,[2001:db8::1]:4242`. Each entry becomes its own listener;
  the first is the discoverable one.

A malformed value stops the container on purpose, rather than silently binding
somewhere you did not intend.

The loopback service ports (Tor/i2pd SOCKS, the bridge endpoints, the SOCKS
egress) stay on `127.0.0.1` and are not configurable — exposing them would be a
security hole. Tor/I2P reachability comes from those overlays (`.onion` /
`.b32.i2p`), not from binding host interfaces.

## Building from source

For development or when iterating on the Dockerfile or a transport. Compose uses
the local image instead of pulling from the registry.

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

- All four profiles publish multi-arch (`amd64`, `arm64`) to GHCR and Docker
  Hub on every `dev → main` merge via `semantic-release`.
- Bidirectional Tor onion + I2P b32 as RNS underlays (`SocksTCPClientInterface`).
- SOCKS5 egress through the mesh; consume by default, opt in to also act as an
  exit for other peers.
- Auto-discovered targets via signed RNS announces; no static peer lists.
- Auto-selected community RNS bootstraps from
  [directory.rns.recipes](https://directory.rns.recipes), with Yggdrasil-IPv6
  anchors as the no-clearnet fallback.
- ICMP transport wired into RNS discovery (covert profile).

Next:

- L3-VPN tun mode for protocols that don't do SOCKS (UDP/QUIC, ICMP, full
  default-route redirect).
- Web UI (`127.0.0.1:8080`) for editing interfaces / peers / exit policy and
  viewing per-transport throughput.
- Wire the remaining bundled transports (DNS, email, Meshtastic) into discovery.
- Adaptive payload compression for the L3 VPN tunnel (issues #1–#4).

## Related projects

- [Reticulum Network Stack](https://reticulum.network/) — the routing fabric
  this project sits on top of.
- [RTNode-HeltecV4](https://github.com/jrl290/RTNode-HeltecV4) — the LoRa
  transport-node firmware, pairs with Resilum on the host side.
- [Sideband](https://github.com/markqvist/sideband) — mobile messenger that
  speaks Reticulum out of the box; works through any Resilum node.
