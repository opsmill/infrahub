from __future__ import annotations

import ssl
from typing import TYPE_CHECKING

import httpx
import pytest
from prefect.client.orchestration import get_client

from infrahub import config
from infrahub.exceptions import HTTPServerError, HTTPServerSSLError, HTTPServerTimeoutError
from infrahub.services.adapters.http.httpx import HttpxAdapter
from tests.helpers.http_server import unused_tcp_port

if TYPE_CHECKING:
    from tests.helpers.http_server import SelfSignedTlsServer, SilentTcpServer


async def test_httpx_post(prefect_test_fixture: None, http_adapter: HttpxAdapter) -> None:
    async with get_client(sync_client=False) as client:
        # Use the Prefect API for testing as that is up and running
        # and needs to be accessible within the tests
        base_url = str(client.api_url)

    get_response = await http_adapter.get(f"{base_url}admin/settings")
    post_response = await http_adapter.post(f"{base_url}events/filter", json={"limit": 1})
    assert get_response.status_code == 200
    assert "api" in get_response.json()
    assert post_response.status_code == 200
    assert "total" in post_response.json()


async def test_connection_refused_is_http_server_error(http_adapter: HttpxAdapter) -> None:
    url = f"http://127.0.0.1:{unused_tcp_port()}"
    with pytest.raises(HTTPServerError) as exc_info:
        await http_adapter.post(url=url, json={})

    assert exc_info.value.message == f"Unknown http error when connecting to {url}"


async def test_self_signed_certificate_is_http_server_ssl_error(
    http_adapter: HttpxAdapter, self_signed_tls_server: SelfSignedTlsServer
) -> None:
    with pytest.raises(HTTPServerSSLError) as exc_info:
        await http_adapter.post(url=self_signed_tls_server.url, json={}, verify=True)

    assert (
        exc_info.value.message == f"Unable to validate TLS certificate for connection to {self_signed_tls_server.url}"
    )


async def test_failed_handshake_buries_the_ssl_error_in_a_transport_error(
    self_signed_tls_server: SelfSignedTlsServer,
) -> None:
    """A rejected handshake surfaces as a transport error, never as a bare ssl error.

    The ssl error is preserved only in the exception chain, so a certificate problem can be
    recognized only by walking that chain, not by catching the ssl error type directly. This
    pins the upstream behavior the classifier depends on.
    """
    async with httpx.AsyncClient(verify=True) as client:
        with pytest.raises(httpx.RequestError) as exc_info:
            await client.post(self_signed_tls_server.url, json={})

    raised = exc_info.value
    assert isinstance(raised, httpx.ConnectError)
    assert not isinstance(raised, ssl.SSLError)

    extracted = HttpxAdapter._extract_ssl_error(raised)
    assert isinstance(extracted, ssl.SSLError)


async def test_unresponsive_target_is_http_server_timeout_error(
    monkeypatch: pytest.MonkeyPatch, http_adapter: HttpxAdapter, silent_tcp_server: SilentTcpServer
) -> None:
    monkeypatch.setattr(config.SETTINGS.http, "timeout", 1)
    with pytest.raises(HTTPServerTimeoutError) as exc_info:
        await http_adapter.post(url=silent_tcp_server.url, json={})

    assert exc_info.value.message == f"Connection to {silent_tcp_server.url} timed out after 1"
