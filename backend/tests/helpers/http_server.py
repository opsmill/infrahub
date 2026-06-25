"""Reusable local network endpoints for exercising the HTTP adapter against real failures.

Each server is a context manager that stands up a localhost endpoint failing in one specific way,
so a test can drive the real adapter and observe how that failure is surfaced, without mocking the
transport. Fixtures wrapping these are defined in the adapter-http test package's conftest.
"""

from __future__ import annotations

import contextlib
import datetime
import ipaddress
import socket
import ssl
import tempfile
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

if TYPE_CHECKING:
    from typing import Self


def unused_tcp_port() -> int:
    """Return a localhost port with nothing listening, so a connection attempt is refused."""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


def write_self_signed_cert(directory: Path) -> tuple[str, str]:
    """Write a short-lived, self-signed certificate for 127.0.0.1 that no client should trust.

    The address is set in the Subject Alternative Name so the only thing wrong with the
    certificate is that it is self-signed, not a hostname mismatch. The validity starts a
    minute in the past to tolerate clock skew.
    """
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "127.0.0.1")])
    now = datetime.datetime.now(datetime.UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), critical=False)
        .sign(key, hashes.SHA256())
    )
    cert_file = directory / "cert.pem"
    key_file = directory / "key.pem"
    cert_file.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key_file.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    return str(cert_file), str(key_file)


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
    """Presents a self-signed certificate, so a certificate-verifying client rejects the handshake."""

    scheme = "https"

    def __init__(self) -> None:
        super().__init__()
        self._tmpdir = tempfile.TemporaryDirectory()
        cert_file, key_file = write_self_signed_cert(Path(self._tmpdir.name))
        self._context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self._context.load_cert_chain(certfile=cert_file, keyfile=key_file)

    def _handle(self, connection: socket.socket) -> None:
        # the client aborts the handshake when it rejects the self-signed certificate
        with contextlib.suppress(OSError):
            self._context.wrap_socket(connection, server_side=True)

    def __exit__(self, *exc: object) -> None:
        super().__exit__(*exc)
        self._tmpdir.cleanup()
