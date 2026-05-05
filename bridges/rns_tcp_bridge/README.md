# `rns_tcp_bridge`

Tunnel a TCP stream over a [Reticulum](https://reticulum.network/) Link.

The bridge does not parse the payload, so it works for any stream-based
protocol — Yggdrasil peers, Tor's TCP transports, plain HTTP, an
internal admin API. As long as both sides agree on a target, anything
that fits in a TCP socket goes through.

## When to use it

- **You run an anchor on a VPS** and want to expose a service that
  already lives there (Yggdrasil daemon, Tor relay, internal HTTP API,
  ...) to the wider Reticulum mesh — peers reach it without knowing
  your IP, even when their only path is LoRa or email.
- **You are a client** that needs to talk to such a service through the
  mesh, on a host that does not necessarily have direct internet
  connectivity.

## Two run modes

| Mode | Side | What it does |
|---|---|---|
| `listen`  | anchor | Binds an RNS destination, accepts incoming Links, forwards each Link bidirectionally to a fixed local TCP endpoint |
| `connect` | client | Listens on a local TCP port; for each TCP connection opens an RNS Link to a known anchor identity and pumps bytes both ways |

Both sides participate in regular Reticulum routing — the Link rides
whatever underlay (LoRa, TCP, I2P, email, ...) RNS finds at the moment.

## Quick start: Yggdrasil over RNS

### Anchor side (VPS or any host with running Yggdrasil)

Yggdrasil already listens for TCP peers on, say, `127.0.0.1:9000`
(`Listen: ['tcp://127.0.0.1:9000']` in `yggdrasil.conf`). Expose it to
the mesh:

```bash
python -m rns_tcp_bridge listen \
    --identity   /var/lib/resilum/bridge-yggdrasil.id \
    --service    yggdrasil \
    --tcp        127.0.0.1:9000
```

Note the destination hash printed at startup
(`destination <hex> ...`) — clients need it.

### Client side

Run the bridge in `connect` mode and point your local Yggdrasil at the
loopback port it exposes:

```bash
python -m rns_tcp_bridge connect \
    --identity   ~/.config/resilum/bridge-yggdrasil.id \
    --service    yggdrasil \
    --tcp        127.0.0.1:9001 \
    --target     <hex hash from the anchor>
```

Then in your `yggdrasil.conf`:

```yaml
Peers:
  - tcp://127.0.0.1:9001
```

Yggdrasil peers up over the bridge. Once one peer is up, Yggdrasil's
own DHT discovers everyone else in the global mesh.

## Quick start: any other TCP service

Replace the `--service` aspect and the `--tcp` endpoint with whatever
you are bridging. Examples:

```bash
# Expose a local HTTP API
python -m rns_tcp_bridge listen --service api --tcp 127.0.0.1:8080 ...

# Expose a Tor ORPort (full pluggable transport is a separate project,
# but a plain TCP forward is enough for testing)
python -m rns_tcp_bridge listen --service tor --tcp 127.0.0.1:9001 ...
```

`--service` is just a name appended to the announced aspect path
(`resilum.bridge.tcp.<service>`). Pick something descriptive; clients
must use the same value.

## Discovery

The current MVP requires the client to know the anchor's destination
hash explicitly (`--target <hex>`). Anchors announce themselves
periodically (every 6 hours by default) so any node that has heard the
announce caches the path and can dial without network round-trips.

Aspect-only auto-discovery (start the client without `--target`, let
Reticulum find the closest anchor) is on the roadmap; for now copy the
hash that the anchor prints on startup.

## Identity file

The first run creates an Ed25519 / Curve25519 RNS identity and writes
it to the path passed via `--identity`. Treat it like an SSH private
key — anyone with that file can impersonate the bridge endpoint. On a
multi-tenant host, store it under `0700` permissions in a directory the
unprivileged service account owns.

## Logging

Reticulum log level is set via `--loglevel N` (0 = critical, 4 =
default, 7 = extreme). Bridge events use the standard `[bridge:listen]`
/ `[bridge:connect]` prefixes so they are easy to filter.

## Failover: how transparency actually works

The bridge itself is dumb on purpose — failover happens on the layers
*around* it, not inside it.

* **Underlay failover is built into Reticulum.** A live RNS Link is not
  tied to a specific interface. As long as there is at least one
  underlay reaching the peer (Yggdrasil, Tor, clearnet, LoRa, ICMP-pipe,
  ...), Transport keeps the Link alive across underlay changes. The
  application sees no break when, say, clearnet drops and the same Link
  starts riding LoRa instead.

* **Application-level reconnect is owned by the higher protocol.** If
  every underlay is gone long enough for the Link to die, the bridge
  closes the matching TCP socket. Yggdrasil, Tor, ssh, browsers and
  most modern protocols then reopen a new TCP to the bridge, the bridge
  establishes a new Link, and service resumes.

The result: from the perspective of a host plugged into the mesh
through the bridge, network changes look like ordinary connection
hiccups — same as roaming between Wi-Fi and 4G — and recovery is fully
automatic with no per-connection reconfiguration. The bridge does
nothing clever; it just does not get in the way.

## Other limitations

- One RNS Link per TCP connection. Long-running, low-throughput
  protocols (Yggdrasil keepalive, ssh, IM) work well; high-throughput
  streams (BitTorrent, video) saturate the slowest available underlay
  quickly.
- TCP only. The bridge tunnels stream protocols by design; UDP, ICMP,
  QUIC and other L4 traffic is handled at the layer *above* the bridge
  by an L3 mesh (typically Yggdrasil), which natively forwards any
  IPv6 payload.
