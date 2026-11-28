from __future__ import annotations

import httpx
import pytest
from structlog.testing import capture_logs

from infrahub.auth.auth import safe_get_response_body, validate_auth_response
from infrahub.exceptions import GatewayError

URL = "https://idp.example.com/userinfo"
URL_WITH_QUERY = f"{URL}?access_token=secret-value"


def _response(status_code: int, content: bytes) -> httpx.Response:
    return httpx.Response(status_code=status_code, content=content, request=httpx.Request("GET", URL_WITH_QUERY))


def test_refused_request_is_logged_without_the_query_string_of_the_url() -> None:
    response = _response(status_code=401, content=b'{"error": "invalid_token"}')

    with capture_logs() as records, pytest.raises(GatewayError) as raised:
        validate_auth_response(response=response, provider_type="OAuth 2.0")

    assert raised.value.message == (
        "Unauthorized request to authentication provider. "
        "Please try again later or contact your administrator.: invalid_token"
    )
    assert records == [
        {
            "event": "Unauthorized request to OAuth 2.0 provider",
            "log_level": "error",
            "url": URL,
            "status_code": 401,
            "error": "invalid_token",
        }
    ]


@pytest.mark.parametrize(
    ("content", "expected_error"),
    [
        pytest.param(
            b'{"error": "invalid_client", "error_description": "Client otto-client-id for otto@example.com is disabled"}',
            "invalid_client",
            id="json_with_error_description",
        ),
        pytest.param(b"Account otto@example.com is locked", None, id="plain_text"),
        pytest.param(b'{"error": {"user": "otto@example.com"}}', None, id="error_that_is_not_a_string"),
    ],
)
def test_refused_request_logs_the_error_code_but_not_the_body(content: bytes, expected_error: str | None) -> None:
    response = _response(status_code=400, content=content)

    with capture_logs() as records, pytest.raises(GatewayError):
        validate_auth_response(response=response, provider_type="OIDC")

    assert [record["error"] for record in records] == [expected_error]
    assert "otto" not in str(records)


def test_empty_response_is_logged_without_the_query_string_of_the_url() -> None:
    response = _response(status_code=200, content=b" ")

    with capture_logs() as records, pytest.raises(GatewayError) as raised:
        safe_get_response_body(response=response)

    assert raised.value.message == "Unable to read response from authentication provider"
    assert [(record["event"], record["url"]) for record in records] == [
        ("Empty response body from authentication provider", URL),
        ("Unable to read response body from authentication provider", URL),
    ]
