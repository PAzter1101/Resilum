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

Early planning. Architecture is being prototyped; no usable build yet.

## Architecture sketch

The container exposes a single TUN device into the host's network namespace
(`--network host` + `/dev/net/tun`). Host applications use that TUN as the
default route — no WireGuard, no SOCKS proxy, no extra client software.

Inside the container, an iptables/nftables policy router decides per
destination which overlay carries the packet:

- **clearnet IP** → Tor TransProxy → Tor exit
- **Yggdrasil `200::/7`** → directly into the `yggdrasil0` interface
- **internal RNS destinations** → Reticulum native, no IP encapsulation

Reticulum (`rnsd`) sits below all of those and aggregates every available
underlying transport. It announces destinations through every enabled
interface in parallel and dynamically picks the best path per destination.
When one underlay dies (clearnet blocked, peer offline, LoRa link lost),
RNS reroutes through the next without disconnecting active sessions.

## Bundled transports

| Transport | Source | Status |
|---|---|---|
| TCP / UDP / AutoInterface | Reticulum core | ready |
| LoRa (RNode hardware) | Reticulum core + RTNode firmware | ready |
| I2P | Reticulum core via `i2pd` | ready |
| Email (IMAP/SMTP, fixed-size, locale-camo) | [TechVoid-Co/rns-covert-transport](https://github.com/TechVoid-Co/rns-covert-transport) | ready |
| ICMP-tunnel | [matvik22000/rns-over-icmp](https://github.com/matvik22000/rns-over-icmp) | ready |
| DNS-tunnel (iodine) | community recipe | ready |
| Meshtastic radios | [Nursedude/RNS-Meshtastic-Gateway-Tool](https://github.com/Nursedude/RNS-Meshtastic-Gateway-Tool) | ready |
| Yggdrasil-IPv6 mesh | [yggdrasil-network/yggdrasil-go](https://github.com/yggdrasil-network/yggdrasil-go) | ready |
| Tor onion as RNS-link | needs custom bridge (planned) | TODO |

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
upgrade paths are linear. Multi-arch builds (`amd64`, `arm64`, `armv7`) via
`docker buildx`, so the same tag pulls the right binary on a Pi Zero, an
Orange Pi, or an x86 laptop.

`debian:bookworm-slim` base, multi-stage build, no Rust toolchain, runtime
only in the final layer.

## Quick start

> Not yet runnable — containerisation is the first task. Check back soon.

```bash
docker run --rm -it \
  --network host \
  --cap-add=NET_ADMIN --cap-add=SYS_ADMIN \
  --device=/dev/net/tun \
  --device=/dev/ttyACM0 \
  -v "$(pwd)/config:/config" \
  ghcr.io/pazter1101/resilum:base
```

`--network host` is required so the in-container TUN appears on the host
side as a regular interface and policy routing on the host can target it
directly — no WireGuard or other VPN software on the host.

## Roadmap

1. **MVP**: `base` profile builds, container connects to a public RNS
   backbone, host can reach clearnet through Tor over a clearnet underlay.
2. **Bridges**: Tor-pluggable-transport over RNS so Tor itself works through
   the LoRa-only fallback.
3. **Web UI**: in-container web console (default `127.0.0.1:8080`) for
   editing the active set of interfaces, peers, exit policy and viewing
   per-transport throughput / RTT — replaces hand-editing TOML.
4. **Open exits**: discovery protocol so any node with clearnet can opt in
   as a public exit, and clients can find the closest one automatically.
5. **All four profiles** published to GHCR with multi-arch images
   (amd64 + arm64 + armv7 for Pi Zero).

## Related projects

- [Reticulum Network Stack](https://reticulum.network/) — the routing
  fabric this project sits on top of.
- [RTNode-HeltecV4](https://github.com/jrl290/RTNode-HeltecV4) — the LoRa
  transport-node firmware, naturally pairs with Resilum on the host side.
- [Sideband](https://github.com/markqvist/sideband) — mobile messenger that
  speaks Reticulum out of the box; works through any Resilum node.
