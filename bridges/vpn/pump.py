"""Bidirectional packet pump between a TUN file descriptor and an
RNS Channel reader/writer pair. Each direction runs in its own
thread and tears the other down on EOF.
"""

import os
import threading

import RNS
from RNS.Buffer import RawChannelReader, RawChannelWriter

from . import framing

TUN_READ_SIZE = 65536


def _shutdown(fd: int, link, closed: threading.Event) -> None:
    if closed.is_set():
        return
    closed.set()
    try:
        os.close(fd)
    except OSError:
        pass
    try:
        link.teardown()
    except Exception:
        pass


def _make_rns_to_tun(reader, fd, label, decoder, teardown):
    def callback(_ready):
        chunk = bytearray(_ready)
        n = reader.readinto(chunk)
        if not n:
            if reader._eof:
                teardown()
            return
        try:
            for packet in decoder.feed(bytes(chunk[:n])):
                os.write(fd, packet)
        except (framing.FramingError, OSError) as exc:
            RNS.log(f"[{label}/rns→tun] {exc}", RNS.LOG_WARNING)
            teardown()

    return callback


def _tun_to_rns(fd, writer, closed, label):
    try:
        while not closed.is_set():
            packet = os.read(fd, TUN_READ_SIZE)
            if not packet:
                break
            writer.write(framing.encode(packet))
    except OSError as exc:
        if not closed.is_set():
            RNS.log(f"[{label}/tun→rns] {exc}", RNS.LOG_DEBUG)
    finally:
        try:
            writer.close()
        except Exception:
            pass


def wire(link, fd: int, label: str) -> threading.Event:
    """Attach the RNS Link's bidirectional Channel to a TUN file
    descriptor. Returns the shared `closed` event so callers can wait
    on the tunnel's lifetime."""
    channel = link.get_channel()
    reader = RawChannelReader(0, channel)
    writer = RawChannelWriter(0, channel)
    decoder = framing.StreamDecoder()
    closed = threading.Event()

    def teardown() -> None:
        _shutdown(fd, link, closed)

    reader.add_ready_callback(_make_rns_to_tun(reader, fd, label, decoder, teardown))
    threading.Thread(
        target=_tun_to_rns,
        args=(fd, writer, closed, label),
        name=f"vpn-{label}-tun→rns",
        daemon=True,
    ).start()
    return closed
