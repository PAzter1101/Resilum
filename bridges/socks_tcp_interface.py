"""TCPClientInterface variant that dials through a SOCKS5 proxy.

When the supplied configuration carries ``socks_proxy_host`` and
``socks_proxy_port``, ``connect()`` is routed through PySocks with
remote DNS resolution (``rdns=True``) so ``.onion`` and other names
the local resolver cannot answer are handed to the proxy. Without
those keys, behaviour is identical to the upstream class.
"""

import platform
import socket

import RNS
import socks
from RNS.Interfaces.Interface import Interface
from RNS.Interfaces.TCPInterface import TCPClientInterface


class SocksTCPClientInterface(TCPClientInterface):
    def __init__(self, owner, configuration, connected_socket=None):
        c = Interface.get_config_obj(configuration)
        self._socks_host = c.get("socks_proxy_host") or None
        self._socks_port = (
            int(c["socks_proxy_port"]) if "socks_proxy_port" in c else None
        )
        super().__init__(owner, configuration, connected_socket=connected_socket)

    def connect(self, initial=False):
        if not (self._socks_host and self._socks_port):
            return super().connect(initial=initial)

        try:
            if initial:
                RNS.log(
                    f"Establishing SOCKS5 TCP connection for {self} "
                    f"via {self._socks_host}:{self._socks_port}...",
                    RNS.LOG_DEBUG,
                )

            s = socks.socksocket()
            s.set_proxy(socks.SOCKS5, self._socks_host, self._socks_port, rdns=True)
            s.settimeout(TCPClientInterface.INITIAL_CONNECT_TIMEOUT)
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            s.connect((self.target_ip, self.target_port))
            s.settimeout(None)
            self.socket = s
            self.online = True

            if initial:
                RNS.log(
                    f"SOCKS5 TCP connection for {self} established",
                    RNS.LOG_DEBUG,
                )

        except Exception as e:
            if initial:
                RNS.log(
                    f"Initial SOCKS5 connection for {self} could not "
                    f"be established: {e}",
                    RNS.LOG_ERROR,
                )
                RNS.log(
                    f"Leaving unconnected and retrying in "
                    f"{TCPClientInterface.RECONNECT_WAIT}s.",
                    RNS.LOG_ERROR,
                )
                return False
            raise

        if platform.system() == "Linux":
            self.set_timeouts_linux()
        elif platform.system() == "Darwin":
            self.set_timeouts_osx()

        self.online = True
        self.writing = False
        self.never_connected = False
        return True
