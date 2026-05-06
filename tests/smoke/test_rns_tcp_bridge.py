"""End-to-end smoke test for `rns_tcp_bridge`.

Spins up two real bridge processes (`listen` + `connect`) on top of a
fresh, isolated Reticulum config directory, sends a magic string
through the resulting TCP-over-RNS-Link tunnel, and asserts it arrives
on the listen side. No network access required — both sides
auto-discover each other through Reticulum's `AutoInterface` on
loopback.
"""

import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time

import pytest

pytest.importorskip("RNS", reason="Reticulum (rns) is not installed")

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BRIDGES_DIR = os.path.join(ROOT_DIR, "bridges")
HASH_RE = re.compile(r"destination <([0-9a-f]+)>")


def _free_port():
    """Ask the kernel for an unused TCP port on loopback."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _spawn_bridge(args, log_path):
    """Launch ``python -m rns_tcp_bridge`` with stdout+stderr redirected
    to ``log_path``. PYTHONUNBUFFERED so we can poll the log live."""
    env = {**os.environ, "PYTHONPATH": BRIDGES_DIR, "PYTHONUNBUFFERED": "1"}
    return subprocess.Popen(
        [sys.executable, "-u", "-m", "rns_tcp_bridge", *args],
        stdout=open(log_path, "w"),
        stderr=subprocess.STDOUT,
        env=env,
    )


def _wait_for_hash(log_path, timeout):
    """Poll ``log_path`` until the listen-side announces a destination
    hash, or raise on timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if os.path.exists(log_path):
            with open(log_path) as fh:
                m = HASH_RE.search(fh.read())
                if m:
                    return m.group(1)
        time.sleep(0.5)
    raise TimeoutError(f"no destination hash logged within {timeout}s")


def _tcp_sink(host, port_holder, ready_event):
    """Single-shot TCP server that records the first connection's bytes.
    Binds to an ephemeral port, publishes it via ``port_holder['port']``,
    then signals ``ready_event``."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, 0))
    port_holder["port"] = server.getsockname()[1]
    server.listen(1)
    ready_event.set()
    conn, _ = server.accept()
    chunks = []
    try:
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)
    finally:
        conn.close()
        server.close()
    return b"".join(chunks)


MINIMAL_RNS_CONFIG = """\
[reticulum]
  enable_transport = no
  share_instance = yes
  instance_name = smoke

[logging]
  loglevel = 5
"""


def _seed_minimal_config(rns_dir):
    os.makedirs(rns_dir, exist_ok=True)
    with open(os.path.join(rns_dir, "config"), "w") as fh:
        fh.write(MINIMAL_RNS_CONFIG)


def test_tcp_through_rns_link():
    work = tempfile.mkdtemp(prefix="resilum-smoke.")
    _seed_minimal_config(os.path.join(work, "rns"))
    listen_log = os.path.join(work, "listen.log")
    connect_log = os.path.join(work, "connect.log")
    received = {}
    sink_port = {}

    def run_sink():
        received["bytes"] = _tcp_sink("127.0.0.1", sink_port, sink_ready)

    sink_ready = threading.Event()
    sink_thread = threading.Thread(target=run_sink, daemon=True)
    sink_thread.start()
    assert sink_ready.wait(5), "TCP sink failed to bind"

    listen_port = sink_port["port"]
    connect_port = _free_port()

    listen_proc = _spawn_bridge(
        [
            "--config",
            os.path.join(work, "rns"),
            "--loglevel",
            "5",
            "listen",
            "--identity",
            os.path.join(work, "listen.id"),
            "--service",
            "smoke",
            "--tcp",
            f"127.0.0.1:{listen_port}",
        ],
        listen_log,
    )
    try:
        target_hash = _wait_for_hash(listen_log, timeout=60)

        connect_proc = _spawn_bridge(
            [
                "--config",
                os.path.join(work, "rns"),
                "--loglevel",
                "5",
                "connect",
                "--identity",
                os.path.join(work, "connect.id"),
                "--service",
                "smoke",
                "--tcp",
                f"127.0.0.1:{connect_port}",
                "--target",
                target_hash,
            ],
            connect_log,
        )
        try:
            time.sleep(5)  # connect side binds + warms up
            magic = f"resilum-smoke-{time.time_ns()}".encode()
            with socket.create_connection(("127.0.0.1", connect_port), timeout=10) as s:
                s.sendall(magic + b"\n")
                s.shutdown(socket.SHUT_WR)
            sink_thread.join(timeout=15)
            assert magic in received.get(
                "bytes", b""
            ), f"magic string did not reach the sink (got {received.get('bytes')!r})"
        finally:
            connect_proc.terminate()
            connect_proc.wait(timeout=5)
    finally:
        listen_proc.terminate()
        listen_proc.wait(timeout=5)
