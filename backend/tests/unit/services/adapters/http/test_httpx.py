from __future__ import annotations

import ssl
from dataclasses import dataclass

import httpx
import pytest

from infrahub.services.adapters.http.httpx import HttpxAdapter


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
