"""TUN interface helpers.

Wraps the ioctl dance to create and configure a TUN device into
something the rest of the package can use without thinking about
file descriptors or `ip` invocations. Everything goes through
`subprocess` for the `ip` calls so we don't add another C-extension
dependency on top of the standard tun ioctl.
"""

import fcntl
import os
import struct
import subprocess

# /usr/include/linux/if_tun.h
TUNSETIFF = 0x400454CA
IFF_TUN = 0x0001
IFF_NO_PI = 0x1000  # don't prepend the 4-byte protocol header
TUN_DEV = "/dev/net/tun"


def open_tun(name: str) -> int:
    """Create or attach to a TUN device named ``name`` (kernel may
    rename it; the requested name is what we get on success). Returns
    the open file descriptor — caller is responsible for closing it."""
    fd = os.open(TUN_DEV, os.O_RDWR)
    ifreq = struct.pack("16sH", name.encode()[:15], IFF_TUN | IFF_NO_PI)
    try:
        fcntl.ioctl(fd, TUNSETIFF, ifreq)
    except OSError:
        os.close(fd)
        raise
    return fd


def configure(name: str, address: str, prefix_len: int, mtu: int) -> None:
    """Bring the TUN interface up with an IPv4 address and MTU."""
    subprocess.run(
        ["ip", "addr", "add", f"{address}/{prefix_len}", "dev", name],
        check=True,
    )
    subprocess.run(["ip", "link", "set", "dev", name, "mtu", str(mtu)], check=True)
    subprocess.run(["ip", "link", "set", "dev", name, "up"], check=True)


def teardown(name: str) -> None:
    """Best-effort: take the interface down. Ignore errors so the
    cleanup path doesn't blow up if something already removed it."""
    subprocess.run(
        ["ip", "link", "set", "dev", name, "down"],
        check=False,
        stderr=subprocess.DEVNULL,
    )


def replace_default_route(tun_name: str, gateway: str) -> str | None:
    """Replace the system default route with one pointing at the
    tunnel. Returns the previous default route (raw text from
    `ip route show default`) so it can be restored on shutdown, or
    None if the host had no default route to begin with."""
    out = subprocess.run(
        ["ip", "route", "show", "default"],
        capture_output=True,
        text=True,
        check=False,
    )
    previous = out.stdout.strip().splitlines()[0] if out.stdout.strip() else None
    subprocess.run(
        ["ip", "route", "del", "default"], check=False, stderr=subprocess.DEVNULL
    )
    subprocess.run(
        ["ip", "route", "add", "default", "via", gateway, "dev", tun_name],
        check=True,
    )
    return previous


def restore_default_route(previous: str | None) -> None:
    if previous is None:
        return
    subprocess.run(
        ["ip", "route", "del", "default"], check=False, stderr=subprocess.DEVNULL
    )
    subprocess.run(
        ["ip", "route", "add"] + previous.split(),
        check=False,
        stderr=subprocess.DEVNULL,
    )
