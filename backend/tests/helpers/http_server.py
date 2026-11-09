"""Reusable local network endpoints for exercising the HTTP adapter against real failures.

Each server is a context manager that stands up a localhost endpoint failing in one specific way,
so a test can drive the real adapter and observe how that failure is surfaced, without mocking the
transport. Fixtures wrapping these are defined in the adapter-http test package's conftest.
"""

from __future__ import annotations

import contextlib
import socket
import ssl
import threading
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Self

# A self-signed certificate for 127.0.0.1 with a validity window fixed in the past, so it is both
# self-signed and expired: verification fails deterministically, with no clock dependence and
# nothing to regenerate. Paired with its private key in the same file.
SELF_SIGNED_CERT = Path(__file__).parent / "expired_self_signed_cert.pem"


def unused_tcp_port() -> int:
    """Return a localhost port with nothing listening, so a connection attempt is refused."""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


class BackgroundTcpServer:
    """A localhost TCP endpoint served from a background thread, usable as a context manager.

    The base owns the socket and thread lifecycle so a test gets a ready endpoint and a clean
    teardown; each subclass decides only how to handle an accepted connection.
    """

    scheme = "http"

    def __init__(self) -> None:
        self._listener = socket.socket()
        self._listener.bind(("127.0.0.1", 0))
        self._listener.listen(1)
        self._listener.settimeout(0.5)  # bounded accept so the loop can notice the stop signal
        self.port = int(self._listener.getsockname()[1])
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=True)

    @property
    def url(self) -> str:
        return f"{self.scheme}://127.0.0.1:{self.port}"

    def _handle(self, connection: socket.socket) -> None:
        raise NotImplementedError

    def _serve(self) -> None:
        while not self._stop.is_set():
            try:
                connection, _ = self._listener.accept()
            except OSError:
                continue
            try:
                self._handle(connection)
            finally:
                connection.close()

    def __enter__(self) -> Self:
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._stop.set()
        self._thread.join()
        self._listener.close()


class SilentTcpServer(BackgroundTcpServer):
    """Accepts a connection but never reads or replies, so the client's read times out."""

    def _handle(self, connection: socket.socket) -> None:
        self._stop.wait()  # hold the connection open, without responding, until teardown


class SelfSignedTlsServer(BackgroundTcpServer):
    """Presents a static, self-signed certificate, so a certificate-verifying client rejects the handshake."""

    scheme = "https"

    def __init__(self) -> None:
        super().__init__()
        self._context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self._context.load_cert_chain(certfile=str(SELF_SIGNED_CERT))

    def _handle(self, connection: socket.socket) -> None:
        # the client aborts the handshake when it rejects the self-signed certificate
        with contextlib.suppress(OSError):
            self._context.wrap_socket(connection, server_side=True)
