# syntax=docker/dockerfile:1
# Resilum — multi-transport mesh node. One Dockerfile, four profile supersets
# (lora < mesh < covert < full) as chained stages so shared layers cache.

# Declared before FROM so ${PROFILE} selects the final stage below.
ARG PROFILE=lora

# ─── base ────────────────────────────────────────────────────────────────────
FROM debian:trixie-slim@sha256:020c0d20b9880058cbe785a9db107156c3c75c2ac944a6aa7ab59f2add76a7bd AS base

ARG DEBIAN_FRONTEND=noninteractive

# pipefail so a failing `uv export` aborts the build instead of piping nothing
# into pip. Inherited by all stages.
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Every apt install bind-mounts a snapshot.debian.org source (never baked into
# the image, so runtime apt still points at live Debian) to keep the below
# `pkg=version` pins resolvable — the live mirror keeps only the newest build.
# Bump the date in apt-snapshot.sources and the versions together in a release.
RUN --mount=type=bind,source=docker/apt-snapshot.sources,target=/etc/apt/sources.list.d/debian.sources \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates=20250419 \
        iproute2=6.15.0-1 \
        iptables=1.8.11-2 \
        nftables=1.1.3-1 \
        libcap2-bin=1:2.75-10+deb13u1+b1 \
        python3=3.13.5-1 \
        python3-pip=25.1.1+dfsg-1 \
        tini=0.19.0-3+b7 \
    && rm -rf /var/lib/apt/lists/*

# Regular user so files written to the /config bind-mount stay host-owned;
# UID/GID overridable via compose `user:`.
RUN groupadd -g 1000 resilum && \
    useradd  -u 1000 -g 1000 -m -s /bin/sh resilum

# Reticulum stack, in every profile. --break-system-packages installs into the
# system Python (no venv) on Debian's externally-managed environment.
RUN --mount=from=ghcr.io/astral-sh/uv:0.9.5,source=/uv,target=/usr/local/bin/uv \
    --mount=type=bind,source=pyproject.toml,target=/tmp/dep/pyproject.toml \
    --mount=type=bind,source=uv.lock,target=/tmp/dep/uv.lock \
    uv export --directory /tmp/dep --frozen --no-default-groups --no-emit-project \
        --format requirements-txt \
    | pip install --no-cache-dir --break-system-packages --ignore-installed \
        --require-hashes -r /dev/stdin

# ─── lora ─── serial LoRa radios; usbutils for `lsusb` pass-through debugging.
FROM base AS profile-lora

RUN --mount=type=bind,source=docker/apt-snapshot.sources,target=/etc/apt/sources.list.d/debian.sources \
    apt-get update && \
    apt-get install -y --no-install-recommends usbutils=1:018-2 && \
    rm -rf /var/lib/apt/lists/*

# ─── mesh ─── Yggdrasil (IPv6 mesh) + i2pd; microsocks is the loopback-only
# SOCKS5 egress endpoint behind the SOCKS-egress bridge.
FROM profile-lora AS profile-mesh

RUN --mount=type=bind,source=docker/apt-snapshot.sources,target=/etc/apt/sources.list.d/debian.sources \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        yggdrasil=0.5.12-2+b4 \
        i2pd=2.56.0-1 \
        microsocks=1.0.5-1 \
    && rm -rf /var/lib/apt/lists/*

# ─── covert ─── Tor + obfs4, iodine (DNS tunnel), ICMP + email transports.
FROM profile-mesh AS profile-covert
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN --mount=type=bind,source=docker/apt-snapshot.sources,target=/etc/apt/sources.list.d/debian.sources \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        tor=0.4.9.11-0+deb13u1 \
        obfs4proxy=0.0.14-2+b5 \
        iodine=0.7.0-11 \
    && rm -rf /var/lib/apt/lists/*

RUN --mount=from=ghcr.io/astral-sh/uv:0.9.5,source=/uv,target=/usr/local/bin/uv \
    --mount=type=bind,source=pyproject.toml,target=/tmp/dep/pyproject.toml \
    --mount=type=bind,source=uv.lock,target=/tmp/dep/uv.lock \
    uv export --directory /tmp/dep --frozen --no-default-groups --group covert \
        --no-emit-project --format requirements-txt \
    | pip install --no-cache-dir --break-system-packages --ignore-installed \
        --require-hashes -r /dev/stdin

# ─── full ─── adds the Meshtastic gateway (heavy transitive deps).
FROM profile-covert AS profile-full
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN --mount=from=ghcr.io/astral-sh/uv:0.9.5,source=/uv,target=/usr/local/bin/uv \
    --mount=type=bind,source=pyproject.toml,target=/tmp/dep/pyproject.toml \
    --mount=type=bind,source=uv.lock,target=/tmp/dep/uv.lock \
    uv export --directory /tmp/dep --frozen --no-default-groups --group full \
        --no-emit-project --format requirements-txt \
    | pip install --no-cache-dir --break-system-packages --ignore-installed \
        --require-hashes -r /dev/stdin

# ─── final ───────────────────────────────────────────────────────────────────
# profile-${PROFILE} is an internal build stage chosen by the ARG, not a remote
# image, so there is no tag to pin.
# hadolint ignore=DL3006
FROM profile-${PROFILE} AS final

VOLUME ["/config"]
ENV RNS_CONFIG_DIR=/config/reticulum

# Baked release version, broadcast in announces for peer major-version compat;
# "0.0.0" (local builds) means "any 0.x peer".
ARG RESILUM_VERSION=0.0.0
ENV RESILUM_VERSION=${RESILUM_VERSION}

COPY --chmod=755 docker/entrypoint.sh /entrypoint.sh

COPY bridges /opt/resilum/bridges
ENV PYTHONPATH=/opt/resilum/bridges

# Shipped defaults; the entrypoint seeds any missing /config file from here.
COPY config/defaults /opt/resilum/defaults
COPY scripts /opt/resilum/scripts

# One layer of final setup: point the RNS CLIs (rnstatus, rnpath, ...) at the
# shared instance, grant each privileged-needing binary its capability so the
# container can run unprivileged, and create the writable state dirs.
#   yggdrasil / iodine — CAP_NET_ADMIN for their TUN devices
#   nft                — CAP_NET_ADMIN; file caps don't propagate from the python
#                        that spawns it, so grant on the binary itself
#   python3            — CAP_NET_RAW for the raw-socket ICMP transport
RUN ln -snf /config/reticulum /home/resilum/.reticulum && \
    if command -v yggdrasil >/dev/null 2>&1; then \
        setcap cap_net_admin+ep "$(command -v yggdrasil)"; fi && \
    if command -v iodine >/dev/null 2>&1; then \
        setcap cap_net_admin+ep "$(command -v iodine)"; fi && \
    if command -v nft >/dev/null 2>&1; then \
        setcap cap_net_admin+ep "$(readlink -f "$(command -v nft)")"; fi && \
    setcap cap_net_raw,cap_net_admin+eip "$(readlink -f "$(command -v python3)")" && \
    mkdir -p /config /var/run/yggdrasil && \
    chown -R resilum:resilum /config /var/run/yggdrasil /opt/resilum

USER resilum

# tini reaps zombies across the multi-process runtime.
ENTRYPOINT ["/usr/bin/tini", "--", "/entrypoint.sh"]
CMD []
