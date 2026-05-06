"""Bidirectional byte glue between an RNS Channel and a TCP socket.

Either side closing tears down the other (and the Link)."""

import socket
import threading

import RNS
from RNS.Buffer import RawChannelReader, RawChannelWriter

from .constants import SOCKET_CHUNK


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

    def on_rns_data(ready):
        chunk = bytearray(ready)
        n = reader.readinto(chunk)
        if n:
            try:
                sock.sendall(bytes(chunk[:n]))
            except Exception as exc:
                RNS.log(f"[{label}/rns→tcp] {exc}", RNS.LOG_DEBUG)
                teardown()
        # readinto returns 0 (instead of None) once the writer on the
        # other side has called close() — propagate the EOF to the
        # local TCP socket so the application layer notices.
        if reader._eof:
            try:
                sock.shutdown(socket.SHUT_WR)
            except Exception:
                pass

    reader.add_ready_callback(on_rns_data)

    def tcp_to_rns():
        try:
            while True:
                chunk = sock.recv(SOCKET_CHUNK)
                if not chunk:
                    break
                writer.write(chunk)
        except Exception as exc:
            RNS.log(f"[{label}/tcp→rns] {exc}", RNS.LOG_DEBUG)
        finally:
            # Closing the writer flushes any pending data and emits an
            # EOF marker to the peer's reader; do this *before* tearing
            # the link down so the EOF actually makes it across.
            try:
                writer.close()
            except Exception:
                pass

    threading.Thread(target=tcp_to_rns, name=f"{label}/tcp→rns", daemon=True).start()
