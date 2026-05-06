#!/bin/sh
# Resilum container entrypoint.
#
# Boots the Reticulum daemon and, depending on which optional daemons are
# present in this image AND enabled in the user config, launches them as
# background processes. Designed to be tini-reaped: every child writes its
# logs to stdout so `docker logs` shows everything in one place.

set -e

CONFIG_DIR="${RNS_CONFIG_DIR:-/config/reticulum}"
mkdir -p "$CONFIG_DIR"

# Yggdrasil's admin socket lives at /var/run/yggdrasil/yggdrasil.sock
# by default; the directory is not present in a fresh container.
mkdir -p /var/run/yggdrasil

# Seed any missing config file from the in-image defaults so the
# operator always sees populated, editable files in their /config bind
# mount on first run. Existing files are never overwritten.
seed_default() {
    src="/opt/resilum/defaults/$1"
    dst="/config/$1"
    if [ -f "$src" ] && [ ! -f "$dst" ]; then
        echo "[entrypoint] seeding default $dst"
        mkdir -p "$(dirname "$dst")"
        cp "$src" "$dst"
    fi
}

seed_default yggdrasil.conf
seed_default bridges.yaml
seed_default torrc
seed_default i2pd.conf
seed_default i2pd-tunnels.conf

# Tor needs writeable state and hidden-service directories under /config.
mkdir -p /config/tor/data /config/tor/hidden_service
chmod 700 /config/tor/hidden_service 2>/dev/null || true

# i2pd's datadir, generated keys and the exported hostname all live
# under /config/i2p/ so they survive container restarts.
mkdir -p /config/i2p/data /config/i2p/keys /config/i2p/hidden_service

# RNS config lives at $CONFIG_DIR/config (no file extension by convention).
if [ ! -f "$CONFIG_DIR/config" ] && [ -f /opt/resilum/defaults/reticulum.config ]; then
    echo "[entrypoint] seeding default Reticulum config to $CONFIG_DIR/config"
    cp /opt/resilum/defaults/reticulum.config "$CONFIG_DIR/config"
fi

# Network identity for interface-discovery. The default reticulum.config
# references it via `network_identity = ...`; without an existing key
# file rnsd silently exits when discovery is enabled. Generating it once
# on first boot keeps the same identity across container restarts.
NETWORK_IDENTITY="$CONFIG_DIR/storage/identities/resilum"
if [ ! -f "$NETWORK_IDENTITY" ]; then
    echo "[entrypoint] generating network identity at $NETWORK_IDENTITY"
    mkdir -p "$(dirname "$NETWORK_IDENTITY")"
    rnid -g "$NETWORK_IDENTITY" -q
fi

# First-run keypair generation for Yggdrasil. Failure in the helper
# is non-fatal — the operator can always paste keys manually into
# /config/yggdrasil.conf.
if command -v yggdrasil >/dev/null 2>&1; then
    python3 /opt/resilum/scripts/yggdrasil_seed_keys.py /config/yggdrasil.conf || true
fi

# Helper: launch a daemon in the background only if its binary is present
# in the image (i.e. its profile bundled it) AND the user opted into it
# via an environment flag. Each ENABLE_* flag defaults to "0".
run_if_enabled() {
    flag="$1"
    binary="$2"
    shift 2
    value=$(printenv "$flag" || echo 0)
    if [ "$value" = "1" ] && command -v "$binary" >/dev/null 2>&1; then
        echo "[entrypoint] starting $binary"
        "$binary" "$@" &
    elif [ "$value" = "1" ]; then
        echo "[entrypoint] WARNING: $flag=1 but $binary is not in this image profile"
    fi
}

run_if_enabled ENABLE_YGGDRASIL    yggdrasil   -useconffile /config/yggdrasil.conf
run_if_enabled ENABLE_I2PD         i2pd        --datadir=/config/i2p --conf=/config/i2pd.conf
run_if_enabled ENABLE_TOR          tor         -f /config/torrc
run_if_enabled ENABLE_IODINE       iodine      -f -P "${IODINE_PASSWORD:-}" "${IODINE_TOPDOMAIN:-}"
run_if_enabled ENABLE_SOCKS_EGRESS microsocks  -i 127.0.0.1 -p "${RESILUM_SOCKS_EGRESS_PORT:-1080}"

# When i2pd is enabled, derive the .b32.i2p hostname of our server
# tunnel from the keys file i2pd generates on first start, and write
# it where the i2p discovery plugin reads it from. Runs in the
# background — the helper polls the keys file and exits once written.
if [ "$(printenv ENABLE_I2PD || echo 0)" = "1" ] && command -v i2pd >/dev/null 2>&1; then
    python3 /opt/resilum/scripts/i2pd_export_hostname.py \
        /config/i2p/keys/rns-server.dat \
        /config/i2p/hidden_service/hostname &
fi

# rnsd MUST start before the bridge supervisor. If the supervisor's
# `import RNS; RNS.Reticulum(...)` runs first, *it* claims the
# `share_instance` slot, and the real rnsd that follows quietly
# downgrades to a client and exits — taking the container with it.
# So: launch rnsd in the background, wait until the shared instance
# is ready, then start the supervisor.
echo "[entrypoint] starting rnsd"
rnsd --config "$CONFIG_DIR" "$@" &
RNSD_PID=$!

# Wait for rnsd's shared instance to be up by probing rnstatus.
# Cap at ~30s; rnsd usually answers in under 5.
i=0
while [ $i -lt 30 ]; do
    if rnstatus >/dev/null 2>&1; then
        echo "[entrypoint] rnsd shared instance ready after ${i}s"
        break
    fi
    if ! kill -0 "$RNSD_PID" 2>/dev/null; then
        echo "[entrypoint] FATAL: rnsd exited before becoming ready"
        wait "$RNSD_PID"
        exit $?
    fi
    sleep 1
    i=$((i + 1))
done

# Bridge supervisor: spawns one `rns_tcp_bridge` per entry in
# /config/bridges.yaml. Now safe to start — rnsd already owns the
# shared instance, supervisor's RNS() call will join as a client.
if [ -f /config/bridges.yaml ]; then
    mkdir -p /config/bridges
    echo "[entrypoint] starting bridge supervisor"
    python3 -u -m supervisor /config/bridges.yaml &
fi

# Container lifecycle is tied to rnsd: wait on its PID so an rnsd
# crash propagates as the container's exit code (and tini reaps the
# rest).
wait "$RNSD_PID"
