from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
import pytest
from structlog.testing import capture_logs

from infrahub.auth.auth import get_groups_from_provider
from infrahub.config import SecurityOAuth2Google, SecurityOAuth2Provider1
from infrahub.exceptions import HTTPServerError
from infrahub.services import InfrahubServices
from infrahub.services.adapters.http.httpx import HttpxAdapter
from infrahub.tls.registry import TlsContextRegistry
from tests.adapters.http import MemoryHTTP, RecordedGet

if TYPE_CHECKING:
    from pytest_httpx import HTTPXMock

EMAIL = "otto@example.com"
TOKEN_PAYLOAD = {"token_type": "Bearer", "access_token": "google-access-token"}
USER_INFO = {"sub": "u1", "name": "Otto", "email": EMAIL}


def _google(fetch_groups: bool = True) -> SecurityOAuth2Google:
    return SecurityOAuth2Google(client_id="infrahub", client_secret="secret", fetch_groups=fetch_groups)


async def test_google_group_lookup_sends_the_email_address_as_a_request_parameter() -> None:
    provider = _google()
    memory_http = MemoryHTTP()
    memory_http.add_get_response(
        url=provider.cloudidentity_url,
        response=httpx.Response(
            status_code=200,
            json={
                "memberships": [{"groupKey": {"id": "network@example.com"}}, {"groupKey": {"id": "ops@example.com"}}]
            },
        ),
    )
    service = await InfrahubServices.new(http=memory_http)

    groups = await get_groups_from_provider(
        provider=provider, service=service, payload=TOKEN_PAYLOAD, user_info=USER_INFO
    )

    assert groups == ["network@example.com", "ops@example.com"]
    assert memory_http.gets == [
        RecordedGet(
            url="https://cloudidentity.googleapis.com/v1/groups/-/memberships:searchDirectGroups",
            headers={"Authorization": "Bearer google-access-token"},
            params={"query": f"member_key_id == '{EMAIL}'"},
        )
    ]


async def test_google_group_lookup_puts_the_email_address_in_the_query_string_of_the_request(
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_response(json={})
    service = await InfrahubServices.new(http=HttpxAdapter(tls_registry=TlsContextRegistry()))

    groups = await get_groups_from_provider(
        provider=_google(), service=service, payload=TOKEN_PAYLOAD, user_info=USER_INFO
    )

    [request] = httpx_mock.get_requests()
    assert groups == []
    assert dict(request.url.params) == {"query": f"member_key_id == '{EMAIL}'"}


async def test_failed_google_group_lookup_is_reported_without_the_email_address(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_exception(httpx.ConnectError("connection refused"))
    service = await InfrahubServices.new(http=HttpxAdapter(tls_registry=TlsContextRegistry()))
    url = "https://cloudidentity.googleapis.com/v1/groups/-/memberships:searchDirectGroups"

    with capture_logs() as records, pytest.raises(HTTPServerError) as raised:
        await get_groups_from_provider(provider=_google(), service=service, payload=TOKEN_PAYLOAD, user_info=USER_INFO)

    assert raised.value.message == f"Unknown http error when connecting to {url}"
    assert records == [{"event": f"Unhandled HTTP error for {url} (connection refused)", "log_level": "warning"}]


@pytest.mark.parametrize(
    "provider",
    [
        _google(fetch_groups=False),
        SecurityOAuth2Provider1(
            client_id="infrahub",
            client_secret="secret",
            authorization_url="https://idp.example.com/auth",
            token_url="https://idp.example.com/token",
            userinfo_url="https://idp.example.com/userinfo",
        ),
    ],
    ids=["google_without_fetch_groups", "other_provider"],
)
async def test_no_group_lookup_request_when_the_provider_does_not_fetch_groups(
    provider: SecurityOAuth2Google | SecurityOAuth2Provider1,
) -> None:
    memory_http = MemoryHTTP()
    service = await InfrahubServices.new(http=memory_http)

    groups = await get_groups_from_provider(
        provider=provider, service=service, payload=TOKEN_PAYLOAD, user_info=USER_INFO
    )

    assert groups == []
    assert memory_http.gets == []
