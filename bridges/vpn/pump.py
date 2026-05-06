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

    def on_rns_data(_ready: int) -> None:
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

    reader.add_ready_callback(on_rns_data)

    def tun_to_rns() -> None:
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

    threading.Thread(
        target=tun_to_rns, name=f"vpn-{label}-tun→rns", daemon=True
    ).start()
    return closed
