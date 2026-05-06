"""Bidirectional byte glue between an RNS Channel and a TCP socket.

Either side closing tears down the other (and the Link)."""

import socket
import threading
import time

import RNS
from RNS.Buffer import RawChannelReader, RawChannelWriter

from .constants import SOCKET_CHUNK

WRITE_BACKOFF = 0.05
WRITE_STALL_TIMEOUT = 30


def _shutdown(sock, link):
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except Exception:
        pass
    try:
        sock.close()
    except Exception:
        pass
    try:
        link.teardown()
    except Exception:
        pass


def _write_all(writer, data):
    """RawChannelWriter.write may consume less than the full chunk
    (capped at MAX_DATA_LEN per call, or 0 when the link is not yet
    ready). Loop until the whole buffer is delivered, bailing if the
    link refuses to drain for too long."""
    view = memoryview(data)
    deadline = time.time() + WRITE_STALL_TIMEOUT
    while view:
        n = writer.write(bytes(view))
        if not n:
            if time.time() >= deadline:
                raise RuntimeError(
                    f"link did not drain {len(view)} bytes "
                    f"within {WRITE_STALL_TIMEOUT}s"
                )
            time.sleep(WRITE_BACKOFF)
            continue
        view = view[n:]
        deadline = time.time() + WRITE_STALL_TIMEOUT


def _half_close_write(sock):
    try:
        sock.shutdown(socket.SHUT_WR)
    except Exception:
        pass


def _make_rns_to_tcp(reader, sock, label, teardown):
    def callback(ready):
        chunk = bytearray(ready)
        n = reader.readinto(chunk)
        if n:
            try:
                sock.sendall(bytes(chunk[:n]))
            except Exception as exc:
                RNS.log(f"[{label}/rns→tcp] {exc}", RNS.LOG_DEBUG)
                teardown()
                return
        if reader._eof:
            _half_close_write(sock)

    return callback


def _tcp_to_rns(sock, writer, label):
    try:
        while True:
            chunk = sock.recv(SOCKET_CHUNK)
            if not chunk:
                break
            _write_all(writer, chunk)
    except Exception as exc:
        RNS.log(f"[{label}/tcp→rns] {exc}", RNS.LOG_DEBUG)
    finally:
        try:
            writer.close()
        except Exception:
            pass


def wire_link_to_socket(link, sock, label):
    channel = link.get_channel()
    reader = RawChannelReader(0, channel)
    writer = RawChannelWriter(0, channel)
    closed = threading.Event()

    def teardown():
        if closed.is_set():
            return
        closed.set()
        _shutdown(sock, link)

    reader.add_ready_callback(_make_rns_to_tcp(reader, sock, label, teardown))
    threading.Thread(
        target=_tcp_to_rns,
        args=(sock, writer, label),
        name=f"{label}/tcp→rns",
        daemon=True,
    ).start()
