from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.services.adapters.http.httpx import HttpxAdapter
from infrahub.tls.registry import TlsContextRegistry
from tests.helpers.http_server import SelfSignedTlsServer, SilentTcpServer

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def http_adapter() -> HttpxAdapter:
    """The HTTP adapter wired with its real collaborators, as it is constructed in production."""
    return HttpxAdapter(tls_registry=TlsContextRegistry())


@pytest.fixture
def silent_tcp_server() -> Iterator[SilentTcpServer]:
    """A TCP endpoint that accepts a connection but never replies, so a client read times out."""
    with SilentTcpServer() as server:
        yield server


@pytest.fixture
def self_signed_tls_server() -> Iterator[SelfSignedTlsServer]:
    """A TLS endpoint with a self-signed certificate, so a verifying client rejects the handshake."""
    with SelfSignedTlsServer() as server:
        yield server
