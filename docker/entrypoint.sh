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

# Tor needs writeable state and hidden-service directories under /config.
mkdir -p /config/tor/data /config/tor/hidden_service
chmod 700 /config/tor/hidden_service 2>/dev/null || true

# RNS config lives at $CONFIG_DIR/config (no file extension by convention).
if [ ! -f "$CONFIG_DIR/config" ] && [ -f /opt/resilum/defaults/reticulum.config ]; then
    echo "[entrypoint] seeding default Reticulum config to $CONFIG_DIR/config"
    cp /opt/resilum/defaults/reticulum.config "$CONFIG_DIR/config"
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
run_if_enabled ENABLE_I2PD         i2pd        --conf=/config/i2pd.conf
run_if_enabled ENABLE_TOR          tor         -f /config/torrc
run_if_enabled ENABLE_IODINE       iodine      -f -P "${IODINE_PASSWORD:-}" "${IODINE_TOPDOMAIN:-}"

# Bridge supervisor: spawns one `rns_tcp_bridge` per entry in
# /config/bridges.yaml. Skipped silently if the file is absent.
if [ -f /config/bridges.yaml ]; then
    mkdir -p /config/bridges
    echo "[entrypoint] starting bridge supervisor"
    python3 -u -m supervisor /config/bridges.yaml &
fi

# rnsd runs in the foreground as PID 1 (under tini) so its exit drives the
# container lifecycle.
exec rnsd --config "$CONFIG_DIR" "$@"
