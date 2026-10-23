from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

import httpx
import pytest
from fastapi import FastAPI, Request, Response

from infrahub import config
from infrahub.api import oauth2, oidc
from infrahub.auth.auth import SSOStateCache
from infrahub.config import SecurityOAuth2Provider1, SecurityOIDCSettings
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.services import InfrahubServices
from tests.adapters.cache import MemoryCache
from tests.adapters.http import MemoryHTTP
from tests.helpers.log import find_logged_events
from tests.helpers.trace import recorded_spans

if TYPE_CHECKING:
    from collections.abc import Iterator

    from opentelemetry.sdk.trace import ReadableSpan

    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

PROVIDER_NAME = "provider1"
STATE = "state-1234"
AUTHORIZATION_CODE = "authorization-code-5678"
USER_INFO: dict[str, Any] = {
    "sub": "sub-telemetry-001",
    "name": "Grace Hopper",
    "email": "grace@example.com",
    "groups": ["operators", "auditors"],
}
TOKEN_RESPONSE: dict[str, Any] = {
    "access_token": "secret-access-token",
    "token_type": "Bearer",
    "expires_in": 600,
}

OIDC_PROVIDER = SecurityOIDCSettings(
    client_id="infrahub-client",
    discovery_url="https://oidc.example.com/.well-known/openid-configuration",
)
OIDC_DISCOVERY: dict[str, Any] = {
    "issuer": "https://oidc.example.com",
    "authorization_endpoint": "https://oidc.example.com/auth",
    "token_endpoint": "https://oidc.example.com/token",
    "userinfo_endpoint": "https://oidc.example.com/userinfo",
    "jwks_uri": "https://oidc.example.com/certs",
    "response_types_supported": ["code"],
    "subject_types_supported": ["public"],
    "id_token_signing_alg_values_supported": ["RS256"],
}

OAUTH2_PROVIDER = SecurityOAuth2Provider1(
    client_id="infrahub-client",
    client_secret="client-secret",
    authorization_url="https://idp.example.com/auth",
    token_url="https://idp.example.com/token",
    userinfo_url="https://idp.example.com/userinfo",
)


def _json_response(body: dict[str, Any]) -> httpx.Response:
    return httpx.Response(status_code=200, content=json.dumps(body))


async def _service_with_state(memory_http: MemoryHTTP, protocol: str) -> InfrahubServices:
    cache = MemoryCache()
    await cache.set(
        key=f"security:{protocol}:provider:{PROVIDER_NAME}:state:{STATE}",
        value=SSOStateCache(final_url="/").model_dump_json(),
    )
    return await InfrahubServices.new(cache=cache, http=memory_http)


def _token_request(service: InfrahubServices, protocol: str) -> Request:
    app = FastAPI()
    app.state.service = service
    return Request(
        scope={
            "type": "http",
            "app": app,
            "method": "GET",
            "scheme": "http",
            "server": ("testserver", 80),
            "root_path": "",
            "path": f"/api/{protocol}/{PROVIDER_NAME}/token",
            "query_string": b"",
            "headers": [],
        }
    )


def _spans_by_name(spans: tuple[ReadableSpan, ...], name: str) -> list[ReadableSpan]:
    return [span for span in spans if span.name == name]


def _assert_sso_spans_hold_no_personal_data(spans: tuple[ReadableSpan, ...]) -> None:
    (token_span,) = _spans_by_name(spans, "sso_token_request")
    (signin_span,) = _spans_by_name(spans, "signin_sso_account")

    for span in (token_span, signin_span):
        attributes = dict(span.attributes or {})
        assert "token_request_data" not in attributes
        assert "account_name" not in attributes
        assert attributes["provider_name"] == PROVIDER_NAME

    assert dict(signin_span.attributes or {})["sso_group_count"] == 2

    secrets = ("secret-access-token", "Grace Hopper", "grace@example.com", AUTHORIZATION_CODE, STATE)
    recorded_values = [
        str(value)
        for span in spans
        for attributes in (span.attributes, *(event.attributes for event in span.events))
        for value in (attributes or {}).values()
    ]
    assert [value for value in recorded_values if any(secret in value for secret in secrets)] == []


async def _signed_in_account_id(db: InfrahubDatabase) -> str:
    (account,) = await NodeManager.query(db=db, schema=InfrahubKind.ACCOUNT, filters={"name__value": USER_INFO["name"]})
    return account.id


def _assert_log_names_account_id(caplog: pytest.LogCaptureFixture, account_id: str) -> None:
    (entry,) = find_logged_events(caplog, event="SSO user authenticated")
    assert entry["body"]["account_id"] == account_id
    assert "user_name" not in entry["body"]
    assert "Grace Hopper" not in json.dumps(entry, default=str)


@pytest.fixture
def oidc_provider() -> Iterator[None]:
    settings = config.SETTINGS.security._oidc_settings
    original = dict(settings)
    settings[PROVIDER_NAME] = OIDC_PROVIDER
    yield
    settings.clear()
    settings.update(original)


@pytest.fixture
def oauth2_provider() -> Iterator[None]:
    settings = config.SETTINGS.security._oauth2_settings
    original = dict(settings)
    settings[PROVIDER_NAME] = OAUTH2_PROVIDER
    yield
    settings.clear()
    settings.update(original)


async def test_oidc_token_exchange_records_no_personal_data(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    oidc_provider: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    memory_http = MemoryHTTP()
    memory_http.add_get_response(url=OIDC_PROVIDER.discovery_url, response=_json_response(OIDC_DISCOVERY))
    memory_http.add_post_response(url=OIDC_DISCOVERY["token_endpoint"], response=_json_response(TOKEN_RESPONSE))
    memory_http.add_get_response(url=OIDC_DISCOVERY["userinfo_endpoint"], response=_json_response(USER_INFO))
    service = await _service_with_state(memory_http=memory_http, protocol="oidc")

    caplog.set_level(logging.INFO)
    with recorded_spans() as exported:
        result = await oidc.token(
            request=_token_request(service=service, protocol="oidc"),
            response=Response(),
            provider_name=PROVIDER_NAME,
            state=STATE,
            code=AUTHORIZATION_CODE,
            db=db,
        )
        spans = exported.get_finished_spans()

    assert result.access_token
    _assert_sso_spans_hold_no_personal_data(spans)
    _assert_log_names_account_id(caplog, account_id=await _signed_in_account_id(db=db))


async def test_oauth2_token_exchange_records_no_personal_data(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    oauth2_provider: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    memory_http = MemoryHTTP()
    memory_http.add_post_response(url=OAUTH2_PROVIDER.token_url, response=_json_response(TOKEN_RESPONSE))
    memory_http.add_get_response(url=OAUTH2_PROVIDER.userinfo_url, response=_json_response(USER_INFO))
    service = await _service_with_state(memory_http=memory_http, protocol="oauth2")

    caplog.set_level(logging.INFO)
    with recorded_spans() as exported:
        result = await oauth2.token(
            request=_token_request(service=service, protocol="oauth2"),
            response=Response(),
            provider_name=PROVIDER_NAME,
            state=STATE,
            code=AUTHORIZATION_CODE,
            db=db,
        )
        spans = exported.get_finished_spans()

    assert result.access_token
    _assert_sso_spans_hold_no_personal_data(spans)
    _assert_log_names_account_id(caplog, account_id=await _signed_in_account_id(db=db))
