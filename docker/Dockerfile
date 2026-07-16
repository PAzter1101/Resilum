# syntax=docker/dockerfile:1
# Resilum — multi-transport mesh node
#
# Single Dockerfile, four profile supersets selected via the PROFILE
# build-arg: lora < mesh < covert < full. Each profile is built on top
# of the previous one in dedicated stages so unchanged layers cache
# cleanly between rebuilds.
#
#   docker buildx build \
#     --build-arg PROFILE=lora \
#     --tag ghcr.io/pazter1101/resilum:lora \
#     --platform linux/amd64,linux/arm64,linux/arm/v7 \
#     -f docker/Dockerfile .

# Global build-arg: which superset becomes the final image. Must be declared
# before any FROM so it can be interpolated into the FROM at the bottom.
ARG PROFILE=lora

# ─── base ───────────────────────────────────────────────────────────────────
# Common runtime: Debian slim with Python and the bare-minimum networking
# tools required regardless of which transports are bundled.
#
# Debian 13 ("trixie", stable since 2025-08-09) ships Yggdrasil 0.5.x and
# Python 3.12 in main, so we get wire-compatible Yggdrasil out of the box
# without backports or third-party CDNs.
FROM debian:trixie-slim AS base

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        iproute2 \
        iptables \
        nftables \
        libcap2-bin \
        python3 \
        python3-pip \
        tini \
    && rm -rf /var/lib/apt/lists/*

# Run all daemons as a regular user so files written into the
# operator's /config bind-mount stay owned by them, not by root. The
# UID/GID can be overridden at runtime via `user:` in docker-compose
# to match the host user exactly.
RUN groupadd -g 1000 resilum && \
    useradd  -u 1000 -g 1000 -m -s /bin/sh resilum

# Reticulum stack — present in every profile.
# `--break-system-packages` is required on Debian 12+ to install into the
# system Python; we deliberately avoid a venv to keep image size minimal
# and the entrypoint trivial.
RUN --mount=from=ghcr.io/astral-sh/uv:0.9.5,source=/uv,target=/usr/local/bin/uv \
    --mount=type=bind,source=pyproject.toml,target=/tmp/dep/pyproject.toml \
    --mount=type=bind,source=uv.lock,target=/tmp/dep/uv.lock \
    uv export --directory /tmp/dep --frozen --no-default-groups --no-emit-project \
        --format requirements-txt \
    | pip install --no-cache-dir --break-system-packages --ignore-installed \
        --require-hashes -r /dev/stdin

# ─── lora ───────────────────────────────────────────────────────────────────
# Minimum viable Reticulum node: native interfaces (TCP/UDP/AutoInterface)
# plus a serial-attached LoRa radio (RNode/Heltec via USB CDC).
FROM base AS profile-lora

# `usbutils` is included for diagnostics (`lsusb` from inside the container
# while debugging USB pass-through). No additional Python packages are
# required: RNS' built-in `RNodeInterface` speaks directly to /dev/tty*.
RUN apt-get update && \
    apt-get install -y --no-install-recommends usbutils && \
    rm -rf /var/lib/apt/lists/*

# ─── mesh ───────────────────────────────────────────────────────────────────
# Public mesh overlays: Yggdrasil (encrypted IPv6 mesh) and I2P (anonymous
# overlay). Both run as separate daemons and Reticulum talks to them via
# standard TCPClientInterface / I2PInterface respectively.
FROM profile-lora AS profile-mesh

# Both yggdrasil and i2pd come from Debian trixie main; the 0.5.x
# yggdrasil is wire-compatible with the global mesh, no backports or
# third-party CDN involved.
#
# microsocks is a tiny (~10 KB), no-config SOCKS5 server. We bind it
# to 127.0.0.1 inside the container only — it is never directly
# reachable from outside. Its job is to be the egress endpoint behind
# our SOCKS-egress bridge: incoming RNS Links (from clients elsewhere
# in the mesh) terminate here and microsocks does the actual outbound
# connect from the VPS's public IP.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        yggdrasil \
        i2pd \
        microsocks \
    && rm -rf /var/lib/apt/lists/*

# ─── covert ─────────────────────────────────────────────────────────────────
# Anti-censorship transports: Tor + obfs4, DNS-tunnel (iodine), ICMP-tunnel,
# email transport. Each can be toggled independently at runtime.
FROM profile-mesh AS profile-covert

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        tor \
        obfs4proxy \
        iodine \
        libcap2-bin \
    && rm -rf /var/lib/apt/lists/*

# rns-over-icmp uses scapy; rns-covert-transport packages the email
# transport. Granting CAP_NET_RAW to the Python interpreter (required by
# scapy) is deliberately deferred to the final stage — applying setcap
# here puts Python into secure-execution mode and breaks subsequent
# `pip install` invocations in higher-superset profiles (e.g. `full`).
RUN --mount=from=ghcr.io/astral-sh/uv:0.9.5,source=/uv,target=/usr/local/bin/uv \
    --mount=type=bind,source=pyproject.toml,target=/tmp/dep/pyproject.toml \
    --mount=type=bind,source=uv.lock,target=/tmp/dep/uv.lock \
    uv export --directory /tmp/dep --frozen --no-default-groups --group covert \
        --no-emit-project --format requirements-txt \
    | pip install --no-cache-dir --break-system-packages --ignore-installed \
        --require-hashes -r /dev/stdin

# ─── full ───────────────────────────────────────────────────────────────────
# Everything plus the Meshtastic gateway. Pulls the largest dependency set
# (the meshtastic Python lib has heavy transitive deps).
FROM profile-covert AS profile-full

RUN --mount=from=ghcr.io/astral-sh/uv:0.9.5,source=/uv,target=/usr/local/bin/uv \
    --mount=type=bind,source=pyproject.toml,target=/tmp/dep/pyproject.toml \
    --mount=type=bind,source=uv.lock,target=/tmp/dep/uv.lock \
    uv export --directory /tmp/dep --frozen --no-default-groups --group full \
        --no-emit-project --format requirements-txt \
    | pip install --no-cache-dir --break-system-packages --ignore-installed \
        --require-hashes -r /dev/stdin

# ─── final ──────────────────────────────────────────────────────────────────
# Selects which of the four supersets is the final image based on the
# globally-declared PROFILE build-arg.
FROM profile-${PROFILE} AS final

# Where the user mounts their persistent config (RNS config, peers,
# transport-specific settings).
VOLUME ["/config"]
ENV RNS_CONFIG_DIR=/config/reticulum

# Resilum release version, baked at build time. Read at runtime by
# bridges/rns_tcp_bridge/version.py and broadcast in every announce
# so peers can drop us when their major doesn't match. Local builds
# without the build-arg fall back to "0.0.0", which is interpreted
# as "any 0.x peer is compatible".
ARG RESILUM_VERSION=0.0.0
ENV RESILUM_VERSION=${RESILUM_VERSION}

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Ship the bridge package and its supervisor inside the image. The
# supervisor reads /config/bridges.yaml at startup and spawns one
# `rns_tcp_bridge` child per entry.
COPY bridges /opt/resilum/bridges
ENV PYTHONPATH=/opt/resilum/bridges

# Default config snippets shipped inside the image. The entrypoint
# copies any of these into the operator-mounted /config/ directory on
# first run when the corresponding user file is missing, so the user
# always sees a populated, editable directory in their bind mount.
COPY config/defaults /opt/resilum/defaults
COPY scripts /opt/resilum/scripts

# Make Reticulum CLI tools (`rnstatus`, `rnpath`, `rnprobe`, ...) discover
# the daemon's shared instance without having to pass `--config` every
# time, by symlinking the canonical home-directory location to the
# operator-mounted config directory. The link points from the running
# user's $HOME (resilum), not /root, since rnsd no longer runs as root.
RUN ln -snf /config/reticulum /home/resilum/.reticulum

# Grant the capabilities each privileged-needing binary actually
# requires, so the container can run as an unprivileged user. The
# `+ep` mode keeps the capability "effective+permitted" but not
# inheritable — fine for daemons that don't fork to other binaries.
#
#   yggdrasil — needs CAP_NET_ADMIN to create the ygg0 TUN interface
#   iodine    — needs CAP_NET_ADMIN to create its DNS-tunnel TUN
#   python3   — needs CAP_NET_RAW for scapy-based ICMP transport
RUN if command -v yggdrasil >/dev/null 2>&1; then \
        setcap cap_net_admin+ep "$(command -v yggdrasil)"; \
    fi
RUN if command -v iodine >/dev/null 2>&1; then \
        setcap cap_net_admin+ep "$(command -v iodine)"; \
    fi
RUN setcap cap_net_raw,cap_net_admin+eip "$(readlink -f "$(command -v python3)")" || true

# State directories the unprivileged user must be able to write to.
RUN mkdir -p /config /var/run/yggdrasil && \
    chown -R resilum:resilum /config /var/run/yggdrasil /opt/resilum

USER resilum

# tini reaps zombies for the multi-process runtime (rnsd + optional
# tor / yggdrasil / i2pd / bridges all under one container).
ENTRYPOINT ["/usr/bin/tini", "--", "/entrypoint.sh"]
CMD []
