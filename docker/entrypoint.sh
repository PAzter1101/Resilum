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

# If the user did not mount a config, drop a minimal default in place so
# rnsd has something to start with. The default brings up an AutoInterface
# only — no clearnet peers, no public backbone — so the operator must
# explicitly opt in to whatever transport they want to use.
if [ ! -f "$CONFIG_DIR/config" ]; then
    echo "[entrypoint] no config found at $CONFIG_DIR/config, writing default"
    cat > "$CONFIG_DIR/config" <<'EOF'
[reticulum]
  enable_transport = Yes
  share_instance = Yes
  instance_name = resilum

[logging]
  loglevel = 4

[interfaces]
  [[Default Interface]]
    type = AutoInterface
    enabled = Yes
EOF
fi

# Helper: launch a daemon in the background only if its binary is present
# in the image (i.e. its profile bundled it) AND the user opted into it
# via an environment flag. Each ENABLE_* flag defaults to "0".
run_if_enabled() {
    flag="$1"
    binary="$2"
    shift 2
    eval "value=\${$flag:-0}"
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

# rnsd runs in the foreground as PID 1 (under tini) so its exit drives the
# container lifecycle.
exec rnsd --config "$CONFIG_DIR" "$@"
