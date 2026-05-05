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
FROM debian:bookworm-slim AS base

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        iproute2 \
        iptables \
        nftables \
        python3 \
        python3-pip \
        tini \
    && rm -rf /var/lib/apt/lists/*

# Reticulum stack — present in every profile.
# `--break-system-packages` is required on Debian 12+ to install into the
# system Python; we deliberately avoid a venv to keep image size minimal
# and the entrypoint trivial.
RUN pip install --no-cache-dir --break-system-packages rns

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

# Both yggdrasil and i2pd are shipped in Debian bookworm main, so we just
# pull them from the stock Debian mirror. The yggdrasil version there is
# slightly behind upstream (0.4.x vs the latest 0.5.x), but is sufficient
# for the public mesh and avoids dependency on third-party CDNs which
# may be unreachable from some networks.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        yggdrasil \
        i2pd \
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
RUN pip install --no-cache-dir --break-system-packages \
        scapy \
        rns-covert-transport

# ─── full ───────────────────────────────────────────────────────────────────
# Everything plus the Meshtastic gateway. Pulls the largest dependency set
# (the meshtastic Python lib has heavy transitive deps).
FROM profile-covert AS profile-full

RUN pip install --no-cache-dir --break-system-packages meshtastic

# ─── final ──────────────────────────────────────────────────────────────────
# Selects which of the four supersets is the final image based on the
# globally-declared PROFILE build-arg.
FROM profile-${PROFILE} AS final

# Where the user mounts their persistent config (RNS config, peers,
# transport-specific settings).
VOLUME ["/config"]
ENV RNS_CONFIG_DIR=/config/reticulum

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Make Reticulum CLI tools (`rnstatus`, `rnpath`, `rnprobe`, ...) discover
# the daemon's shared instance without having to pass `--config` every
# time, by symlinking the canonical home-directory location to the
# operator-mounted config directory.
RUN mkdir -p /root && ln -snf /config/reticulum /root/.reticulum

# Grant raw-socket capability to the Python interpreter so scapy-based
# transports (rns-over-icmp) can craft ICMP packets without privileged
# container mode. setcap puts Python into secure-execution mode, so it
# is intentionally the very last step — no `pip install` may follow.
# `setcap` is not present in the `lora` profile; ignore the absence
# silently when the target profile bundles neither scapy nor libcap2-bin.
RUN if command -v setcap >/dev/null 2>&1; then \
        setcap cap_net_raw,cap_net_admin+eip "$(readlink -f "$(command -v python3)")"; \
    fi

# tini reaps zombies for the multi-process runtime (rnsd + optional
# tor / yggdrasil / i2pd / bridges all under one container).
ENTRYPOINT ["/usr/bin/tini", "--", "/entrypoint.sh"]
CMD []
