from __future__ import annotations

import ssl
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx
import pytest
from structlog.testing import capture_logs

from infrahub.exceptions import HTTPServerError, HTTPServerSSLError, HTTPServerTimeoutError
from infrahub.services.adapters.http.httpx import HttpxAdapter
from infrahub.tls.registry import TlsContextRegistry

if TYPE_CHECKING:
    from pytest_httpx import HTTPXMock


def _connect_error_wrapping(inner: BaseException, *, via: str) -> httpx.ConnectError:
    """Build a transport error that chains `inner` the way httpx surfaces a failed handshake."""
    error = httpx.ConnectError("connection failed")
    if via == "cause":
        error.__cause__ = inner
    else:
        error.__context__ = inner
    return error


@dataclass
class ExtractCase:
    name: str
    exc: BaseException
    expected: ssl.SSLError | None


_CERT_ERROR = ssl.SSLCertVerificationError("certificate verify failed: self-signed certificate")

EXTRACT_CASES = [
    ExtractCase(name="direct_ssl_error", exc=_CERT_ERROR, expected=_CERT_ERROR),
    ExtractCase(
        name="wrapped_in_context", exc=_connect_error_wrapping(_CERT_ERROR, via="context"), expected=_CERT_ERROR
    ),
    ExtractCase(name="wrapped_in_cause", exc=_connect_error_wrapping(_CERT_ERROR, via="cause"), expected=_CERT_ERROR),
    ExtractCase(
        name="nested_context",
        exc=_connect_error_wrapping(_connect_error_wrapping(_CERT_ERROR, via="context"), via="cause"),
        expected=_CERT_ERROR,
    ),
    ExtractCase(name="plain_connect_error", exc=httpx.ConnectError("connection refused"), expected=None),
]


@pytest.mark.parametrize("case", EXTRACT_CASES, ids=[case.name for case in EXTRACT_CASES])
def test_extract_ssl_error(case: ExtractCase) -> None:
    assert HttpxAdapter._extract_ssl_error(case.exc) is case.expected


def test_extract_ssl_error_tolerates_a_cycle() -> None:
    first = httpx.ConnectError("a")
    second = httpx.ConnectError("b")
    first.__context__ = second
    second.__context__ = first

    assert HttpxAdapter._extract_ssl_error(first) is None


URL = "https://example.test/hook"
URL_WITH_QUERY = f"{URL}?token=secret-value"
SECRET = "secret-value"


@pytest.fixture
def adapter() -> HttpxAdapter:
    return HttpxAdapter(tls_registry=TlsContextRegistry())


@dataclass
class FailedRequestCase:
    name: str
    error: Exception
    expected_error: type[HTTPServerError]
    expected_message: str
    expected_log_level: str
    expected_log: str


FAILED_REQUEST_CASES = [
    FailedRequestCase(
        name="timeout",
        error=httpx.ReadTimeout("timed out"),
        expected_error=HTTPServerTimeoutError,
        expected_message=f"Connection to {URL} timed out after 10",
        expected_log_level="info",
        expected_log=f"Connection timed out when trying to reach {URL}",
    ),
    FailedRequestCase(
        name="certificate_not_valid",
        error=_connect_error_wrapping(_CERT_ERROR, via="context"),
        expected_error=HTTPServerSSLError,
        expected_message=f"Unable to validate TLS certificate for connection to {URL}",
        expected_log_level="info",
        expected_log=f"TLS error for connection to {URL}",
    ),
    FailedRequestCase(
        name="other_tls_error",
        error=_connect_error_wrapping(ssl.SSLError("wrong version number"), via="context"),
        expected_error=HTTPServerSSLError,
        expected_message=f"TLS error when connecting to {URL}",
        expected_log_level="info",
        expected_log=f"TLS error for connection to {URL}",
    ),
    FailedRequestCase(
        name="other_error",
        error=httpx.ConnectError("connection refused"),
        expected_error=HTTPServerError,
        expected_message=f"Unknown http error when connecting to {URL}",
        expected_log_level="warning",
        expected_log=f"Unhandled HTTP error for {URL} (connection refused)",
    ),
    FailedRequestCase(
        name="error_that_repeats_a_request_header",
        error=httpx.LocalProtocolError("Illegal header value b'Bearer secret-value\\n'"),
        expected_error=HTTPServerError,
        expected_message=f"Unknown http error when connecting to {URL}",
        expected_log_level="warning",
        expected_log=f"Unhandled HTTP error for {URL} (LocalProtocolError)",
    ),
    FailedRequestCase(
        name="other_error_that_repeats_the_url",
        error=httpx.ConnectError(f"cannot reach {URL_WITH_QUERY}"),
        expected_error=HTTPServerError,
        expected_message=f"Unknown http error when connecting to {URL}",
        expected_log_level="warning",
        expected_log=f"Unhandled HTTP error for {URL} (cannot reach {URL}?[MASKED])",
    ),
    FailedRequestCase(
        name="other_error_that_repeats_a_url_with_user_and_password",
        error=httpx.ConnectError("cannot reach https://hookuser:secret-value@other.example.test/hook"),
        expected_error=HTTPServerError,
        expected_message=f"Unknown http error when connecting to {URL}",
        expected_log_level="warning",
        expected_log=f"Unhandled HTTP error for {URL} (cannot reach https://other.example.test/hook)",
    ),
]


@pytest.mark.parametrize("case", FAILED_REQUEST_CASES, ids=lambda case: case.name)
async def test_failed_request_is_reported_without_the_query_string_of_the_url(
    adapter: HttpxAdapter, httpx_mock: HTTPXMock, case: FailedRequestCase
) -> None:
    httpx_mock.add_exception(case.error)

    with capture_logs() as records, pytest.raises(case.expected_error) as raised:
        await adapter.post(url=URL_WITH_QUERY, json={"event": "created"})

    assert raised.value.message == case.expected_message
    assert records == [{"event": case.expected_log, "log_level": case.expected_log_level}]


async def test_failed_get_is_reported_without_its_request_parameters(
    adapter: HttpxAdapter, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_exception(httpx.ConnectError("connection refused"))

    with capture_logs() as records, pytest.raises(HTTPServerError) as raised:
        await adapter.get(url=URL, params={"token": SECRET})

    assert raised.value.message == f"Unknown http error when connecting to {URL}"
    assert records == [{"event": f"Unhandled HTTP error for {URL} (connection refused)", "log_level": "warning"}]


async def test_get_sends_its_request_parameters_in_the_query_string(
    adapter: HttpxAdapter, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(json={})

    await adapter.get(url=URL, params={"query": "member_key_id == 'otto@example.com'"}, headers={"X-Check": "1"})

    [request] = httpx_mock.get_requests()
    assert request.method == "GET"
    assert request.url.copy_with(query=None) == URL
    assert dict(request.url.params) == {"query": "member_key_id == 'otto@example.com'"}
    assert request.headers["X-Check"] == "1"
